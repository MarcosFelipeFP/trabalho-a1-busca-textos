"""
preparar_corpus.py
------------------
Monta a base de documentos da Parte II baixando artigos da Wikipedia em
portugues sobre temas de Computacao e gravando cada um como um .txt em
`documentos/`.

O script existe para tornar o corpus reproduzivel: qualquer pessoa que clone o
repositorio consegue regerar exatamente a mesma base. Os .txt ja vao
versionados, entao rodar este script e opcional.

Conteudo sob licenca CC BY-SA 4.0 da Wikipedia (creditos no README.md).
Usa apenas a biblioteca padrao (urllib, json, re) -- nenhuma dependencia externa.

Uso:
    python preparar_corpus.py            # baixa apenas o que ainda falta
    python preparar_corpus.py --forcar   # rebaixa tudo, sobrescrevendo
"""

import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://pt.wikipedia.org/w/api.php"
USER_AGENT = "TrabalhoA1-UVA/1.0 (projeto academico; Analise e Otimizacao de Sistemas)"
PASTA_DESTINO = Path(__file__).parent / "documentos"

# Palavras minimas para o artigo ser aceito (descarta stubs e paginas vazias).
MINIMO_PALAVRAS = 200

# (titulo do artigo na Wikipedia PT, nome base do arquivo de saida)
ARTIGOS = [
    ("Algoritmo",                            "algoritmos"),
    ("Estrutura de dados",                   "estruturas_de_dados"),
    ("Inteligência artificial",              "inteligencia_artificial"),
    ("Aprendizado de máquina",               "aprendizado_de_maquina"),
    ("Aprendizagem profunda",                "aprendizagem_profunda"),
    ("Banco de dados",                       "banco_dados"),
    ("Rede de computadores",                 "redes"),
    ("Engenharia de software",               "engenharia_software"),
    ("Sistema operativo",                    "sistemas_operacionais"),
    ("Linguagem de programação",             "linguagens_programacao"),
    ("Programação orientada a objetos",      "programacao_orientada_objetos"),
    ("Complexidade computacional",           "complexidade_computacional"),
    ("Teoria dos grafos",                    "teoria_dos_grafos"),
    ("Compilador",                           "compiladores"),
    ("Criptografia",                         "criptografia"),
    ("Segurança da informação",              "seguranca_informacao"),
    ("Computação em nuvem",                  "computacao_nuvem"),
    ("Ciência de dados",                     "ciencia_de_dados"),
    ("Big data",                             "big_data"),
    ("Processamento de linguagem natural",   "processamento_linguagem_natural"),
    ("Recuperação de informação",            "recuperacao_informacao"),
    ("Arquitetura de computadores",          "arquitetura_computadores"),
    ("Computação quântica",                  "computacao_quantica"),
    ("Internet das coisas",                  "internet_das_coisas"),
]

# Secoes finais que sao so listas de links -- nao interessam ao corpus.
SECOES_DESCARTAVEIS = ("Ver também", "Ligações externas", "Referências", "Bibliografia", "Notas")


def baixar_extrato(titulo, tentativas=6):
    """
    Baixa o texto plano de um artigo da Wikipedia PT via API MediaWiki.

    A API aplica limite de requisicoes e responde HTTP 429 quando ele e
    estourado. Nesse caso (e em 503) a funcao espera um intervalo crescente
    -- backoff exponencial de 5s, 10s, 20s, 40s... -- antes de tentar de novo.
    """
    parametros = {
        "action": "query",
        "prop": "extracts",
        "explaintext": "1",
        "redirects": "1",
        "format": "json",
        "titles": titulo,
    }
    url = f"{API}?{urllib.parse.urlencode(parametros)}"
    requisicao = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    for tentativa in range(tentativas):
        try:
            with urllib.request.urlopen(requisicao, timeout=30) as resposta:
                dados = json.load(resposta)
            break
        except urllib.error.HTTPError as erro:
            ultima_tentativa = tentativa == tentativas - 1
            if erro.code in (429, 503) and not ultima_tentativa:
                espera = 5 * (2 ** tentativa)
                print(f"           (HTTP {erro.code} - aguardando {espera}s)", flush=True)
                time.sleep(espera)
                continue
            raise

    paginas = dados.get("query", {}).get("pages", {})
    if not paginas:
        return ""
    pagina = next(iter(paginas.values()))
    return pagina.get("extract", "") or ""


def limpar(texto):
    """Remove marcacoes de secao e normaliza o espacamento do extrato."""
    # Cabecalhos do tipo "== Historia ==" viram apenas "Historia".
    texto = re.sub(r"^=+\s*(.*?)\s*=+$", r"\1", texto, flags=re.MULTILINE)
    for secao in SECOES_DESCARTAVEIS:
        texto = re.split(rf"^{secao}\s*$", texto, flags=re.MULTILINE)[0]
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto.strip()


def ascii_seguro(nome):
    """Converte o nome do arquivo para ASCII puro, sem acentos."""
    normalizado = unicodedata.normalize("NFKD", nome)
    return "".join(c for c in normalizado if not unicodedata.combining(c))


def main():
    forcar = "--forcar" in sys.argv
    PASTA_DESTINO.mkdir(exist_ok=True)

    total_palavras = 0
    gravados = 0
    falhas = []

    print(f"Preparando corpus com {len(ARTIGOS)} artigos da Wikipedia PT\n")
    for titulo, nome_arquivo in ARTIGOS:
        destino = PASTA_DESTINO / f"{ascii_seguro(nome_arquivo)}.txt"

        # Ja baixado numa execucao anterior: reaproveita e segue em frente.
        if destino.exists() and not forcar:
            palavras = len(destino.read_text(encoding="utf-8").split())
            total_palavras += palavras
            gravados += 1
            print(f"  [EXISTE] {destino.name:<40} {palavras:>7,} palavras")
            continue

        try:
            texto = limpar(baixar_extrato(titulo))
        except Exception as erro:                 # rede, timeout, JSON invalido
            falhas.append((titulo, str(erro)))
            print(f"  [FALHA]  {titulo}: {erro}")
            continue

        if len(texto.split()) < MINIMO_PALAVRAS:
            falhas.append((titulo, "extrato curto demais"))
            print(f"  [CURTO]  {titulo}")
            continue

        destino.write_text(texto, encoding="utf-8")
        palavras = len(texto.split())
        total_palavras += palavras
        gravados += 1
        print(f"  [BAIXOU] {destino.name:<40} {palavras:>7,} palavras", flush=True)
        time.sleep(2.0)                           # cortesia com a API

    print(f"\n{gravados} arquivo(s) em '{PASTA_DESTINO.name}/'")
    print(f"Total aproximado: {total_palavras:,} palavras")
    if falhas:
        print(f"\n{len(falhas)} artigo(s) nao baixado(s) -- rode o script de novo:")
        for titulo, motivo in falhas:
            print(f"  - {titulo}: {motivo}")
    return 0 if gravados else 1


if __name__ == "__main__":
    sys.exit(main())
