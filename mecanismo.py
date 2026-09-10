"""
mecanismo.py
------------
Integra todas as peças da Parte II em um mecanismo de busca sobre arquivos
.txt: varredura automática da pasta, pré-processamento, vocabulário, Trie,
índice invertido e as três modalidades de consulta.

--------------------------------------------------------------------------
O caminho de uma consulta
--------------------------------------------------------------------------
    palavra exata   consulta -> RSLP -> radical -> índice (hash) -> documentos
                    O(1) em média

    prefixo         prefixo -> Trie -> termos do vocabulário -> RSLP ->
                    índice (hash) -> documentos
                    O(m + p) na Trie, mais O(1) por termo recuperado

    sequência       padrão -> KMP sobre o texto ORIGINAL de cada documento
                    O(n + m) por documento

A terceira difere das outras em natureza: não passa pelo índice. Ela varre o
conteúdo bruto, por isso encontra trechos que a indexação descarta -- pedaços
de palavra, pontuação, números -- ao custo de ser linear no tamanho do corpus,
e não constante.
"""

from pathlib import Path

from estatisticas import Cronometro, Estatisticas
from indice_invertido import IndiceInvertido
from kmp import buscar_kmp, contexto_da_ocorrencia
from preprocessamento import Preprocessador
from trie import Trie, TrieComprimida

__all__ = ["MecanismoBusca"]


class MecanismoBusca:
    """
    Mecanismo de busca sobre uma pasta de arquivos .txt.

    A pasta é varrida a cada execução com `Path.glob("*.txt")`: nenhum nome de
    arquivo aparece no código, e basta soltar um .txt novo na pasta para que
    ele entre no índice na próxima execução -- o que a seção 3.2 do enunciado
    exige explicitamente.
    """

    def __init__(self, pasta="documentos", usar_stemming=True, guardar_conteudo=True):
        self.pasta = Path(pasta)
        self.preprocessador = Preprocessador(usar_stemming=usar_stemming)
        self.indice = IndiceInvertido()
        self.trie = Trie()                    # vocabulário para o autocomplete
        self.trie_comprimida = TrieComprimida()  # mesma coisa, para comparação
        self.estatisticas = Estatisticas()

        # O texto original de cada documento fica em memória porque a busca por
        # sequência (KMP) trabalha sobre o conteúdo bruto, não sobre os tokens.
        # Para corpora grandes valeria reler o arquivo a cada consulta e trocar
        # memória por tempo de E/S.
        self.guardar_conteudo = guardar_conteudo
        self.conteudo = {}

        self.vocabulario = set()

    # ------------------------------------------------------------- construção

    def listar_arquivos(self):
        """
        Todos os .txt da pasta, em ordem alfabética.

        A ordenação não é estética: garante que duas execuções sobre a mesma
        pasta produzam exatamente o mesmo índice, o que torna as medições de
        tempo comparáveis entre si.
        """
        if not self.pasta.is_dir():
            return []
        return sorted(self.pasta.glob("*.txt"))

    def construir(self, ao_progredir=None):
        """
        Executa o pipeline completo, cronometrando cada fase separadamente.

        `ao_progredir` é um callback opcional (nome, indice, total) para a
        interface mostrar o andamento em corpora grandes.

        Devolve o número de documentos indexados.
        Complexidade total: O(N + V*m), com N = total de tokens do corpus,
        V = tamanho do vocabulário e m = tamanho médio das palavras.
        """
        arquivos = self.listar_arquivos()
        if not arquivos:
            return 0

        tokens_por_documento = {}

        # --- fases 1 e 2: leitura e pré-processamento ---
        for posicao, arquivo in enumerate(arquivos, start=1):
            if ao_progredir:
                ao_progredir(arquivo.name, posicao, len(arquivos))

            with Cronometro() as relogio:
                texto = arquivo.read_text(encoding="utf-8", errors="replace")
            self.estatisticas.tempo_leitura += relogio.decorrido

            if self.guardar_conteudo:
                self.conteudo[arquivo.name] = texto

            with Cronometro() as relogio:
                brutos, tokens = self.preprocessador.processar_detalhado(texto)
            self.estatisticas.tempo_preprocessamento += relogio.decorrido

            tokens_por_documento[arquivo.name] = tokens
            self.estatisticas.total_palavras_brutas += len(brutos)
            self.estatisticas.total_palavras += len(tokens)
            self.vocabulario.update(tokens)

        # --- fase 3: construção da Trie a partir do vocabulário ---
        # Ordenar antes de inserir mantém o resultado determinístico e permite
        # repetir a medição de tempo em condições idênticas.
        vocabulario_ordenado = sorted(self.vocabulario)

        with Cronometro() as relogio:
            for palavra in vocabulario_ordenado:
                self.trie.inserir(palavra)
        self.estatisticas.tempo_trie = relogio.decorrido

        for palavra in vocabulario_ordenado:
            self.trie_comprimida.inserir(palavra)

        # --- fase 4: construção do índice invertido ---
        with Cronometro() as relogio:
            for documento, tokens in tokens_por_documento.items():
                self.indice.indexar(documento, tokens, self.preprocessador)
        self.estatisticas.tempo_indice = relogio.decorrido

        # --- métricas finais ---
        self.estatisticas.documentos = len(arquivos)
        self.estatisticas.termos_distintos = len(self.vocabulario)
        self.estatisticas.palavras_na_trie = len(self.trie)
        self.estatisticas.nos_na_trie = self.trie.total_nos()
        self.estatisticas.nos_na_trie_comprimida = self.trie_comprimida.total_nos()
        self.estatisticas.postagens = self.indice.total_postagens()

        return len(arquivos)

    # --------------------------------------------------------- consulta exata

    def buscar_palavra(self, palavra, ranquear=True):
        """
        Consulta por palavra exata (seção 3.7.1).

        A palavra digitada passa pelo MESMO pré-processamento aplicado aos
        documentos e vira um radical; esse radical é a chave consultada no
        índice. É o que permite "algoritmo" encontrar as ocorrências de
        "algoritmos" nos textos.

        Devolve um dicionário com os documentos, a pontuação BM25 e o tempo.
        Complexidade: O(1) em média para a consulta ao índice, mais O(d log d)
        para ordenar os d documentos encontrados.
        """
        with Cronometro() as relogio:
            tokens = self.preprocessador.processar_consulta(palavra)
            if not tokens:
                resposta = {"termo": palavra, "radical": None, "documentos": [],
                            "frequencias": {}, "exatos": {}}
            else:
                radical = self.preprocessador.radicalizar(tokens[0])
                frequencias = self.indice.buscar(radical, usar_radical=True)
                exatos = self.indice.buscar(tokens[0].lower(), usar_radical=False)

                if ranquear and frequencias:
                    ordenados = self.indice.ranquear_bm25([radical])
                else:
                    ordenados = [(documento, 0.0) for documento in sorted(frequencias)]

                resposta = {
                    "termo": tokens[0],
                    "radical": radical,
                    "documentos": ordenados,
                    "frequencias": frequencias,
                    "exatos": exatos,
                }

        resposta["tempo"] = relogio.decorrido
        self.estatisticas.registrar_consulta(
            "palavra", palavra, len(resposta["documentos"]), relogio.decorrido
        )
        return resposta

    # ------------------------------------------------------- consulta prefixo

    def buscar_prefixo(self, prefixo, limite=50):
        """
        Consulta por prefixo (seção 3.7.2): a integração Trie + índice.

        Duas etapas encadeadas:
          1. a Trie devolve os termos do vocabulário que começam com o prefixo;
          2. para cada termo, o índice invertido informa em que documentos ele
             aparece.

        Devolve os termos, o mapa termo -> documentos, os documentos reunidos e
        o tempo. Complexidade: O(m + p) na Trie, mais O(1) por termo no índice.
        """
        with Cronometro() as relogio:
            termos = self.trie.buscar_prefixo(prefixo, limite=limite)
            total_disponivel = self.trie.contar_prefixo(prefixo)

            por_termo = {}
            documentos = set()
            for termo in termos:
                radical = self.preprocessador.radicalizar(termo)
                encontrados = self.indice.buscar(radical, usar_radical=True)
                por_termo[termo] = sorted(encontrados)
                documentos.update(encontrados)

            radicais = {self.preprocessador.radicalizar(t) for t in termos}
            ranking = self.indice.ranquear_bm25(sorted(radicais)) if radicais else []

        resposta = {
            "prefixo": prefixo,
            "termos": termos,
            "total_disponivel": total_disponivel,
            "truncado": total_disponivel > len(termos),
            "por_termo": por_termo,
            "documentos": sorted(documentos),
            "ranking": ranking,
            "tempo": relogio.decorrido,
        }
        self.estatisticas.registrar_consulta(
            "prefixo", prefixo, len(termos), relogio.decorrido
        )
        return resposta

    # ----------------------------------------------------- consulta sequência

    def buscar_sequencia(self, sequencia, ignorar_caixa=True, max_contextos=3):
        """
        Consulta por sequência de caracteres com KMP (seção 3.7.3, opcional).

        Procura o padrão diretamente no conteúdo ORIGINAL dos documentos, sem
        passar por tokenização nem índice. Por isso encontra o que a indexação
        não alcança: fragmentos de palavra, expressões com pontuação, trechos
        no meio de um termo.

        Complexidade: O(n + m) por documento, portanto O(N + D*m) no corpus
        inteiro -- linear, mas sem o O(1) que o índice oferece. É o preço de
        não depender de estrutura pré-construída.
        """
        with Cronometro() as relogio:
            padrao = sequencia if not ignorar_caixa else sequencia.lower()
            resultados = []
            total_ocorrencias = 0
            total_comparacoes = 0

            for documento in sorted(self.conteudo):
                texto = self.conteudo[documento]
                alvo = texto.lower() if ignorar_caixa else texto

                encontrado = buscar_kmp(alvo, padrao)
                total_comparacoes += encontrado.comparacoes
                if not encontrado.ocorrencias:
                    continue

                total_ocorrencias += len(encontrado.ocorrencias)
                contextos = [
                    contexto_da_ocorrencia(texto, posicao, len(padrao))
                    for posicao in encontrado.ocorrencias[:max_contextos]
                ]
                resultados.append({
                    "documento": documento,
                    "ocorrencias": len(encontrado.ocorrencias),
                    "posicoes": encontrado.ocorrencias,
                    "contextos": contextos,
                })

            resultados.sort(key=lambda item: (-item["ocorrencias"], item["documento"]))

        resposta = {
            "sequencia": sequencia,
            "resultados": resultados,
            "total_ocorrencias": total_ocorrencias,
            "comparacoes": total_comparacoes,
            "tempo": relogio.decorrido,
        }
        self.estatisticas.registrar_consulta(
            "sequencia", sequencia, len(resultados), relogio.decorrido
        )
        return resposta

    # ---------------------------------------------------------------- apoio

    def inserir_palavra(self, palavra):
        """
        Insere uma palavra nova no vocabulário e na Trie durante a execução.

        Atende ao requisito de inserção em tempo de execução da Parte I. A
        palavra passa a valer para o autocomplete, mas não ganha documentos no
        índice invertido -- ela não foi encontrada em nenhum arquivo.
        """
        nova = self.trie.inserir(palavra)
        self.trie_comprimida.inserir(palavra)
        if nova:
            self.vocabulario.add(palavra.strip())
            self.estatisticas.palavras_na_trie = len(self.trie)
            self.estatisticas.nos_na_trie = self.trie.total_nos()
            self.estatisticas.termos_distintos = len(self.vocabulario)
        return nova

    def resumo_documentos(self):
        """Nome, tamanho em bytes e total de tokens indexados de cada documento."""
        linhas = []
        for arquivo in self.listar_arquivos():
            linhas.append({
                "documento": arquivo.name,
                "bytes": arquivo.stat().st_size,
                "tokens": self.indice.tamanho_documento.get(arquivo.name, 0),
            })
        return linhas
