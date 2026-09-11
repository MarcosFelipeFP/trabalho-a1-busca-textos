"""
testes.py
---------
Testes automatizados das estruturas e algoritmos do trabalho.

Usa `unittest`, da biblioteca padrão -- nenhuma dependência externa. Os testes
cobrem quatro frentes:

  * casos dos exemplos do enunciado, para garantir que o programa produz
    exatamente a saída pedida;
  * casos de borda (entrada vazia, prefixo inexistente, padrão maior que o
    texto), onde implementações de Trie e KMP costumam quebrar;
  * testes de propriedade com entradas aleatórias, comparando o KMP contra a
    busca ingênua e a Trie comprimida contra a tradicional -- duas
    implementações independentes que precisam concordar sempre;
  * um teste ponta a ponta que monta um índice em uma pasta temporária.

Uso:
    python testes.py
    python testes.py -v
"""

import http.client
import json
import random
import shutil
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from indice_invertido import IndiceInvertido, TabelaHash
from kmp import buscar_ingenuo, buscar_kmp, tabela_falha
from mecanismo import MecanismoBusca
from preprocessamento import Preprocessador, remover_pontuacao, tokenizar
from servidor import Aplicacao, criar_servidor
from stemmer_rslp import RSLP
from trie import Trie, TrieComprimida, normalizar

# Palavras da seção 2.2 do enunciado.
EXEMPLO_ENUNCIADO = [
    "computador", "computação", "computacional", "compilador",
    "complexidade", "programação", "processador", "processamento",
]


class TesteNormalizacao(unittest.TestCase):

    def test_remove_acentos_e_caixa(self):
        self.assertEqual(normalizar("Computação"), "computacao")
        self.assertEqual(normalizar("ÁÉÍÓÚ"), "aeiou")
        self.assertEqual(normalizar("  Ônibus  "), "onibus")

    def test_texto_sem_acento_nao_muda(self):
        self.assertEqual(normalizar("algoritmo"), "algoritmo")

    def test_string_vazia(self):
        self.assertEqual(normalizar(""), "")


class TesteTrie(unittest.TestCase):

    def setUp(self):
        self.trie = Trie(EXEMPLO_ENUNCIADO)

    def test_exemplo_do_enunciado(self):
        """A saída para o prefixo 'comp' deve ser exatamente a da seção 2.2."""
        esperado = ["compilador", "complexidade", "computação",
                    "computacional", "computador"]
        self.assertEqual(self.trie.buscar_prefixo("comp"), esperado)

    def test_busca_exata(self):
        self.assertTrue(self.trie.buscar("computador"))
        self.assertTrue(self.trie.buscar("computação"))
        self.assertFalse(self.trie.buscar("computadores"))

    def test_prefixo_nao_e_palavra(self):
        """'comp' é caminho de outras palavras, mas não foi inserida."""
        self.assertFalse(self.trie.buscar("comp"))
        self.assertTrue(self.trie.buscar_prefixo("comp"))

    def test_busca_ignora_acento(self):
        self.assertTrue(self.trie.buscar("computacao"))
        self.assertTrue(self.trie.buscar("COMPUTAÇÃO"))

    def test_resultado_preserva_acento(self):
        self.assertIn("computação", self.trie.buscar_prefixo("computa"))

    def test_prefixo_inexistente(self):
        self.assertEqual(self.trie.buscar_prefixo("xyz"), [])

    def test_prefixo_vazio_devolve_tudo(self):
        self.assertEqual(len(self.trie.buscar_prefixo("")), len(EXEMPLO_ENUNCIADO))

    def test_limite_trunca(self):
        self.assertEqual(len(self.trie.buscar_prefixo("comp", limite=2)), 2)

    def test_contar_prefixo(self):
        self.assertEqual(self.trie.contar_prefixo("comp"), 5)
        self.assertEqual(self.trie.contar_prefixo("prog"), 1)
        self.assertEqual(self.trie.contar_prefixo("zzz"), 0)

    def test_insercao_repetida_nao_duplica(self):
        antes = len(self.trie)
        self.assertFalse(self.trie.inserir("computador"))
        self.assertEqual(len(self.trie), antes)

    def test_insercao_nova(self):
        self.assertTrue(self.trie.inserir("compressao"))
        self.assertTrue(self.trie.buscar("compressao"))

    def test_ignora_entrada_vazia(self):
        self.assertFalse(self.trie.inserir(""))
        self.assertFalse(self.trie.inserir("   "))

    def test_operador_in(self):
        self.assertIn("compilador", self.trie)
        self.assertNotIn("javascript", self.trie)

    def test_altura_e_maior_chave(self):
        self.assertEqual(self.trie.altura(), len("processamento"))

    def test_trie_vazia(self):
        vazia = Trie()
        self.assertEqual(len(vazia), 0)
        self.assertEqual(vazia.buscar_prefixo("a"), [])
        self.assertFalse(vazia.buscar("a"))


class TesteTrieComprimida(unittest.TestCase):

    def setUp(self):
        self.trie = Trie(EXEMPLO_ENUNCIADO)
        self.comprimida = TrieComprimida(EXEMPLO_ENUNCIADO)

    def test_mesmo_total_de_palavras(self):
        self.assertEqual(len(self.trie), len(self.comprimida))

    def test_usa_menos_nos(self):
        self.assertLess(self.comprimida.total_nos(), self.trie.total_nos())

    def test_exemplo_do_enunciado(self):
        esperado = ["compilador", "complexidade", "computação",
                    "computacional", "computador"]
        self.assertEqual(self.comprimida.buscar_prefixo("comp"), esperado)

    def test_busca_exata_igual_a_tradicional(self):
        for palavra in EXEMPLO_ENUNCIADO + ["comp", "xyz", "computadores"]:
            self.assertEqual(
                self.comprimida.buscar(palavra),
                self.trie.buscar(palavra),
                f"divergiram em '{palavra}'",
            )

    def test_equivalencia_com_palavras_aleatorias(self):
        """
        Duas implementações independentes precisam concordar em toda entrada.

        Gera vocabulários aleatórios com muitos prefixos compartilhados, que é
        onde a divisão de arestas da PATRICIA tem mais chance de errar.
        """
        random.seed(7)
        for _ in range(40):
            palavras = list({
                "".join(random.choice("abc") for _ in range(random.randint(1, 8)))
                for _ in range(random.randint(1, 40))
            })
            tradicional = Trie(palavras)
            comprimida = TrieComprimida(palavras)

            self.assertEqual(len(tradicional), len(comprimida))
            for prefixo in ["", "a", "b", "ab", "abc", "ca", "zzz"]:
                self.assertEqual(
                    tradicional.buscar_prefixo(prefixo),
                    comprimida.buscar_prefixo(prefixo),
                    f"prefixo '{prefixo}' divergiu em {sorted(palavras)}",
                )


class TesteStemmerRSLP(unittest.TestCase):

    def setUp(self):
        self.stemmer = RSLP()

    def test_caso_do_enunciado(self):
        """
        O exemplo da seção 3.7.1 digita 'algoritmo' e espera achar os textos
        que trazem 'algoritmos'. Só funciona se os dois derem o mesmo radical.
        """
        self.assertEqual(
            self.stemmer.radicalizar("algoritmo"),
            self.stemmer.radicalizar("algoritmos"),
        )

    def test_plural_conflata(self):
        for singular, plural in [("dado", "dados"), ("rede", "redes"),
                                 ("documento", "documentos"), ("chave", "chaves")]:
            self.assertEqual(
                self.stemmer.radicalizar(singular),
                self.stemmer.radicalizar(plural),
                f"'{singular}' e '{plural}' deveriam ter o mesmo radical",
            )

    def test_flexao_verbal_conflata(self):
        radicais = {self.stemmer.radicalizar(p)
                    for p in ["buscar", "buscando", "buscou", "buscas"]}
        self.assertEqual(len(radicais), 1)

    def test_radical_sem_acento(self):
        self.assertEqual(self.stemmer.radicalizar("informação"), "informac")

    def test_palavra_curta_intacta(self):
        self.assertEqual(self.stemmer.radicalizar("de"), "de")
        self.assertEqual(self.stemmer.radicalizar("é"), "e")

    def test_excecao_preservada(self):
        """'coração' está na lista de exceções: não pode virar 'corac'."""
        self.assertNotEqual(self.stemmer.radicalizar("coração"), "corac")

    def test_deterministico(self):
        for palavra in ["algoritmos", "computação", "programadores"]:
            self.assertEqual(
                self.stemmer.radicalizar(palavra),
                RSLP().radicalizar(palavra),
            )

    def test_cache_funciona(self):
        self.stemmer.radicalizar("algoritmos")
        antes = self.stemmer.acertos_cache
        self.stemmer.radicalizar("algoritmos")
        self.assertEqual(self.stemmer.acertos_cache, antes + 1)


class TestePreprocessamento(unittest.TestCase):

    def setUp(self):
        self.pre = Preprocessador()

    def test_exemplo_do_enunciado(self):
        """Seção 3.3: a entrada dada deve produzir exatamente esses tokens."""
        entrada = "Os Algoritmos de Busca são muito importantes."
        self.assertEqual(self.pre.processar(entrada),
                         ["algoritmos", "busca", "importantes"])

    def test_pontuacao_vira_separador(self):
        self.assertEqual(tokenizar(remover_pontuacao("banco-de-dados")),
                         ["banco", "de", "dados"])

    def test_numeros_descartados(self):
        self.assertEqual(tokenizar("versão 3 do x86"), ["versão", "do", "x"])

    def test_acentos_preservados_no_token(self):
        self.assertIn("índices", self.pre.processar("os índices são rápidos"))

    def test_texto_vazio(self):
        self.assertEqual(self.pre.processar(""), [])
        self.assertEqual(self.pre.processar("   ...   "), [])

    def test_stopwords_carregadas(self):
        self.assertGreater(len(self.pre.stopwords), 100)
        self.assertIn("de", self.pre.stopwords)

    def test_indexacao_e_consulta_usam_o_mesmo_radical(self):
        """Se os dois lados divergirem, nenhuma consulta encontra nada."""
        do_documento = self.pre.radicalizar(self.pre.processar("os algoritmos")[0])
        da_consulta = self.pre.radicalizar(self.pre.processar_consulta("Algoritmo")[0])
        self.assertEqual(do_documento, da_consulta)

    def test_sem_stemming_devolve_forma_normalizada(self):
        pre = Preprocessador(usar_stemming=False)
        self.assertEqual(pre.radicalizar("Computação"), "computacao")


class TesteKMP(unittest.TestCase):

    def test_tabela_falha_conhecida(self):
        self.assertEqual(tabela_falha("ababc"), [0, 0, 1, 2, 0])
        self.assertEqual(tabela_falha("aabaabaaa"), [0, 1, 0, 1, 2, 3, 4, 5, 2])
        self.assertEqual(tabela_falha("abcd"), [0, 0, 0, 0])
        self.assertEqual(tabela_falha("aaaa"), [0, 1, 2, 3])

    def test_encontra_todas_as_ocorrencias(self):
        self.assertEqual(buscar_kmp("xxabcxxabc", "abc").ocorrencias, [2, 7])

    def test_ocorrencias_sobrepostas(self):
        self.assertEqual(buscar_kmp("aaaa", "aa").ocorrencias, [0, 1, 2])

    def test_padrao_ausente(self):
        self.assertEqual(buscar_kmp("abcdef", "xyz").ocorrencias, [])

    def test_padrao_vazio(self):
        self.assertEqual(buscar_kmp("abc", "").ocorrencias, [])

    def test_padrao_maior_que_texto(self):
        self.assertEqual(buscar_kmp("ab", "abcdef").ocorrencias, [])

    def test_texto_igual_ao_padrao(self):
        self.assertEqual(buscar_kmp("abc", "abc").ocorrencias, [0])

    def test_primeira_apenas(self):
        self.assertEqual(buscar_kmp("aaaa", "aa", primeira_apenas=True).ocorrencias, [0])

    def test_equivalencia_com_busca_ingenua(self):
        """
        Teste de propriedade: KMP e força bruta são implementações
        independentes do mesmo problema e precisam concordar em toda entrada.
        """
        random.seed(123)
        for _ in range(2000):
            texto = "".join(random.choice("abc") for _ in range(random.randint(0, 50)))
            padrao = "".join(random.choice("abc") for _ in range(random.randint(1, 5)))
            self.assertEqual(
                buscar_kmp(texto, padrao).ocorrencias,
                buscar_ingenuo(texto, padrao).ocorrencias,
                f"divergiram em texto='{texto}' padrao='{padrao}'",
            )

    def test_custo_linear_no_pior_caso(self):
        """
        No pior caso o KMP faz O(n) comparações, e a busca ingênua O(n*m).

        A verificação é sobre o CRESCIMENTO: dobrando n, as comparações do KMP
        devem dobrar, mantendo a razão comparações/n praticamente constante.
        """
        razoes = []
        for n in (1000, 2000, 4000):
            resultado = buscar_kmp("a" * n, "a" * 50 + "b")
            razoes.append(resultado.comparacoes / n)

        self.assertLess(max(razoes) - min(razoes), 0.1)
        self.assertLess(max(razoes), 3.0)      # o limite teórico é 2n


class TesteTabelaHash(unittest.TestCase):

    def test_insercao_e_busca(self):
        tabela = TabelaHash(capacidade=16)
        tabela.inserir("algoritmo", 42)
        self.assertEqual(tabela.buscar("algoritmo"), 42)
        self.assertIsNone(tabela.buscar("inexistente"))

    def test_atualizacao_nao_conta_como_nova(self):
        tabela = TabelaHash(capacidade=16)
        self.assertTrue(tabela.inserir("x", 1))
        self.assertFalse(tabela.inserir("x", 2))
        self.assertEqual(tabela.buscar("x"), 2)
        self.assertEqual(len(tabela), 1)

    def test_redimensiona_ao_passar_da_carga(self):
        tabela = TabelaHash(capacidade=8)
        for i in range(200):
            tabela.inserir(f"chave{i}", i)
        self.assertGreater(tabela.capacidade, 8)
        self.assertLessEqual(tabela.n / tabela.capacidade, TabelaHash.CARGA_MAXIMA)

    def test_recupera_tudo_apos_redimensionar(self):
        tabela = TabelaHash(capacidade=8)
        for i in range(500):
            tabela.inserir(f"chave{i}", i)
        for i in range(500):
            self.assertEqual(tabela.buscar(f"chave{i}"), i)

    def test_hash_dentro_do_intervalo(self):
        tabela = TabelaHash(capacidade=64)
        for palavra in ["a", "casa", "caso", "algoritmo", "computação", ""]:
            self.assertTrue(0 <= tabela._hash(palavra) < 64)

    def test_colisoes_sao_contadas(self):
        tabela = TabelaHash(capacidade=4)
        tabela.CARGA_MAXIMA = 1e9        # desliga o redimensionamento
        for i in range(50):
            tabela.inserir(f"chave{i}", i)
        self.assertGreater(tabela.colisoes, 0)
        for i in range(50):
            self.assertEqual(tabela.buscar(f"chave{i}"), i)


class TesteIndiceInvertido(unittest.TestCase):

    def setUp(self):
        self.pre = Preprocessador()
        self.indice = IndiceInvertido()
        self.indice.indexar("d1.txt", ["algoritmo", "busca", "algoritmo"], self.pre)
        self.indice.indexar("d2.txt", ["busca", "dados"], self.pre)
        self.indice.indexar("d3.txt", ["algoritmos", "grafos"], self.pre)

    def test_termo_encontra_os_documentos(self):
        radical = self.pre.radicalizar("busca")
        self.assertEqual(set(self.indice.buscar(radical)), {"d1.txt", "d2.txt"})

    def test_frequencia_registrada(self):
        radical = self.pre.radicalizar("algoritmo")
        self.assertEqual(self.indice.buscar(radical)["d1.txt"], 2)

    def test_stemming_une_singular_e_plural(self):
        radical = self.pre.radicalizar("algoritmo")
        self.assertEqual(set(self.indice.buscar(radical)), {"d1.txt", "d3.txt"})

    def test_indice_exato_separa_as_formas(self):
        self.assertEqual(set(self.indice.buscar("algoritmo", usar_radical=False)),
                         {"d1.txt"})

    def test_termo_ausente(self):
        self.assertEqual(self.indice.buscar("inexistente"), {})
        self.assertEqual(self.indice.frequencia_documental("inexistente"), 0)

    def test_idf_nunca_negativo(self):
        """
        O '+1' dentro do logaritmo garante IDF >= 0 até para termos presentes
        em todos os documentos -- sem ele, um documento perderia pontos por
        conter o termo buscado.
        """
        for termo in self.indice.por_radical:
            self.assertGreaterEqual(self.indice._idf(termo), 0.0)

    def test_bm25_ordena_por_relevancia(self):
        radical = self.pre.radicalizar("algoritmo")
        ranking = self.indice.ranquear_bm25([radical])
        self.assertEqual(ranking[0][0], "d1.txt")    # 2 ocorrências contra 1
        self.assertEqual(len(ranking), 2)

    def test_bm25_de_consulta_ausente(self):
        self.assertEqual(self.indice.ranquear_bm25(["inexistente"]), [])

    def test_contagem_de_postagens(self):
        # busc: d1, d2 | algoritm: d1, d3 | dad: d2 | graf: d3
        self.assertEqual(self.indice.total_postagens(), 6)


class TesteMecanismoPontaAPonta(unittest.TestCase):
    """Monta um índice completo em uma pasta temporária."""

    @classmethod
    def setUpClass(cls):
        cls.pasta = Path(tempfile.mkdtemp(prefix="testes_a1_"))
        (cls.pasta / "algoritmos.txt").write_text(
            "Algoritmos de busca são fundamentais. Um algoritmo eficiente "
            "reduz o tempo de execução. Estruturas de dados complementam "
            "os algoritmos de ordenação.",
            encoding="utf-8",
        )
        (cls.pasta / "redes.txt").write_text(
            "Redes de computadores conectam máquinas. Uma rede local usa "
            "protocolos como TCP e IP para transmitir dados entre os hosts.",
            encoding="utf-8",
        )
        (cls.pasta / "banco_dados.txt").write_text(
            "Banco de dados relacional organiza dados em tabelas. Índices "
            "aceleram consultas. A busca por chave primária é imediata.",
            encoding="utf-8",
        )
        cls.mecanismo = MecanismoBusca(cls.pasta)
        cls.mecanismo.construir()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.pasta, ignore_errors=True)

    def test_descobriu_todos_os_arquivos(self):
        """Seção 3.2: os nomes não estão no código, a pasta é varrida."""
        self.assertEqual(self.mecanismo.estatisticas.documentos, 3)

    def test_arquivo_novo_entra_na_reconstrucao(self):
        """Soltar um .txt na pasta deve bastar para ele ser indexado."""
        novo = self.pasta / "extra.txt"
        novo.write_text("Compiladores traduzem código fonte.", encoding="utf-8")
        try:
            outro = MecanismoBusca(self.pasta)
            self.assertEqual(outro.construir(), 4)
            self.assertTrue(outro.buscar_palavra("compilador")["documentos"])
        finally:
            novo.unlink()

    def test_busca_exata_encontra(self):
        resposta = self.mecanismo.buscar_palavra("algoritmo")
        documentos = [d for d, _ in resposta["documentos"]]
        self.assertIn("algoritmos.txt", documentos)

    def test_stemming_amplia_a_cobertura(self):
        """'rede' no singular deve encontrar o texto que traz 'redes'."""
        resposta = self.mecanismo.buscar_palavra("rede")
        self.assertIn("redes.txt", [d for d, _ in resposta["documentos"]])

    def test_stopwords_fora_do_indice(self):
        self.assertEqual(self.mecanismo.buscar_palavra("de")["documentos"], [])

    def test_prefixo_integra_trie_e_indice(self):
        resposta = self.mecanismo.buscar_prefixo("algor")
        self.assertTrue(resposta["termos"])
        for termo in resposta["termos"]:
            self.assertIn("algoritmos.txt", resposta["por_termo"][termo])

    def test_kmp_acha_no_conteudo_original(self):
        """A busca por sequência alcança trechos que a tokenização descarta."""
        resposta = self.mecanismo.buscar_sequencia("chave primária")
        self.assertEqual(len(resposta["resultados"]), 1)
        self.assertEqual(resposta["resultados"][0]["documento"], "banco_dados.txt")

    def test_kmp_acha_fragmento_de_palavra(self):
        resposta = self.mecanismo.buscar_sequencia("ordena")
        self.assertTrue(resposta["total_ocorrencias"])

    def test_insercao_em_tempo_de_execucao(self):
        antes = len(self.mecanismo.trie)
        self.assertTrue(self.mecanismo.inserir_palavra("javascript"))
        self.assertEqual(len(self.mecanismo.trie), antes + 1)
        self.assertTrue(self.mecanismo.trie.buscar("javascript"))

    def test_estatisticas_obrigatorias_preenchidas(self):
        """As sete métricas da seção 3.9 precisam existir depois da construção."""
        e = self.mecanismo.estatisticas
        self.assertGreater(e.documentos, 0)
        self.assertGreater(e.total_palavras, 0)
        self.assertGreater(e.termos_distintos, 0)
        self.assertGreater(e.palavras_na_trie, 0)
        self.assertGreater(e.tempo_trie, 0)
        self.assertGreater(e.tempo_indice, 0)
        self.assertTrue(e.consultas)          # item 7: tempo de cada consulta

    def test_pasta_inexistente_nao_quebra(self):
        vazio = MecanismoBusca(self.pasta / "nao_existe")
        self.assertEqual(vazio.construir(), 0)

    def test_trie_comprimida_economiza_nos(self):
        e = self.mecanismo.estatisticas
        self.assertLess(e.nos_na_trie_comprimida, e.nos_na_trie)


# ==========================================================================
#  INTERFACE WEB
# ==========================================================================

class TesteServidorWeb(unittest.TestCase):
    """
    Sobe o servidor de verdade em uma porta livre e conversa com ele por HTTP.

    Não é teste de interface: a página é conferida no navegador. O que se
    verifica aqui é o contrato entre as duas pontas -- que cada rota devolve o
    que a página espera, que uma consulta vazia é recusada e que nenhum pedido
    consegue ler arquivo de fora da pasta `web/`.
    """

    @classmethod
    def setUpClass(cls):
        cls.raiz = Path(tempfile.mkdtemp(prefix="testes_web_a1_"))

        # O léxico fica FORA da pasta de documentos: o mecanismo indexa todo
        # .txt que encontrar, e um léxico solto ali viraria um documento.
        cls.pasta = cls.raiz / "documentos"
        cls.pasta.mkdir()
        (cls.pasta / "grafos.txt").write_text(
            "Grafos modelam relações entre objetos. Um grafo dirigido tem "
            "arestas com sentido. A busca em largura percorre o grafo por "
            "níveis.",
            encoding="utf-8",
        )
        lexico = cls.raiz / "lexico.txt"
        lexico.write_text(
            "# lexico de teste\ncomputador\ncomputação\ncompilador\ngrafo\n",
            encoding="utf-8",
        )

        cls.aplicacao = Aplicacao(pasta=cls.pasta, lexico=lexico)
        # Porta 0: o sistema escolhe uma livre, então dois testes simultâneos
        # nunca disputam o mesmo número.
        cls.servidor = criar_servidor(cls.aplicacao, porta=0, silencioso=True)
        cls.porta = cls.servidor.server_address[1]
        cls.thread = threading.Thread(target=cls.servidor.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.servidor.shutdown()
        cls.servidor.server_close()
        cls.thread.join(timeout=5)
        shutil.rmtree(cls.raiz, ignore_errors=True)

    # ------------------------------------------------------------- auxílio

    def obter(self, caminho, **parametros):
        """GET em uma rota, devolvendo o JSON já decodificado."""
        if parametros:
            caminho += "?" + urllib.parse.urlencode(parametros)
        endereco = f"http://127.0.0.1:{self.porta}{caminho}"
        with urllib.request.urlopen(endereco, timeout=10) as resposta:
            return json.loads(resposta.read().decode("utf-8"))

    def codigo_de(self, caminho):
        """Código HTTP de uma rota que se espera recusada."""
        endereco = f"http://127.0.0.1:{self.porta}{caminho}"
        try:
            urllib.request.urlopen(endereco, timeout=10)
        except urllib.error.HTTPError as falha:
            return falha.code
        return 200

    # -------------------------------------------------------------- rotas

    # Os testes desta classe compartilham um servidor só, e um deles insere uma
    # palavra nova. Por isso as contagens são verificadas como "pelo menos" ou
    # em relação ao estado do momento -- nunca como um número fixo que a ordem
    # de execução poderia mudar.

    def test_estado_traz_os_dois_lados(self):
        estado = self.obter("/api/estado")
        self.assertGreaterEqual(estado["parte1"]["palavras"], 4)
        self.assertEqual(estado["parte2"]["documentos"], 1)
        self.assertGreater(estado["parte2"]["termos"], 0)

    def test_prefixo_do_lexico(self):
        resposta = self.obter("/api/parte1/prefixo", q="comp")
        self.assertGreaterEqual(resposta["total"], 3)
        for palavra in ("compilador", "computador", "computação"):
            self.assertIn(palavra, resposta["palavras"])
        self.assertGreater(resposta["tempo"], 0)

    def test_limite_trunca_e_avisa(self):
        resposta = self.obter("/api/parte1/prefixo", q="comp", limite=1)
        self.assertEqual(len(resposta["palavras"]), 1)
        self.assertTrue(resposta["truncado"])

    def test_palavra_do_lexico_distingue_prefixo_de_palavra(self):
        """'comp' é caminho na Trie, mas não é palavra; 'grafo' é as duas coisas."""
        caminho = self.obter("/api/parte1/palavra", q="comp")
        self.assertFalse(caminho["existe"])
        self.assertGreaterEqual(caminho["continuacoes"], 3)

        palavra = self.obter("/api/parte1/palavra", q="grafo")
        self.assertTrue(palavra["existe"])
        self.assertEqual(palavra["formas"], ["grafo"])

    def test_insercao_em_tempo_de_execucao(self):
        antes = self.obter("/api/estado")["parte1"]["palavras"]
        endereco = f"http://127.0.0.1:{self.porta}/api/parte1/inserir"
        requisicao = urllib.request.Request(
            endereco,
            data=json.dumps({"palavra": "computaria"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(requisicao, timeout=10) as resposta:
            dados = json.loads(resposta.read().decode("utf-8"))

        self.assertTrue(dados["nova"])
        self.assertEqual(dados["palavras"], antes + 1)
        self.assertIn("computaria", self.obter("/api/parte1/prefixo", q="comp")["palavras"])

    def test_busca_por_palavra_devolve_ranqueamento(self):
        resposta = self.obter("/api/parte2/palavra", q="grafo")
        self.assertEqual(len(resposta["documentos"]), 1)
        documento, pontuacao = resposta["documentos"][0]
        self.assertEqual(documento, "grafos.txt")
        self.assertGreater(pontuacao, 0)

    def test_busca_por_sequencia_conta_comparacoes(self):
        resposta = self.obter("/api/parte2/sequencia", q="busca em largura")
        self.assertEqual(resposta["total_ocorrencias"], 1)
        self.assertGreater(resposta["comparacoes"], 0)
        self.assertIn("busca em largura", resposta["resultados"][0]["contextos"][0])

    def test_estatisticas_trazem_as_metricas_obrigatorias(self):
        estatisticas = self.obter("/api/estatisticas")
        self.assertGreater(estatisticas["corpus"]["documentos"], 0)
        self.assertGreater(estatisticas["corpus"]["postagens"], 0)
        self.assertIn("total", estatisticas["construcao"])
        self.assertIn("fator de carga", estatisticas["hash"])

    # --------------------------------------------------------- recusas

    def test_consulta_vazia_e_recusada(self):
        self.assertEqual(self.codigo_de("/api/parte2/palavra"), 400)

    def test_rota_inexistente_e_404(self):
        self.assertEqual(self.codigo_de("/api/nao/existe"), 404)

    def test_pagina_e_servida(self):
        endereco = f"http://127.0.0.1:{self.porta}/"
        with urllib.request.urlopen(endereco, timeout=10) as resposta:
            corpo = resposta.read().decode("utf-8")
        self.assertEqual(resposta.status, 200)
        self.assertIn("<title>", corpo)

    def test_nao_serve_arquivo_fora_da_pasta_web(self):
        """
        `urllib` normalizaria o caminho antes de enviar, escondendo o ataque;
        por isso o pedido é montado na mão, com os `..` intactos.
        """
        conexao = http.client.HTTPConnection("127.0.0.1", self.porta, timeout=10)
        conexao.request("GET", "/../palavras.txt")
        resposta = conexao.getresponse()
        resposta.read()
        conexao.close()
        self.assertEqual(resposta.status, 403)


if __name__ == "__main__":
    unittest.main(verbosity=2)
