"""
indice_invertido.py
-------------------
Índice invertido, tabela hash didática e ranqueamento BM25.

--------------------------------------------------------------------------
Por que "invertido"
--------------------------------------------------------------------------
O índice natural de uma coleção de textos é o índice DIRETO: documento ->
lista de palavras que ele contém. É assim que o arquivo está gravado no disco.
Responder "em quais arquivos aparece a palavra X" com esse índice obriga a
abrir e varrer todos os documentos, custo O(N * n).

O índice INVERTIDO troca o papel de chave e valor: palavra -> lista de
documentos em que ela ocorre. A relação é a mesma, lida na direção oposta --
daí o nome. Com ele a mesma pergunta vira uma única consulta a tabela hash,
O(1) em média, independentemente do tamanho da coleção.

    índice direto      algoritmos.txt -> {algoritmo, busca, dados, ...}
    índice invertido   algoritmo      -> {algoritmos.txt, complexidade.txt}

É a estrutura central de todo motor de busca desde os anos 1960, e continua
sendo o que Lucene, Elasticsearch e Solr usam por baixo.

--------------------------------------------------------------------------
Ranqueamento: TF-IDF e BM25
--------------------------------------------------------------------------
O índice responde QUAIS documentos contêm o termo, mas não em que ORDEM
apresentá-los. Duas funções clássicas de pontuação são implementadas aqui:

  * TF-IDF -- Spärck Jones, K. "A statistical interpretation of term
    specificity and its application in retrieval". Journal of Documentation,
    28(1):11-21, 1972. A ideia de que um termo raro na coleção é mais
    informativo que um termo comum.

  * BM25 (Okapi BM25) -- Robertson, S. E. et al. "Okapi at TREC-3".
    In: Proceedings of the Third Text REtrieval Conference (TREC-3), 1994;
    formalizado em Robertson, S. E.; Zaragoza, H. "The Probabilistic Relevance
    Framework: BM25 and Beyond". Foundations and Trends in Information
    Retrieval, 3(4):333-389, 2009.

O BM25 corrige duas fraquezas do TF-IDF puro: satura a frequência do termo
(a décima ocorrência de uma palavra vale muito menos que a segunda) e
normaliza pelo tamanho do documento, para que textos longos não dominem o
ranking só por serem longos. Trinta anos depois ele segue sendo a linha de
base obrigatória contra a qual todo modelo neural de recuperação é comparado
-- o benchmark BEIR (Thakur et al., NeurIPS 2021) mostrou o BM25 superando
vários modelos densos em cenários fora do domínio de treino.
"""

import math

__all__ = ["TabelaHash", "IndiceInvertido"]


# ==========================================================================
#  TABELA HASH DIDÁTICA
# ==========================================================================

class TabelaHash:
    """
    Tabela hash com tratamento de colisão por encadeamento separado.

    O sistema em produção usa o `dict` do Python, como o enunciado autoriza.
    Esta classe existe para tornar visível o que o `dict` faz por baixo e para
    permitir MEDIR o fenômeno das colisões, em vez de apenas descrevê-lo no
    relatório.

    --- Função hash ---
    Uma função hash mapeia uma chave de tamanho arbitrário para um inteiro em
    um intervalo fixo [0, capacidade). Aqui usa-se a hash polinomial (também
    chamada de hash de Horner), a mesma família empregada em `String.hashCode`
    do Java:

        h(s) = (s[0]*B^(m-1) + s[1]*B^(m-2) + ... + s[m-1]) mod C

    A base B é um primo ímpar, o que espalha bem cadeias parecidas: "casa" e
    "caso" caem em posições distantes, apesar de diferirem em uma letra.

    --- Colisões ---
    Como o conjunto de chaves possíveis é infinito e o de posições é finito,
    duas chaves distintas inevitavelmente vão para a mesma posição. Isso é uma
    colisão, e ela não é um defeito da função: é uma consequência do princípio
    da casa dos pombos. O que se pode fazer é tratá-la bem. A estratégia aqui
    é o encadeamento separado: cada posição guarda uma lista de pares
    (chave, valor) e a busca percorre essa lista.

    --- Complexidade ---
    Com função hash de boa dispersão e fator de carga α = n/C mantido baixo, o
    comprimento médio das listas é α, e a busca é O(1 + α) = O(1) em média. No
    pior caso -- todas as chaves colidindo na mesma posição -- a tabela
    degenera em lista ligada e a busca vira O(n). É para evitar esse cenário
    que a tabela redimensiona quando α ultrapassa o limite.
    """

    BASE = 31          # base primária da hash polinomial
    CARGA_MAXIMA = 0.75

    def __init__(self, capacidade=1024):
        self.capacidade = capacidade
        self.baldes = [[] for _ in range(capacidade)]
        self.n = 0
        self.colisoes = 0          # inserções que caíram em balde já ocupado
        self.sondagens = 0         # comparações feitas dentro dos baldes

    def _hash(self, chave):
        """
        Hash polinomial avaliada pelo esquema de Horner.

        O `& 0xFFFFFFFF` mantém o acumulador em 32 bits: sem isso o Python
        cresceria o inteiro indefinidamente e a operação deixaria de ser O(1)
        por caractere.

        Complexidade: O(m), no tamanho da chave.
        """
        h = 0
        for caractere in chave:
            h = (h * self.BASE + ord(caractere)) & 0xFFFFFFFF
        return h % self.capacidade

    def inserir(self, chave, valor):
        """Insere ou atualiza uma chave. O(1) em média."""
        indice = self._hash(chave)
        balde = self.baldes[indice]

        for posicao, (chave_atual, _) in enumerate(balde):
            self.sondagens += 1
            if chave_atual == chave:
                balde[posicao] = (chave, valor)
                return False

        if balde:                      # já havia algo aqui: houve colisão
            self.colisoes += 1
        balde.append((chave, valor))
        self.n += 1

        if self.n / self.capacidade > self.CARGA_MAXIMA:
            self._redimensionar()
        return True

    def buscar(self, chave, padrao=None):
        """Recupera o valor associado à chave. O(1) em média, O(n) no pior caso."""
        balde = self.baldes[self._hash(chave)]
        for chave_atual, valor in balde:
            self.sondagens += 1
            if chave_atual == chave:
                return valor
        return padrao

    def _redimensionar(self):
        """
        Dobra a capacidade e reinsere tudo.

        A operação custa O(n), mas acontece cada vez mais raramente conforme a
        tabela cresce. Diluído sobre as n inserções, o custo AMORTIZADO por
        inserção continua O(1) -- o mesmo argumento que sustenta o `append` de
        listas dinâmicas.
        """
        antigos = self.baldes
        self.capacidade *= 2
        self.baldes = [[] for _ in range(self.capacidade)]
        self.n = 0
        self.colisoes = 0
        for balde in antigos:
            for chave, valor in balde:
                self.inserir(chave, valor)

    def estatisticas(self):
        """Métricas de dispersão, usadas na seção de hash do relatório."""
        ocupados = [len(b) for b in self.baldes if b]
        return {
            "chaves": self.n,
            "capacidade": self.capacidade,
            "fator de carga": round(self.n / self.capacidade, 3),
            "baldes ocupados": len(ocupados),
            "colisoes": self.colisoes,
            "maior cadeia": max(ocupados) if ocupados else 0,
            "cadeia media": round(sum(ocupados) / len(ocupados), 3) if ocupados else 0.0,
        }

    def __len__(self):
        return self.n

    def __contains__(self, chave):
        return self.buscar(chave, _AUSENTE) is not _AUSENTE


_AUSENTE = object()   # sentinela para distinguir "valor None" de "chave ausente"


# ==========================================================================
#  ÍNDICE INVERTIDO
# ==========================================================================

class IndiceInvertido:
    """
    Índice invertido com duas chaves de acesso e ranqueamento por relevância.

    --- Por que dois índices ---
    `por_termo` guarda a palavra exata como aparece no texto, atendendo ao que
    a seção 3.5 do enunciado pede literalmente. `por_radical` guarda o radical
    produzido pelo RSLP, o que faz "algoritmo" encontrar "algoritmos" -- sem
    isso o exemplo da seção 3.7.1 do próprio enunciado não funcionaria. Manter
    os dois permite comparar as duas estratégias lado a lado no relatório.

    --- Estrutura ---
    Cada índice é um dicionário de dicionários:

        {termo: {documento: frequência}}

    Guardar a frequência, e não apenas o conjunto de documentos, é o que torna
    possível ranquear os resultados. O custo extra de memória é pequeno e
    habilita TF-IDF e BM25.

    --- Complexidade ---
        indexar documento     O(t), com t = tokens do documento
        buscar termo          O(1) em média (uma consulta de hash)
        ranquear consulta     O(q * d), com q termos e d documentos que contêm
                              cada termo -- só os documentos que realmente
                              contêm algum termo da consulta são visitados
    """

    # Parâmetros do BM25. Os valores são os recomendados por Robertson &
    # Zaragoza (2009) e são os padrões de Lucene e Elasticsearch.
    K1 = 1.5      # saturação da frequência do termo
    B = 0.75      # peso da normalização por tamanho do documento

    def __init__(self):
        self.por_termo = {}            # palavra exata -> {documento: frequência}
        self.por_radical = {}          # radical RSLP  -> {documento: frequência}
        self.documentos = []           # nomes, na ordem de indexação
        self.tamanho_documento = {}    # documento -> total de tokens indexados
        self.total_tokens = 0

    # ------------------------------------------------------------- construção

    def indexar(self, documento, tokens, preprocessador):
        """
        Adiciona um documento ao índice.

        Percorre os tokens uma única vez, alimentando os dois índices em
        paralelo. Complexidade: O(t).
        """
        if documento not in self.tamanho_documento:
            self.documentos.append(documento)

        self.tamanho_documento[documento] = len(tokens)
        self.total_tokens += len(tokens)

        for token in tokens:
            chave_exata = token.lower()
            postagem = self.por_termo.setdefault(chave_exata, {})
            postagem[documento] = postagem.get(documento, 0) + 1

            chave_radical = preprocessador.radicalizar(token)
            postagem = self.por_radical.setdefault(chave_radical, {})
            postagem[documento] = postagem.get(documento, 0) + 1

    # ------------------------------------------------------------------ busca

    def buscar(self, termo, usar_radical=True):
        """
        Documentos em que o termo aparece, com a frequência em cada um.

        Devolve um dicionário {documento: frequência}, vazio se o termo não
        existir. Complexidade: O(1) em média.
        """
        indice = self.por_radical if usar_radical else self.por_termo
        return dict(indice.get(termo, {}))

    def frequencia_documental(self, termo, usar_radical=True):
        """Em quantos documentos o termo aparece (o df da literatura de RI)."""
        indice = self.por_radical if usar_radical else self.por_termo
        return len(indice.get(termo, ()))

    # ------------------------------------------------------------ ranqueamento

    def _idf(self, termo, usar_radical=True):
        """
        Frequência inversa de documento, na formulação probabilística do BM25.

            IDF(t) = ln( (N - df + 0.5) / (df + 0.5) + 1 )

        O "+1" dentro do logaritmo é a correção adotada pelo Lucene: sem ela um
        termo presente em mais da metade da coleção receberia peso negativo, o
        que faria um documento perder pontos por conter o termo buscado.

        A intuição de Spärck Jones (1972) está no numerador: quanto MENOR o
        número de documentos que contêm o termo, MAIOR o seu poder de
        discriminação.
        """
        n = len(self.documentos)
        df = self.frequencia_documental(termo, usar_radical)
        if df == 0:
            return 0.0
        return math.log((n - df + 0.5) / (df + 0.5) + 1.0)

    def tamanho_medio(self):
        """Tamanho médio dos documentos em tokens -- o avgdl da fórmula BM25."""
        if not self.documentos:
            return 0.0
        return self.total_tokens / len(self.documentos)

    def ranquear_bm25(self, termos, usar_radical=True):
        """
        Ordena os documentos por relevância para a consulta, usando BM25.

            score(D,Q) = Σ  IDF(t) * ---------------------------------------
                        t∈Q             f(t,D) * (k1 + 1)
                                     -------------------------------------
                                     f(t,D) + k1 * (1 - b + b * |D| / avgdl)

        Leitura dos três fatores:
          * IDF(t)          -- termos raros pesam mais;
          * saturação (k1)  -- repetir a palavra ajuda, mas com retorno
                               decrescente: de 1 para 2 ocorrências o ganho é
                               grande, de 20 para 21 é quase nulo;
          * normalização (b)-- documentos mais longos que a média têm o score
                               reduzido, porque acumulam ocorrências apenas por
                               serem grandes.

        Devolve lista de (documento, score) em ordem decrescente.
        Complexidade: O(q * d).
        """
        tamanho_medio = self.tamanho_medio()
        if not tamanho_medio:
            return []

        pontuacoes = {}
        for termo in termos:
            idf = self._idf(termo, usar_radical)
            if idf == 0.0:
                continue

            for documento, frequencia in self.buscar(termo, usar_radical).items():
                normalizacao = 1.0 - self.B + self.B * (
                    self.tamanho_documento[documento] / tamanho_medio
                )
                contribuicao = idf * (frequencia * (self.K1 + 1.0)) / (
                    frequencia + self.K1 * normalizacao
                )
                pontuacoes[documento] = pontuacoes.get(documento, 0.0) + contribuicao

        return sorted(pontuacoes.items(), key=lambda par: (-par[1], par[0]))

    def ranquear_tfidf(self, termos, usar_radical=True):
        """
        Ranqueamento TF-IDF clássico, mantido para comparação com o BM25.

            peso(t,D) = (1 + log10 f(t,D)) * log10(N / df(t))

        A diferença prática em relação ao BM25 aparece em documentos longos:
        sem o fator de normalização por tamanho, o TF-IDF tende a favorecê-los.
        """
        n = len(self.documentos)
        if not n:
            return []

        pontuacoes = {}
        for termo in termos:
            df = self.frequencia_documental(termo, usar_radical)
            if df == 0:
                continue
            idf = math.log10(n / df)

            for documento, frequencia in self.buscar(termo, usar_radical).items():
                peso = (1.0 + math.log10(frequencia)) * idf
                pontuacoes[documento] = pontuacoes.get(documento, 0.0) + peso

        return sorted(pontuacoes.items(), key=lambda par: (-par[1], par[0]))

    # ---------------------------------------------------------------- métricas

    def total_termos(self, usar_radical=True):
        """Número de chaves distintas em um dos dois índices."""
        return len(self.por_radical if usar_radical else self.por_termo)

    def total_postagens(self, usar_radical=True):
        """
        Número de pares (termo, documento) armazenados.

        É a medida real de tamanho do índice: um termo que aparece em 10
        documentos ocupa 10 postagens, não 1.
        """
        indice = self.por_radical if usar_radical else self.por_termo
        return sum(len(postagem) for postagem in indice.values())

    def espelhar_em_tabela_hash(self, usar_radical=True):
        """
        Copia o índice para a `TabelaHash` própria, para medir colisões e
        comprimento de cadeia sobre dados reais. Usado apenas no relatório --
        o sistema continua operando sobre o `dict`.
        """
        indice = self.por_radical if usar_radical else self.por_termo
        tabela = TabelaHash(capacidade=1024)
        for termo, postagem in indice.items():
            tabela.inserir(termo, postagem)
        return tabela

    def __len__(self):
        return len(self.por_radical)

    def __repr__(self):
        return (
            f"IndiceInvertido(documentos={len(self.documentos)}, "
            f"termos={len(self.por_termo)}, radicais={len(self.por_radical)})"
        )
