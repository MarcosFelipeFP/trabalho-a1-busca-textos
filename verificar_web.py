"""
verificar_web.py
----------------
Confere que o motor JavaScript de `interface/src/algoritmos/` responde
exatamente o mesmo que os módulos Python deste repositório.

--------------------------------------------------------------------------
Por que este script existe
--------------------------------------------------------------------------
A versão offline da interface roda em um pendrive, sem Python instalado, e por
isso precisa dos algoritmos escritos também em JavaScript. Duas implementações
do mesmo algoritmo é uma oportunidade de divergência silenciosa: basta um
`<` virar `<=` em um dos lados para que a Trie devolva uma palavra a mais e
ninguém perceba até a apresentação.

A resposta não é confiar na tradução, é medir. Este script roda as duas
implementações sobre o MESMO corpus e o MESMO léxico e exige resultado
idêntico em doze frentes:

    1. normalização de acentos           todas as palavras do léxico
    2. tokenização                       os 24 documentos, token a token
    3. stemming RSLP                     todo o vocabulário do corpus
    4. Trie                              prefixos, contagens, nós e altura
    5. Trie comprimida (PATRICIA)        mesmos prefixos, contagens e nós
    6. autocomplete por relevância       ordem e pesos da busca best-first
    7. busca aproximada                  palavras, distâncias e pesos
    8. índice invertido                  frequência documental de cada radical
    9. consultas com vários termos       BM25 (tolerância 1e-9), interseção e
                                         "você quis dizer?"
   10. KMP                               posições e número de comparações
   11. tabela hash                       dispersão, colisões e maior cadeia

Requer o Node.js apenas aqui -- a página no navegador não precisa dele. Se o
`node` não estiver instalado, o script diz isso e sai sem falhar.

Uso:
    python verificar_web.py             confere tudo
    python verificar_web.py -v          lista cada comparação
"""

import argparse
import json
import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from indice_invertido import TabelaHash
from kmp import buscar_kmp
from main import carregar_lexico, configurar_saida
from mecanismo import MecanismoBusca
from preprocessamento import Preprocessador, carregar_stopwords
from stemmer_rslp import RSLP
from trie import Trie, TrieComprimida, distancia_edicao, normalizar

RAIZ = Path(__file__).parent
ALGORITMOS = RAIZ / "interface" / "src" / "algoritmos"
DADOS = RAIZ / "interface" / "src" / "dados"

ARQUIVOS_DADOS = ["corpus.json", "lexico.json", "stopwords.json"]

TOLERANCIA = 1e-9


# ==========================================================================
#  O LADO JAVASCRIPT
# ==========================================================================

# Os algoritmos são módulos ES, os mesmos arquivos que o Vite empacota na
# página: o adaptador só os importa e roda os casos. Nada dos algoritmos é
# reescrito aqui.
ADAPTADOR = r"""
import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const [pasta, dados, arquivoEntrada, saida] = process.argv.slice(2);
const entrada = JSON.parse(fs.readFileSync(arquivoEntrada, 'utf8'));

const carregar = (nome) => import(pathToFileURL(path.join(pasta, nome)).href);
const A1 = {
  ...(await carregar('trie.js')),
  ...(await carregar('stemmer-rslp.js')),
  ...(await carregar('kmp.js')),
  ...(await carregar('mecanismo.js')),
};
const ler = (nome) => JSON.parse(fs.readFileSync(path.join(dados, nome), 'utf8'));
const D = { corpus: ler('corpus.json'), lexico: ler('lexico.json'), stopwords: ler('stopwords.json') };

/* --- as mesmas estruturas que a página monta ao abrir --- */
const stemmer = new A1.RSLP();
const trieLexico = new A1.Trie(D.lexico);
const patriciaLexico = new A1.TrieComprimida(D.lexico);
const mecanismo = new A1.MecanismoBusca({
  documentos: D.corpus, stopwords: D.stopwords, usarStemming: true,
});
mecanismo.construir();

const preprocessador = mecanismo.preprocessador;

/* --- 1. normalização --- */
const normalizacao = entrada.palavras.map((p) => A1.normalizar(p));

/* --- 2. tokenização --- */
const tokenizacao = {};
for (const documento of D.corpus) {
  const [brutos, filtrados] = preprocessador.processarDetalhado(documento.texto);
  tokenizacao[documento.nome] = { brutos: brutos.length, filtrados, amostra: brutos.slice(0, 50) };
}

/* --- 3. stemming --- */
const stemming = entrada.vocabulario.map((p) => stemmer.radicalizar(p));

/* --- 4 e 5. tries --- */
const trie = {
  palavras: trieLexico.tamanho,
  nos: trieLexico.totalNos(),
  altura: trieLexico.altura(),
  prefixos: entrada.prefixos.map((p) => ({
    prefixo: p,
    palavras: trieLexico.buscarPrefixo(p, 40),
    total: trieLexico.contarPrefixo(p),
    existe: trieLexico.buscar(p),
  })),
};

const patricia = {
  palavras: patriciaLexico.tamanho,
  nos: patriciaLexico.totalNos(),
  prefixos: entrada.prefixos.map((p) => patriciaLexico.buscarPrefixo(p, 40)),
  totais: entrada.prefixos.map((p) => patriciaLexico.contarPrefixo(p)),
};

/* --- autocomplete por relevância (busca best-first sobre os pesos) --- */
const sugestoes = {};
for (const p of entrada.prefixos) {
  sugestoes[p] = mecanismo.trie.sugerir(p, 10);
}

/* --- busca aproximada: no léxico (pesos iguais) e no vocabulário (frequência) --- */
const aproximadas = { lexico: {}, vocabulario: {}, distancias: [] };
for (const q of entrada.aproximadas) {
  aproximadas.lexico[q] = trieLexico.buscarAproximado(q, null, null);
  aproximadas.vocabulario[q] = mecanismo.trie.buscarAproximado(q, 2, 8);
}
for (const [a, b] of entrada.pares) aproximadas.distancias.push(A1.distanciaEdicao(a, b));

const vocabulario = {
  palavras: mecanismo.trie.tamanho,
  nos: mecanismo.trie.totalNos(),
  nos_comprimida: mecanismo.trieComprimida.totalNos(),
};

/* --- 6. índice invertido --- */
const indice = {
  termos: mecanismo.indice.totalTermos(),
  termos_exatos: mecanismo.indice.totalTermos(false),
  postagens: mecanismo.indice.totalPostagens(),
  tokens: mecanismo.indice.totalTokens,
  tamanho_medio: mecanismo.indice.tamanhoMedio(),
  postagem: {},
};
for (const termo of entrada.termos) {
  indice.postagem[termo] = mecanismo.indice.buscar(termo, true);
}

/* --- 7. consultas: BM25, vários termos e "você quis dizer?" --- */
const ranking = {};
for (const consulta of entrada.consultas) {
  const resposta = mecanismo.buscarPalavra(consulta);
  ranking[consulta] = {
    radical: resposta.radical,
    documentos: resposta.documentos,
    resto: {
      termos: resposta.termos,
      ignorados: resposta.ignorados,
      frequencias: resposta.frequencias,
      cobertura: resposta.cobertura,
      todos: resposta.todos,
      aproximadas: resposta.aproximadas,
      correcao: resposta.correcao,
    },
  };
}

/* --- 8. KMP --- */
const kmp = {};
for (const padrao of entrada.padroes) {
  const porDocumento = {};
  let comparacoes = 0;
  for (const documento of D.corpus) {
    const achado = A1.buscarKmp(documento.texto.toLowerCase(), padrao.toLowerCase());
    comparacoes += achado.comparacoes;
    if (achado.ocorrencias.length) porDocumento[documento.nome] = achado.ocorrencias;
  }
  kmp[padrao] = { documentos: porDocumento, comparacoes };
}

/* --- 9. tabela hash --- */
const hash = mecanismo.indice.espelharEmTabelaHash().estatisticas();

fs.writeFileSync(saida, JSON.stringify({
  normalizacao, tokenizacao, stemming, trie, patricia, sugestoes, aproximadas,
  vocabulario, indice, ranking, kmp, hash,
}));
"""


def executar_node(entrada):
    """Roda o adaptador no Node e devolve o JSON produzido pelo lado JavaScript."""
    node = shutil.which("node")
    if node is None:
        return None

    with tempfile.TemporaryDirectory(prefix="verificar_web_") as pasta:
        pasta = Path(pasta)
        adaptador = pasta / "adaptador.mjs"
        arquivo_entrada = pasta / "entrada.json"
        arquivo_saida = pasta / "saida.json"

        adaptador.write_text(ADAPTADOR, encoding="utf-8")
        arquivo_entrada.write_text(json.dumps(entrada, ensure_ascii=False), encoding="utf-8")

        processo = subprocess.run(
            [node, "--stack-size=8000", str(adaptador), str(ALGORITMOS), str(DADOS),
             str(arquivo_entrada), str(arquivo_saida)],
            capture_output=True, text=True, encoding="utf-8",
        )
        if processo.returncode != 0:
            raise RuntimeError(
                "o motor JavaScript nao rodou:\n" + (processo.stderr or processo.stdout))

        return json.loads(arquivo_saida.read_text(encoding="utf-8"))


# ==========================================================================
#  COMPARAÇÃO
# ==========================================================================

class Relatorio:
    """Acumula o resultado das comparações e imprime o resumo no final."""

    def __init__(self, detalhado=False):
        self.detalhado = detalhado
        self.frentes = []

    def conferir(self, nome, esperado, obtido, casos, amostra=None):
        """
        Registra uma frente de comparação.

        `casos` é quantas unidades foram confrontadas -- palavras, tokens,
        documentos --, porque "stemming: igual" diz muito menos que "stemming:
        14.812 palavras, nenhuma divergência".
        """
        igual = esperado == obtido
        self.frentes.append((nome, igual, casos, amostra if not igual else None))

        marca = "ok " if igual else "FALHA"
        print(f"  [{marca}] {nome:<34} {casos:>8,} casos".replace(",", "."))
        if not igual and amostra:
            for linha in amostra[:6]:
                print(f"          {linha}")
        return igual

    def resumo(self):
        falhas = [nome for nome, igual, _casos, _a in self.frentes if not igual]
        total_casos = sum(casos for _n, _i, casos, _a in self.frentes)

        print()
        print("=" * 64)
        if falhas:
            print(f"  {len(falhas)} frente(s) divergiram: {', '.join(falhas)}")
        else:
            print(f"  Os dois motores concordam em {total_casos:,} casos.".replace(",", "."))
            print("  O JavaScript de interface/src/algoritmos/ responde o mesmo que o Python.")
        print("=" * 64)
        return 0 if not falhas else 1


def quase_igual(a, b):
    """Compara números com tolerância, e o resto por igualdade estrutural."""
    if isinstance(a, float) or isinstance(b, float):
        return math.isclose(a, b, rel_tol=TOLERANCIA, abs_tol=TOLERANCIA)
    return a == b


def comparar_ranking(python, javascript):
    """
    Confronta duas listas [(documento, pontuação)].

    A ordem tem de ser a mesma e as pontuações precisam coincidir dentro da
    tolerância -- BM25 envolve logaritmo e divisão, e exigir igualdade binária
    entre duas linguagens seria exigir o impossível.
    """
    if len(python) != len(javascript):
        return False, f"{len(python)} documentos no Python, {len(javascript)} no JS"
    for (documento_py, nota_py), par_js in zip(python, javascript):
        documento_js, nota_js = par_js
        if documento_py != documento_js:
            return False, f"ordem diferente: {documento_py} contra {documento_js}"
        if not quase_igual(nota_py, nota_js):
            return False, f"{documento_py}: {nota_py!r} contra {nota_js!r}"
    return True, None


# ==========================================================================
#  ROTEIRO
# ==========================================================================

def montar_entrada(lexico, vocabulario):
    """
    Define os casos de teste -- os mesmos dos dois lados, gerados aqui.

    A escolha é determinística de propósito: rodar de novo tem de confrontar
    exatamente os mesmos casos, senão uma execução verde não diz nada sobre a
    seguinte.
    """
    vocabulario_ordenado = sorted(vocabulario)

    prefixos = [chr(letra) for letra in range(ord("a"), ord("z") + 1)]
    prefixos += ["comp", "algo", "estrut", "dado", "busc", "program", "rede",
                 "computacao", "computação", "zzz", "", "xyzk"]
    prefixos += sorted({normalizar(palavra)[:3] for palavra in vocabulario_ordenado[::40]})
    prefixos += sorted({normalizar(palavra)[:5] for palavra in vocabulario_ordenado[::97]})

    consultas = ["algoritmo", "algoritmos", "computação", "dados", "rede",
                 "programação", "inteligência", "busca", "criptografia",
                 "quântico", "aprendizado", "grafos", "inexistente", "de",
                 # vários termos, stopwords no meio e termos repetidos
                 "rede neural", "estrutura de dados", "chave pública",
                 "algoritmo algoritmos", "banco de dados relacional",
                 # erros de digitação: o "você quis dizer?"
                 "algortimo", "estrutra de dados", "rede neurl", "hahs",
                 "busca de algortimo", "xyzkw"]

    padroes = ["chave pública", "algoritmo", "busca binária", "árvore",
               "índice invertido", "O(n log n)", "Trie", "zzzz",
               "aprendizado de máquina", "; ", "computação quântica"]

    # Erros de digitação fabricados de forma determinística: para uma palavra
    # a cada 150 do léxico, uma transposição, uma remoção e uma troca.
    aproximadas = ["algortimo", "computacao", "hahs", "estrutra", "xyzw", "a", "rde"]
    for palavra in lexico[::150]:
        letras = list(normalizar(palavra))
        if len(letras) >= 4:
            trocada = letras[:]
            trocada[1], trocada[2] = trocada[2], trocada[1]
            aproximadas.append("".join(trocada))
            aproximadas.append("".join(letras[:len(letras) // 2] + letras[len(letras) // 2 + 1:]))
            aproximadas.append("".join(letras[:-1] + ["x"]))

    pares = [("algortimo", "algoritmo"), ("kitten", "sitting"), ("", "abc"),
             ("ca", "abc"), ("computação", "computacao"), ("abcdef", "badcfe")]
    pares += [(normalizar(a), normalizar(b))
              for a, b in zip(lexico[::97], lexico[13::97])]

    return {
        "palavras": lexico[:4000],
        "vocabulario": vocabulario_ordenado,
        "prefixos": sorted(set(prefixos)),
        "aproximadas": aproximadas,
        "pares": pares,
        "termos": sorted({RSLP().radicalizar(p) for p in vocabulario_ordenado[::7]}),
        "consultas": consultas,
        "padroes": padroes,
    }


def main():
    configurar_saida()
    analisador = argparse.ArgumentParser(
        description="Confere se o motor JavaScript responde o mesmo que o Python.")
    analisador.add_argument("-v", "--detalhado", action="store_true",
                            help="lista as divergências encontradas")
    argumentos = analisador.parse_args()

    faltando = [nome for nome in ARQUIVOS_DADOS if not (DADOS / nome).is_file()]
    if faltando:
        print(f"[erro] faltam os dados da versao offline: {', '.join(faltando)}")
        print("       Rode `python gerar_dados_web.py` primeiro.")
        return 1

    print("Construindo as estruturas em Python...")
    lexico = carregar_lexico("palavras.txt")
    stopwords = carregar_stopwords()
    preprocessador = Preprocessador(stopwords=stopwords, usar_stemming=True)
    stemmer = RSLP()

    trie_lexico = Trie(lexico)
    patricia_lexico = TrieComprimida(lexico)

    mecanismo = MecanismoBusca("documentos", usar_stemming=True)
    mecanismo.construir()

    entrada = montar_entrada(lexico, mecanismo.vocabulario)

    print("Rodando os mesmos casos no motor JavaScript (Node)...")
    try:
        js = executar_node(entrada)
    except RuntimeError as falha:
        print(f"\n[erro] {falha}")
        return 1

    if js is None:
        print("\n[aviso] `node` nao encontrado no PATH; nada foi comparado.")
        print("        A pagina do navegador nao precisa do Node -- ele so e")
        print("        necessario para rodar esta verificacao fora do navegador.")
        return 0

    print("\nComparando os dois motores:\n")
    relatorio = Relatorio(argumentos.detalhado)

    # --- 1. normalização ---
    esperado = [normalizar(p) for p in entrada["palavras"]]
    divergentes = [f"{p!r}: {a!r} contra {b!r}"
                   for p, a, b in zip(entrada["palavras"], esperado, js["normalizacao"])
                   if a != b]
    relatorio.conferir("normalizacao de acentos", esperado, js["normalizacao"],
                       len(esperado), divergentes)

    # --- 2. tokenização ---
    tokens_python, tokens_js, casos, divergentes = {}, {}, 0, []
    for arquivo in sorted(Path("documentos").glob("*.txt")):
        texto = arquivo.read_text(encoding="utf-8", errors="replace")
        brutos, filtrados = preprocessador.processar_detalhado(texto)
        casos += len(brutos)
        lado_js = js["tokenizacao"][arquivo.name]
        tokens_python[arquivo.name] = {
            "brutos": len(brutos), "filtrados": filtrados, "amostra": brutos[:50]}
        tokens_js[arquivo.name] = lado_js
        if filtrados != lado_js["filtrados"]:
            for posicao, (a, b) in enumerate(zip(filtrados, lado_js["filtrados"])):
                if a != b:
                    divergentes.append(f"{arquivo.name} token {posicao}: {a!r} contra {b!r}")
                    break
    relatorio.conferir("tokenizacao dos documentos", tokens_python, tokens_js,
                       casos, divergentes)

    # --- 3. stemming ---
    esperado = [stemmer.radicalizar(p) for p in entrada["vocabulario"]]
    divergentes = [f"{p!r}: {a!r} contra {b!r}"
                   for p, a, b in zip(entrada["vocabulario"], esperado, js["stemming"])
                   if a != b]
    relatorio.conferir("stemming RSLP", esperado, js["stemming"],
                       len(esperado), divergentes)

    # --- 4. Trie ---
    prefixos_python = [{
        "prefixo": prefixo,
        "palavras": trie_lexico.buscar_prefixo(prefixo, limite=40),
        "total": trie_lexico.contar_prefixo(prefixo),
        "existe": trie_lexico.buscar(prefixo),
    } for prefixo in entrada["prefixos"]]
    trie_python = {
        "palavras": len(trie_lexico),
        "nos": trie_lexico.total_nos(),
        "altura": trie_lexico.altura(),
        "prefixos": prefixos_python,
    }
    divergentes = [f"prefixo {a['prefixo']!r}: {a['total']} contra {b['total']} palavras"
                   for a, b in zip(prefixos_python, js["trie"]["prefixos"]) if a != b]
    relatorio.conferir("Trie do lexico", trie_python, js["trie"],
                       len(entrada["prefixos"]), divergentes)

    # --- 5. Trie comprimida ---
    patricia_python = {
        "palavras": len(patricia_lexico),
        "nos": patricia_lexico.total_nos(),
        "prefixos": [patricia_lexico.buscar_prefixo(p, limite=40)
                     for p in entrada["prefixos"]],
        "totais": [patricia_lexico.contar_prefixo(p) for p in entrada["prefixos"]],
    }
    relatorio.conferir("Trie comprimida (PATRICIA)", patricia_python, js["patricia"],
                       len(entrada["prefixos"]))

    # --- autocomplete por relevância ---
    # Confere a busca best-first: mesma ordem, mesmos pesos, mesmos empates.
    # As tuplas do Python viram listas no JSON, então a comparação é feita
    # sobre listas dos dois lados.
    sugestoes_python, divergentes = {}, []
    for prefixo in entrada["prefixos"]:
        sugestoes_python[prefixo] = [[palavra, peso] for palavra, peso
                                     in mecanismo.trie.sugerir(prefixo, limite=10)]
        if sugestoes_python[prefixo] != js["sugestoes"].get(prefixo):
            divergentes.append(f"prefixo {prefixo!r}: {sugestoes_python[prefixo][:3]} "
                               f"contra {(js['sugestoes'].get(prefixo) or [])[:3]}")
    relatorio.conferir("autocomplete por relevancia", sugestoes_python, js["sugestoes"],
                       len(entrada["prefixos"]), divergentes)

    # --- busca aproximada ---
    # Mesmas palavras, mesmas distâncias, mesmos pesos e mesma ordem de
    # desempate, na Trie do léxico (pesos iguais, desempate alfabético) e na do
    # vocabulário (pesos pela frequência no corpus).
    como_listas = lambda trios: [list(trio) for trio in trios]  # noqa: E731
    aproximadas_python = {
        "lexico": {q: como_listas(trie_lexico.buscar_aproximado(q, limite=None))
                   for q in entrada["aproximadas"]},
        "vocabulario": {q: como_listas(mecanismo.trie.buscar_aproximado(q, 2, limite=8))
                        for q in entrada["aproximadas"]},
        "distancias": [distancia_edicao(a, b) for a, b in entrada["pares"]],
    }
    divergentes = [f"{q!r}: {aproximadas_python['lexico'][q][:3]} contra "
                   f"{js['aproximadas']['lexico'].get(q, [])[:3]}"
                   for q in entrada["aproximadas"]
                   if aproximadas_python["lexico"][q] != js["aproximadas"]["lexico"].get(q)]
    relatorio.conferir("busca aproximada", aproximadas_python,
                       js["aproximadas"],
                       2 * len(entrada["aproximadas"]) + len(entrada["pares"]), divergentes)

    # --- vocabulário do corpus ---
    vocabulario_python = {
        "palavras": len(mecanismo.trie),
        "nos": mecanismo.trie.total_nos(),
        "nos_comprimida": mecanismo.trie_comprimida.total_nos(),
    }
    relatorio.conferir("vocabulario do corpus", vocabulario_python, js["vocabulario"], 3)

    # --- 6. índice invertido ---
    indice_python = {
        "termos": mecanismo.indice.total_termos(),
        "termos_exatos": mecanismo.indice.total_termos(usar_radical=False),
        "postagens": mecanismo.indice.total_postagens(),
        "tokens": mecanismo.indice.total_tokens,
        "tamanho_medio": mecanismo.indice.tamanho_medio(),
        "postagem": {termo: mecanismo.indice.buscar(termo) for termo in entrada["termos"]},
    }
    divergentes = [f"radical {termo!r}: {indice_python['postagem'][termo]} contra "
                   f"{js['indice']['postagem'].get(termo)}"
                   for termo in entrada["termos"]
                   if indice_python["postagem"][termo] != js["indice"]["postagem"].get(termo)]
    relatorio.conferir("indice invertido", indice_python, js["indice"],
                       len(entrada["termos"]), divergentes)

    # --- 7. consultas: BM25, vários termos e "você quis dizer?" ---
    iguais, divergentes = True, []
    for consulta in entrada["consultas"]:
        resposta = mecanismo.buscar_palavra(consulta)
        lado_js = js["ranking"][consulta]
        if resposta["radical"] != lado_js["radical"]:
            iguais = False
            divergentes.append(f"{consulta!r}: radical {resposta['radical']!r} "
                               f"contra {lado_js['radical']!r}")
            continue
        ok, motivo = comparar_ranking(resposta["documentos"], lado_js["documentos"])
        if not ok:
            iguais = False
            divergentes.append(f"{consulta!r}: {motivo}")
            continue
        # O resto da resposta passa por JSON antes de comparar, para que as
        # tuplas do Python virem listas como as do JavaScript.
        resto = json.loads(json.dumps({
            chave: resposta[chave] for chave in
            ("termos", "ignorados", "frequencias", "cobertura", "todos",
             "aproximadas", "correcao")
        }, ensure_ascii=False))
        for chave, valor in resto.items():
            if valor != lado_js["resto"].get(chave):
                iguais = False
                divergentes.append(f"{consulta!r}: '{chave}' {valor!r} contra "
                                   f"{lado_js['resto'].get(chave)!r}")
    relatorio.conferir("consultas: BM25 e varios termos", True, iguais,
                       len(entrada["consultas"]), divergentes)

    # --- 8. KMP ---
    kmp_python, divergentes = {}, []
    for padrao in entrada["padroes"]:
        por_documento, comparacoes = {}, 0
        for documento, texto in sorted(mecanismo.conteudo.items()):
            achado = buscar_kmp(texto.lower(), padrao.lower())
            comparacoes += achado.comparacoes
            if achado.ocorrencias:
                por_documento[documento] = achado.ocorrencias
        kmp_python[padrao] = {"documentos": por_documento, "comparacoes": comparacoes}
        if kmp_python[padrao] != js["kmp"].get(padrao):
            lado_js = js["kmp"].get(padrao, {})
            divergentes.append(f"{padrao!r}: {comparacoes} comparacoes contra "
                               f"{lado_js.get('comparacoes')}")
    relatorio.conferir("KMP sobre o corpus", kmp_python, js["kmp"],
                       len(entrada["padroes"]), divergentes)

    # --- 9. tabela hash ---
    tabela = TabelaHash(capacidade=1024)
    for termo, postagem in mecanismo.indice.por_radical.items():
        tabela.inserir(termo, postagem)
    relatorio.conferir("tabela hash do indice", tabela.estatisticas(), js["hash"],
                       len(mecanismo.indice.por_radical))

    return relatorio.resumo()


if __name__ == "__main__":
    sys.exit(main())
