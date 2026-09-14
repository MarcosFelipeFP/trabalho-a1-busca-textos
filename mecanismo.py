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
from trie import Trie, TrieComprimida, normalizar

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

        # A versão em caixa baixa é calculada UMA vez, na indexação, e não a
        # cada consulta. A busca por sequência é insensível a maiúsculas, e
        # baixar a caixa dos 24 documentos custa O(N) — fazer isso dentro da
        # consulta significava pagar esse O(N) de novo a cada tecla digitada,
        # trabalho que chegava a superar o do próprio KMP.
        self.conteudo_minusculo = {}

        self.vocabulario = set()
        self.frequencia = {}      # token -> ocorrências no corpus inteiro

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
                self.conteudo_minusculo[arquivo.name] = texto.lower()

            with Cronometro() as relogio:
                brutos, tokens = self.preprocessador.processar_detalhado(texto)
            self.estatisticas.tempo_preprocessamento += relogio.decorrido

            tokens_por_documento[arquivo.name] = tokens
            self.estatisticas.total_palavras_brutas += len(brutos)
            self.estatisticas.total_palavras += len(tokens)
            self.vocabulario.update(tokens)

            # Contagem de frequência na mesma passada dos tokens: O(t), e é ela
            # que dá ao autocomplete o critério de relevância.
            for token in tokens:
                self.frequencia[token] = self.frequencia.get(token, 0) + 1

        # --- fase 3: construção da Trie a partir do vocabulário ---
        # Ordenar antes de inserir mantém o resultado determinístico e permite
        # repetir a medição de tempo em condições idênticas.
        vocabulario_ordenado = sorted(self.vocabulario)

        # Duas grafias diferentes ("computação" e "computacao") viram a mesma
        # chave na Trie; os pesos delas precisam somar, não competir. O peso de
        # cada palavra fica pronto ANTES do cronômetro: normalizar a chave para
        # consultar a soma não é trabalho da Trie e não deve entrar no tempo
        # de construção dela.
        peso_da_chave = {}
        for token, ocorrencias in self.frequencia.items():
            chave = normalizar(token)
            peso_da_chave[chave] = peso_da_chave.get(chave, 0) + ocorrencias
        pesos = [peso_da_chave.get(normalizar(palavra), 1) for palavra in vocabulario_ordenado]

        with Cronometro() as relogio:
            for palavra, peso in zip(vocabulario_ordenado, pesos):
                self.trie.inserir(palavra, peso=peso)
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

    def buscar_palavra(self, consulta, ranquear=True):
        """
        Consulta por palavra (seção 3.7.1), com um ou mais termos.

        Cada palavra digitada passa pelo MESMO pré-processamento aplicado aos
        documentos e vira um radical; o radical é a chave consultada no índice.
        É o que permite "algoritmo" encontrar as ocorrências de "algoritmos".

        Com vários termos ("rede neural"), cada um é uma consulta O(1) ao
        índice, e os resultados são combinados em duas leituras:

          * `documentos` -- todo documento que contém ALGUM termo, ordenado
            primeiro pelo número de termos que contém e depois pelo BM25 da
            consulta inteira. Quem tem as duas palavras vem antes de quem tem
            muitas ocorrências de uma só;
          * `todos` -- só os que contêm TODOS os termos. A interseção começa
            pela menor lista de documentos e testa cada um nas demais, O(1) por
            teste: custa O(q·d_min), limitado pelo termo mais raro, e não pelo
            mais comum.

        Termo que não aparece em documento nenhum ganha sugestões por distância
        de edição, buscadas na Trie do vocabulário (`Trie.buscar_aproximado`).
        Essa busca só roda quando falta resultado e é cronometrada à parte, em
        `tempo_aproximacao`, para não misturar o custo do "você quis dizer" com
        o da consulta ao índice.

        Complexidade: O(q) consultas O(1) ao índice, mais O(d log d) para
        ordenar os d documentos encontrados.
        """
        with Cronometro() as relogio:
            termos, ignorados = self.preprocessador.termos_da_consulta(consulta)

            detalhes = []       # um por radical distinto, na ordem digitada
            postagens = []      # (radical, {documento: frequência})
            vistos = set()
            for termo in termos:
                radical = self.preprocessador.radicalizar(termo)
                if radical in vistos:
                    continue    # "algoritmo algoritmos" é um termo só
                vistos.add(radical)
                postagem = self.indice.buscar(radical, usar_radical=True)
                exatos = self.indice.frequencia_documental(termo.lower(), usar_radical=False)
                postagens.append((radical, postagem))
                detalhes.append({"termo": termo, "radical": radical,
                                 "documentos": len(postagem), "exatos": exatos})

            cobertura = {}      # documento -> quantos termos da consulta contém
            frequencias = {}    # documento -> ocorrências somadas dos termos
            for _radical, postagem in postagens:
                for documento, frequencia in postagem.items():
                    cobertura[documento] = cobertura.get(documento, 0) + 1
                    frequencias[documento] = frequencias.get(documento, 0) + frequencia

            # Interseção a partir da menor postagem.
            listas = sorted((postagem for _r, postagem in postagens), key=len)
            if listas and listas[0]:
                todos = sorted(documento for documento in listas[0]
                               if all(documento in outra for outra in listas[1:]))
            else:
                todos = []

            pontuacao = {}
            if ranquear and cobertura:
                pontuacao = dict(self.indice.ranquear_bm25([r for r, _p in postagens]))
            documentos = sorted(
                ((documento, pontuacao.get(documento, 0.0)) for documento in cobertura),
                key=lambda par: (-cobertura[par[0]], -par[1], par[0]),
            )

        with Cronometro() as relogio_aproximacao:
            aproximadas = {}
            for detalhe in detalhes:
                if detalhe["documentos"] == 0:
                    aproximadas[detalhe["termo"]] = self.sugerir_correcao(detalhe["termo"])

        # A consulta corrigida troca cada termo sem resultado pela sugestão mais
        # próxima e mantém as demais palavras -- inclusive as stopwords -- no
        # lugar em que foram digitadas.
        correcao = None
        if any(aproximadas.values()):
            brutos = self.preprocessador.processar_consulta(consulta)
            correcao = " ".join(
                aproximadas[token][0][0] if aproximadas.get(token) else token
                for token in brutos
            )

        primeiro = detalhes[0] if detalhes else None
        resposta = {
            "consulta": consulta,
            "termo": primeiro["termo"] if primeiro else consulta,
            "radical": primeiro["radical"] if primeiro else None,
            "termos": detalhes,
            "ignorados": ignorados,
            "documentos": documentos,
            "frequencias": frequencias,
            "cobertura": cobertura,
            "todos": todos,
            "aproximadas": aproximadas,
            "correcao": correcao,
            "tempo": relogio.decorrido,
            "tempo_aproximacao": relogio_aproximacao.decorrido,
        }
        self.estatisticas.registrar_consulta(
            "palavra", consulta, len(documentos), relogio.decorrido
        )
        return resposta

    def sugerir_correcao(self, termo, limite=5):
        """
        Palavras do vocabulário parecidas com `termo`, para o "você quis dizer?".

        Só entram sugestões que de fato levam a algum documento -- uma palavra
        inserida em tempo de execução está na Trie, mas não no índice -- e que
        não são o próprio termo. Devolve trios (palavra, distância, frequência).
        """
        sugestoes = []
        for palavra, distancia, peso in self.trie.buscar_aproximado(termo, limite=None):
            if distancia == 0:
                continue
            if not self.indice.frequencia_documental(self.preprocessador.radicalizar(palavra)):
                continue
            sugestoes.append((palavra, distancia, peso))
            if len(sugestoes) >= limite:
                break
        return sugestoes

    # ------------------------------------------------------- consulta prefixo

    def buscar_prefixo(self, prefixo, limite=50):
        """
        Consulta por prefixo (seção 3.7.2): a integração Trie + índice.

        Duas etapas encadeadas:
          1. a Trie devolve os termos do vocabulário que começam com o prefixo;
          2. para cada termo, o índice invertido informa em que documentos ele
             aparece.

        Além da lista alfabética exigida pelo enunciado, a resposta traz as
        `sugestoes`: as palavras mais frequentes no corpus que começam com o
        prefixo, obtidas pela busca best-first da Trie. É a ordem que um
        autocomplete de verdade usaria, e ela não custa a varredura da
        subárvore — ver `Trie.sugerir`.

        Devolve os termos, o mapa termo -> documentos, os documentos reunidos e
        o tempo. Complexidade: O(m + p) na Trie, mais O(1) por termo no índice.
        """
        with Cronometro() as relogio:
            termos = self.trie.buscar_prefixo(prefixo, limite=limite)
            total_disponivel = self.trie.contar_prefixo(prefixo)
            sugestoes = self.trie.sugerir(prefixo, limite=10)

            por_termo = {}
            documentos = set()
            radicais = set()
            for termo in termos:
                # O radical é calculado uma única vez por termo e reaproveitado
                # no ranqueamento; o stemmer é a etapa mais cara do pipeline.
                radical = self.preprocessador.radicalizar(termo)
                radicais.add(radical)
                encontrados = self.indice.buscar(radical, usar_radical=True)
                por_termo[termo] = sorted(encontrados)
                documentos.update(encontrados)

            ranking = self.indice.ranquear_bm25(sorted(radicais)) if radicais else []

        resposta = {
            "prefixo": prefixo,
            "termos": termos,
            "sugestoes": sugestoes,
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

        A normalização de caixa foi movida para a indexação: a consulta já
        encontra o texto em caixa baixa pronto. Antes ela refazia `texto.lower()`
        nos 24 documentos a cada busca -- um O(N) extra, com alocação de string
        nova, que na prática pesava mais que a varredura do próprio KMP.
        """
        with Cronometro() as relogio:
            padrao = sequencia if not ignorar_caixa else sequencia.lower()
            resultados = []
            total_ocorrencias = 0
            total_comparacoes = 0

            for documento in sorted(self.conteudo):
                texto = self.conteudo[documento]
                # Sem recalcular: a cópia em caixa baixa foi feita na indexação.
                alvo = self.conteudo_minusculo[documento] if ignorar_caixa else texto

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
