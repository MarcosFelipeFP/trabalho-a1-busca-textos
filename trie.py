"""
trie.py
-------
Implementação própria da estrutura Trie (árvore de prefixos) e da sua variante
comprimida (PATRICIA / radix tree). Nenhuma biblioteca externa é usada — todo o
comportamento é construído sobre dicionários da linguagem.

Referências:
    Fredkin, E. "Trie Memory". Communications of the ACM, 3(9):490-499, 1960.
    Morrison, D. R. "PATRICIA - Practical Algorithm To Retrieve Information
        Coded in Alphanumeric". Journal of the ACM, 15(4):514-534, 1968.

--------------------------------------------------------------------------
Decisão de projeto: o caminho é sem acento, a palavra é a grafia
--------------------------------------------------------------------------
Palavras do português carregam acentos, e o acento distingue palavras:
"país" e "pais", "análise" e "analise" (do verbo analisar), "contínua" e
"continua" são palavras diferentes.

A solução adotada separa as duas funções da chave:

  * o CAMINHO percorrido na Trie é a forma normalizada (minúscula, sem
    acento). É o que deixa o prefixo "computa" -- e também "computac",
    digitado sem cedilha -- chegar a "computação";
  * cada GRAFIA é uma palavra. O nó final guarda as grafias inseridas, cada
    uma com o seu peso: "análise" e "analise" dividem o caminho "analise",
    mas são duas palavras, contadas, listadas e buscadas uma a uma. A busca
    exata compara a grafia: com só "país" inserida, "pais" não existe.

Efeito colateral bem-vindo: percorrer o caminho sem acento em ordem
alfabética reproduz exatamente a ordem do exemplo do enunciado
(compilador, complexidade, computação, computacional, computador), porque
"computacao" < "computacional" < "computador".

--------------------------------------------------------------------------
Decisão de projeto: dois agregados por nó
--------------------------------------------------------------------------
Cada nó guarda, além do que a Trie clássica exige, dois números sobre a sua
própria subárvore:

    palavras_abaixo   quantas palavras estão armazenadas abaixo (e nele)
    melhor_peso       o maior peso entre essas palavras

Os dois são mantidos DURANTE a inserção, ao longo do mesmo caminho de m+1 nós
que a inserção já percorre — o custo continua O(m). O que se ganha em troca:

  * `contar_prefixo` deixa de varrer a subárvore e passa a ler um inteiro:
    O(m + p) vira O(m);
  * `sugerir` consegue devolver as k palavras mais relevantes sem abrir a
    subárvore inteira, porque `melhor_peso` é um limite superior que permite
    podar ramos inteiros (busca best-first, detalhada no método).

O preço é honesto e vale registrar: três campos a mais por nó. Numa estrutura
cujo ponto fraco declarado é justamente o consumo de memória, isso é uma troca
deliberada de espaço por tempo — e a Trie comprimida, que tem muito menos nós,
paga esse preço muito menos vezes.
"""

import heapq
import unicodedata

__all__ = ["normalizar", "grafia", "distancia_edicao", "NoTrie", "Trie",
           "NoTrieComprimida", "TrieComprimida"]


def grafia(texto):
    """
    Devolve a palavra como ela é escrita, só que em minúsculas: os acentos
    ficam. É a identidade de uma palavra na Trie -- "Computação" e
    "computação" são a mesma palavra; "computacao" é outra.

    A forma NFC junta letra e sinal num caractere só (c + cedilha -> ç), para
    que a mesma palavra digitada de dois jeitos não vire duas.

    Complexidade: O(m).
    """
    return unicodedata.normalize("NFC", texto.strip().lower())


def normalizar(texto):
    """
    Devolve a forma canônica de uma palavra: minúscula e sem acentos.

    A decomposição NFD separa a letra do sinal diacrítico (ç -> c + cedilha) e
    o filtro descarta os sinais, restando apenas as letras-base.

    Exemplo: normalizar("Computação") devolve "computacao".

    Complexidade: O(m), onde m é o comprimento da palavra.
    """
    decomposto = unicodedata.normalize("NFD", texto.strip().lower())
    return "".join(c for c in decomposto if not unicodedata.combining(c))


def distancia_edicao(a, b):
    """
    Distância de Damerau-Levenshtein restrita entre duas cadeias, pela matriz
    completa.

    É a definição direta, sem Trie e sem poda: O(|a|·|b|) por par. Serve de
    referência -- os testes exigem que `Trie.buscar_aproximado` devolva
    exatamente o que esta função, aplicada palavra a palavra, devolveria -- e
    de termo de comparação no experimento de `benchmark.py`.
    """
    anterior_do_anterior = None
    anterior = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        linha = [i]
        for j in range(1, len(b) + 1):
            custo = 0 if a[i - 1] == b[j - 1] else 1
            valor = min(linha[j - 1] + 1, anterior[j] + 1, anterior[j - 1] + custo)
            if (i > 1 and j > 1 and a[i - 1] == b[j - 2]
                    and a[i - 2] == b[j - 1]):
                valor = min(valor, anterior_do_anterior[j - 2] + 1)
            linha.append(valor)
        anterior_do_anterior, anterior = anterior, linha
    return anterior[len(b)]


# ==========================================================================
#  TRIE TRADICIONAL
# ==========================================================================

class NoTrie:
    """
    Nó de uma Trie tradicional: cada aresta guarda um único caractere.

    __slots__ elimina o dicionário de atributos que todo objeto Python carrega
    por padrão. Numa estrutura com dezenas de milhares de nós isso reduz o
    consumo de memória de forma expressiva — e o consumo de memória é
    justamente o ponto fraco da Trie tradicional discutido no relatório.

    Além do que a Trie clássica exige, o nó guarda dois agregados da sua
    subárvore, mantidos durante a inserção e explicados em detalhe no cabeçalho
    do módulo: `palavras_abaixo` e `melhor_peso`.
    """

    __slots__ = ("filhos", "fim_de_palavra", "formas",
                 "palavras_abaixo", "melhor_peso")

    def __init__(self):
        self.filhos = {}             # caractere -> NoTrie
        self.fim_de_palavra = False  # marca o término de uma palavra válida
        self.formas = None           # grafia -> peso, das palavras que terminam aqui

        self.palavras_abaixo = 0     # palavras armazenadas nesta subárvore
        self.melhor_peso = 0         # maior peso encontrado nesta subárvore


class Trie:
    """
    Árvore de prefixos.

    Cada aresta carrega um caractere; o caminho da raiz até um nó marcado
    representa uma palavra. Prefixos comuns compartilham o mesmo caminho, que é
    exatamente a propriedade explorada pelo autocomplete.

    Complexidades (m = tamanho da palavra/prefixo, k = palavras retornadas,
    p = número de nós na subárvore do prefixo, h = altura da Trie):

        inserir(palavra)       O(m)
        buscar(palavra)        O(m)
        buscar_prefixo(pref)   O(m + p)  -- desce o prefixo e varre a subárvore
        contar_prefixo(pref)   O(m)      -- lê o agregado do nó, não varre nada
        sugerir(pref, k)       O(m + k·h·σ·log(k·h·σ)) -- não depende de p
        buscar_aproximado(w)   O(n·m), n = nós que sobrevivem à poda
    """

    def __init__(self, palavras=None):
        self.raiz = NoTrie()
        self._total_palavras = 0   # palavras (grafias) armazenadas
        self._total_nos = 1        # a raiz já conta
        self.comparacoes = 0       # instrumentação usada nos experimentos
        self.nos_visitados = 0     # nós tocados pela última busca por prefixo

        if palavras:
            for palavra in palavras:
                self.inserir(palavra)

    # ---------------------------------------------------------------- inserção

    def inserir(self, palavra, peso=1):
        """
        Insere uma palavra na Trie.

        Percorre o caminho sem acento caractere a caractere, criando os nós que
        ainda não existirem, e registra a grafia no nó final. Devolve True se a
        palavra é nova e False se aquela grafia já estava lá. "analise" é nova
        mesmo com "análise" inserida: divide o caminho, mas é outra palavra.

        `peso` é a relevância da palavra (no mecanismo de busca, a frequência
        dela no corpus). Reinserir a mesma palavra com peso maior atualiza o
        valor; o padrão 1 deixa todas as palavras equivalentes, que é o
        comportamento esperado de uma Trie comum.

        Complexidade: O(m). Os dois agregados são atualizados numa segunda
        passada pelo MESMO caminho de m+1 nós já visitados, portanto o custo
        continua linear no tamanho da palavra.
        """
        forma = grafia(palavra)
        chave = normalizar(forma)
        if not chave:
            return False

        # O caminho é guardado na descida porque as agregações são propagadas
        # da folha para a raiz, e a Trie não mantém ponteiro para o pai.
        caminho = [self.raiz]
        no = self.raiz
        for caractere in chave:
            proximo = no.filhos.get(caractere)
            if proximo is None:
                proximo = NoTrie()
                no.filhos[caractere] = proximo
                self._total_nos += 1
            no = proximo
            caminho.append(no)

        if no.formas is None:
            no.fim_de_palavra = True
            no.formas = {}
        nova = forma not in no.formas
        if nova:
            no.formas[forma] = peso
            self._total_palavras += 1
        elif peso > no.formas[forma]:
            no.formas[forma] = peso
        peso_da_forma = no.formas[forma]

        for ancestral in caminho:
            if nova:
                ancestral.palavras_abaixo += 1
            if peso_da_forma > ancestral.melhor_peso:
                ancestral.melhor_peso = peso_da_forma
        return nova

    # ------------------------------------------------------------------ busca

    def _descer(self, texto):
        """
        Desce a Trie seguindo `texto` e devolve o nó alcançado, ou None se o
        caminho não existir. É a base tanto da busca exata quanto da busca por
        prefixo.

        Complexidade: O(m).
        """
        no = self.raiz
        for caractere in texto:
            self.comparacoes += 1
            no = no.filhos.get(caractere)
            if no is None:
                return None
        return no

    def buscar(self, palavra):
        """
        Informa se a palavra completa existe na Trie.

        Não basta o caminho existir: o nó final precisa estar marcado como fim
        de palavra. É o que distingue uma palavra realmente armazenada de um
        simples prefixo de outra — "comp" é caminho de "computador", mas só é
        palavra se tiver sido inserida.

        Nem basta chegar ao nó: a grafia tem de ser a mesma. O caminho é sem
        acento, então "pais" e "país" chegam ao mesmo nó, mas só existe a que
        foi inserida. Maiúsculas não contam: "Computação" é "computação".

        Complexidade: O(m).
        """
        forma = grafia(palavra)
        no = self._descer(normalizar(forma))
        return no is not None and no.fim_de_palavra and forma in no.formas

    def formas_de(self, palavra):
        """
        As palavras que dividem o caminho de `palavra`: as grafias inseridas
        que só diferem dela no acento -- "pais" devolve {"país"} se só esta foi
        inserida. Conjunto vazio se não houver nenhuma. O(m).
        """
        no = self._descer(normalizar(palavra))
        if no is None or not no.fim_de_palavra:
            return set()
        return set(no.formas)

    def buscar_prefixo(self, prefixo, limite=None):
        """
        Devolve, em ordem alfabética, todas as palavras que começam com o prefixo.

        São duas etapas com custos distintos:
          1. descer o prefixo             -> O(m)
          2. varrer a subárvore restante  -> O(p), proporcional ao número de nós
                                             abaixo do prefixo

        O prefixo é comparado sem acento, como o caminho: "computac" encontra
        "computação". As palavras devolvidas são as grafias inseridas, uma a
        uma -- "analise" e "análise" aparecem as duas.

        O parâmetro `limite` interrompe a coleta após k resultados, útil quando
        o prefixo é curto e a subárvore é enorme: digitar "a" pode alcançar
        milhares de palavras.

        Complexidade: O(m + p), ou O(m + k) quando `limite` é informado.
        """
        no = self._descer(normalizar(prefixo))
        if no is None:
            return []

        self.nos_visitados = 0      # instrumentação: contraste com `sugerir`
        encontradas = []
        self._coletar(no, encontradas, limite)
        return encontradas

    def _coletar(self, no, saida, limite):
        """
        Busca em profundidade que acumula as palavras da subárvore.

        Usa pilha explícita em vez de recursão para não esbarrar no limite de
        recursão do Python quando as chaves são muito longas. Os filhos são
        empilhados em ordem DECRESCENTE para que o menor caractere seja
        desempilhado primeiro.

        Com essa disciplina a travessia em pré-ordem já sai ordenada, e não é
        preciso ordenar coisa alguma no fim:

          * o nó é emitido antes dos seus descendentes, e toda chave da
            subárvore tem a chave do nó como prefixo — na ordem lexicográfica
            um prefixo vem sempre antes de suas extensões ("comp" < "compilar");
          * entre irmãos, quem tem o menor caractere é visitado primeiro.

        Isso importa quando há `limite`: os k primeiros resultados são de fato
        os k alfabeticamente menores, e não uma amostra arbitrária que ainda
        precisaria ser ordenada. Poupa a ordenação O(k log k) do fim.

        As grafias de um mesmo nó, que só diferem no acento, saem em ordem
        alfabética entre si: "analise" antes de "análise".
        """
        pilha = [no]
        while pilha:
            if limite is not None and len(saida) >= limite:
                return
            atual = pilha.pop()
            self.nos_visitados += 1

            if atual.fim_de_palavra:
                for forma in sorted(atual.formas):
                    if limite is not None and len(saida) >= limite:
                        return
                    saida.append(forma)

            for caractere in sorted(atual.filhos, reverse=True):
                pilha.append(atual.filhos[caractere])

    def contar_prefixo(self, prefixo):
        """
        Quantas palavras começam com o prefixo.

        Custa O(m), e não O(m + p): a contagem não é calculada aqui, ela já
        está pronta no nó, mantida pela inserção. Desce-se o prefixo e lê-se um
        inteiro.

        A diferença é prática, não cosmética. A interface mostra "25 de 1.238
        termos" a cada consulta por prefixo; com a varredura, descobrir esse
        1.238 obrigava a visitar a subárvore inteira — exatamente o trabalho
        que o `limite` da busca existia para evitar. O agregado devolve o total
        sem tocar em nenhum nó abaixo do prefixo.
        """
        no = self._descer(normalizar(prefixo))
        return no.palavras_abaixo if no is not None else 0

    def sugerir(self, prefixo, limite=10):
        """
        As `limite` palavras mais relevantes que começam com o prefixo, da mais
        para a menos relevante. Devolve pares (palavra, peso).

        É o autocomplete como ele funciona na prática: a busca alfabética
        devolve o que vem primeiro no dicionário, não o que o usuário
        provavelmente quis. Para o prefixo "com", "combate" ganha de
        "computador" na ordem alfabética, embora o corpus mencione o segundo
        muitas vezes mais.

        --- O algoritmo: busca best-first com fila de prioridade ---
        A chave é o agregado `melhor_peso`, que em cada nó guarda o maior peso
        da sua subárvore. Ele é um LIMITE SUPERIOR: nenhuma palavra abaixo
        daquele nó pode valer mais do que isso. Basta então explorar a Trie na
        ordem decrescente desse limite, mantendo a fronteira em uma heap:

          * desempilha-se sempre o item de maior prioridade;
          * um item-PALAVRA no topo pode ser emitido com segurança, porque
            toda subárvore ainda fechada tem limite superior menor ou igual;
          * um item-NÓ é expandido: gera um item-palavra por grafia que
            termina nele e um item por filho.

        O laço para assim que k palavras saem. Subárvores cujo melhor peso é
        pior que o k-ésimo resultado NUNCA chegam a ser abertas.

        --- Complexidade ---
        A busca exaustiva custa O(m + p), com p = nós abaixo do prefixo: para
        prefixos curtos, p é quase o vocabulário inteiro. Aqui, todo nó
        desempilhado tem melhor_peso ≥ peso do k-ésimo resultado, e esses nós
        estão nos caminhos que levam às k melhores palavras — são O(k·h), com
        h = altura da Trie. Cada expansão empurra até σ filhos na heap, a
        O(log) por operação, o que dá

            O(m + k·h·σ · log(k·h·σ))

        O que importa nessa expressão não é o tamanho dela, é o que sumiu: p.
        O custo deixou de depender de quantas palavras existem sob o prefixo, e
        é por isso que o autocomplete responde igualmente rápido para "c" e
        para "computa".

        Empates de peso são desfeitos pela ordem alfabética do caminho e, no
        mesmo caminho, da grafia, o que mantém a saída determinística —
        condição para os testes automatizados e para a comparação com o motor
        JavaScript.
        """
        chave = normalizar(prefixo)
        no = self._descer(chave)
        if no is None:
            return []

        self.nos_visitados = 0

        # Itens da heap: (-peso, caminho, tipo, grafia, nó). Os quatro
        # primeiros campos bastam para ordenar e são únicos — cada nó gera um
        # item-nó e um item-palavra por grafia —, de modo que a heap nunca
        # precisa comparar dois objetos NoTrie, que não definem ordem entre si.
        TIPO_PALAVRA, TIPO_NO = 0, 1
        fila = [(-no.melhor_peso, chave, TIPO_NO, "", no)]
        encontradas = []

        while fila and len(encontradas) < limite:
            peso_negativo, caminho, tipo, forma, atual = heapq.heappop(fila)

            if tipo == TIPO_PALAVRA:
                encontradas.append((forma, -peso_negativo))
                continue

            self.nos_visitados += 1

            if atual.fim_de_palavra:
                for forma_do_no, peso in atual.formas.items():
                    heapq.heappush(fila, (-peso, caminho, TIPO_PALAVRA, forma_do_no, atual))

            for caractere, filho in atual.filhos.items():
                heapq.heappush(
                    fila,
                    (-filho.melhor_peso, caminho + caractere, TIPO_NO, "", filho),
                )

        return encontradas

    def buscar_aproximado(self, palavra, distancia_maxima=None, limite=5):
        """
        Palavras a no máximo `distancia_maxima` edições de `palavra`, para o
        "você quis dizer?". Devolve trios (palavra, distância, peso), da mais
        próxima para a mais distante e, na mesma distância, da mais relevante
        para a menos relevante.

        Sem `distancia_maxima`, a tolerância acompanha o tamanho da palavra: com
        quatro letras ou menos, duas edições transformam quase qualquer palavra
        em quase qualquer outra ("rede" alcançaria "roda", "sede", "rei"...),
        então o limite cai para uma.

        Uma edição é inserir, remover ou trocar um caractere, ou inverter dois
        vizinhos -- "algortimo" está a UMA edição de "algoritmo". É a distância
        de Damerau-Levenshtein restrita (optimal string alignment), a variante
        que conta a transposição, o erro de digitação mais comum.

        A distância é medida no caminho sem acento: "computacao" está a zero
        edições de "computação". É outra palavra, e por isso entra na lista --
        a primeira sugestão para quem digitou sem acento. Quem chama descarta
        a própria palavra digitada.

        --- O algoritmo: programação dinâmica sobre a própria Trie ---
        A distância entre duas cadeias é a última célula de uma matriz em que a
        linha i depende só das linhas i-1 e i-2. Na Trie, a linha i de um nó é a
        do seu caminho de i caracteres -- e todas as palavras abaixo dele
        compartilham esse caminho. Uma travessia em profundidade calcula então
        UMA linha por nó, e cada linha vale para a subárvore inteira.

        Comparar a consulta com cada palavra do vocabulário, em separado,
        recalcularia o prefixo "comput" para "computador", "computação",
        "computacional"... A Trie calcula uma vez.

        --- A poda ---
        O menor valor de uma linha nunca é menor que o da linha anterior: as
        três primeiras operações partem da linha de cima somando 0 ou 1, e a
        transposição parte de duas linhas acima somando 1 -- e duas linhas acima
        o mínimo era no máximo 1 a menos. Logo, quando o mínimo da linha passa
        de `distancia_maxima`, nenhuma palavra da subárvore volta para dentro
        do limite, e o ramo inteiro é descartado sem ser visitado.

        --- Complexidade ---
        O(n·m), com n = nós visitados e m = tamanho da consulta. Sem a poda, n
        seria o total de nós da Trie; com ela, n fica restrito aos caminhos que
        ainda estão a até `distancia_maxima` edições de algum prefixo da
        consulta -- tipicamente uma fração pequena da árvore.
        """
        chave = normalizar(palavra)
        if not chave:
            return []

        m = len(chave)
        if distancia_maxima is None:
            distancia_maxima = 1 if m <= 4 else 2
        self.nos_visitados = 0
        linha_da_raiz = list(range(m + 1))
        candidatas = []

        # Cada item: (nó, caminho até ele, linha do pai, linha do avô). Pilha
        # explícita pelo mesmo motivo de `_coletar`: chaves longas não podem
        # esbarrar no limite de recursão.
        pilha = [(filho, caractere, linha_da_raiz, None)
                 for caractere, filho in self.raiz.filhos.items()]

        while pilha:
            no, caminho, anterior, avo = pilha.pop()
            self.nos_visitados += 1

            atual = caminho[-1]
            linha = [len(caminho)]
            for j in range(1, m + 1):
                custo = 0 if chave[j - 1] == atual else 1
                valor = min(linha[j - 1] + 1,          # inserção
                            anterior[j] + 1,           # remoção
                            anterior[j - 1] + custo)   # troca (ou acerto)
                if (avo is not None and j > 1 and atual == chave[j - 2]
                        and caminho[-2] == chave[j - 1]):
                    valor = min(valor, avo[j - 2] + 1)  # transposição
                linha.append(valor)

            if no.fim_de_palavra and linha[m] <= distancia_maxima:
                for forma, peso in no.formas.items():
                    candidatas.append((linha[m], -peso, caminho, forma))

            if min(linha) <= distancia_maxima:
                for caractere, filho in no.filhos.items():
                    pilha.append((filho, caminho + caractere, linha, anterior))

        # Mais perto primeiro; empate pela relevância e, por fim, pelo caminho
        # e pela grafia, para a saída ser determinística (e igual à do motor
        # JavaScript).
        candidatas.sort()
        if limite is not None:
            candidatas = candidatas[:limite]
        return [(forma, distancia, -peso_negativo)
                for distancia, peso_negativo, _caminho, forma in candidatas]

    # ---------------------------------------------------------------- métricas

    def total_nos(self):
        """Número de nós alocados — métrica de memória usada no relatório."""
        return self._total_nos

    def altura(self):
        """Comprimento do caminho mais longo, isto é, o tamanho da maior chave."""
        maior = 0
        pilha = [(self.raiz, 0)]
        while pilha:
            no, profundidade = pilha.pop()
            if profundidade > maior:
                maior = profundidade
            for filho in no.filhos.values():
                pilha.append((filho, profundidade + 1))
        return maior

    def __len__(self):
        """Palavras armazenadas -- cada grafia conta uma vez."""
        return self._total_palavras

    def __contains__(self, palavra):
        return self.buscar(palavra)

    def __repr__(self):
        return f"Trie(palavras={self._total_palavras}, nos={self._total_nos})"


# ==========================================================================
#  TRIE COMPRIMIDA (PATRICIA / RADIX TREE)
# ==========================================================================

class NoTrieComprimida:
    """
    Nó de uma Trie comprimida: a aresta guarda uma SUBSTRING, não um caractere.

    É essa a diferença estrutural em relação à Trie tradicional. Numa cadeia de
    nós sem bifurcação — "e", "x", "c", "e", "ç", "ã", "o" para a palavra
    "exceção" — a Trie tradicional aloca sete nós; a comprimida aloca um só,
    com o rótulo "excecao".
    """

    __slots__ = ("rotulo", "filhos", "fim_de_palavra", "formas",
                 "palavras_abaixo", "melhor_peso")

    def __init__(self, rotulo=""):
        self.rotulo = rotulo         # trecho da chave consumido nesta aresta
        self.filhos = {}             # primeiro caractere do rótulo -> nó filho
        self.fim_de_palavra = False
        self.formas = None           # grafia -> peso, das palavras que terminam aqui

        self.palavras_abaixo = 0     # palavras armazenadas nesta subárvore
        self.melhor_peso = 0         # maior peso encontrado nesta subárvore


class TrieComprimida:
    """
    Trie comprimida no estilo PATRICIA (Morrison, 1968).

    Colapsa cadeias de nós de filho único em uma única aresta rotulada com a
    substring correspondente. O resultado é a MESMA linguagem reconhecida e as
    MESMAS complexidades assintóticas da Trie tradicional — O(m) para inserir e
    buscar —, com consumo de memória bem menor, porque some a maior parte dos
    nós intermediários.

    É a resposta prática à questão conceitual 6 do enunciado: o relatório
    compara o número de nós das duas estruturas sobre o mesmo vocabulário.
    """

    def __init__(self, palavras=None):
        self.raiz = NoTrieComprimida()
        self._total_palavras = 0
        self._total_nos = 1

        if palavras:
            for palavra in palavras:
                self.inserir(palavra)

    @staticmethod
    def _prefixo_comum(a, b):
        """Comprimento do maior prefixo comum entre duas strings."""
        limite = min(len(a), len(b))
        i = 0
        while i < limite and a[i] == b[i]:
            i += 1
        return i

    def inserir(self, palavra, peso=1):
        """
        Insere uma palavra, dividindo arestas quando a chave diverge no meio de
        um rótulo.

        Três situações podem ocorrer ao comparar o resto da chave com o rótulo
        do filho:

          1. o rótulo é consumido por inteiro  -> desce e continua;
          2. a chave termina no meio do rótulo -> divide a aresta e marca o
             nó de cima como fim de palavra;
          3. os dois divergem no meio          -> divide a aresta e cria um
             novo filho para o resto da chave.

        Complexidade: O(m).
        """
        forma = grafia(palavra)
        chave = normalizar(forma)
        if not chave:
            return False

        # Assim como na Trie tradicional, o caminho é guardado na descida para
        # que os agregados possam ser propagados de volta até a raiz.
        caminho = [self.raiz]
        no = self.raiz
        resto = chave

        while True:
            if not resto:
                return self._registrar(caminho, no, forma, peso)

            filho = no.filhos.get(resto[0])

            if filho is None:
                # Nada em comum: uma única aresta nova carrega todo o resto.
                novo = NoTrieComprimida(resto)
                no.filhos[resto[0]] = novo
                self._total_nos += 1
                caminho.append(novo)
                return self._registrar(caminho, novo, forma, peso)

            comum = self._prefixo_comum(resto, filho.rotulo)

            if comum == len(filho.rotulo):
                # Caso 1: rótulo inteiramente consumido — desce um nível.
                no = filho
                caminho.append(no)
                resto = resto[comum:]
                continue

            # Casos 2 e 3: a aresta precisa ser dividida em `comum`.
            #
            # O nó intermediário HERDA os agregados do filho: ele passa a ser o
            # topo da mesma subárvore que o filho encabeçava. Sem essa herança
            # a contagem de palavras se perderia a cada divisão de aresta.
            intermediario = NoTrieComprimida(filho.rotulo[:comum])
            intermediario.palavras_abaixo = filho.palavras_abaixo
            intermediario.melhor_peso = filho.melhor_peso
            no.filhos[resto[0]] = intermediario
            self._total_nos += 1

            filho.rotulo = filho.rotulo[comum:]
            intermediario.filhos[filho.rotulo[0]] = filho
            caminho.append(intermediario)

            if comum == len(resto):
                # Caso 2: a chave termina exatamente no ponto da divisão.
                return self._registrar(caminho, intermediario, forma, peso)

            # Caso 3: sobra chave — vira um segundo filho do intermediário.
            sobra = resto[comum:]
            novo = NoTrieComprimida(sobra)
            intermediario.filhos[sobra[0]] = novo
            self._total_nos += 1
            caminho.append(novo)
            return self._registrar(caminho, novo, forma, peso)

    def _registrar(self, caminho, destino, forma, peso):
        """
        Registra a grafia no nó de destino, atualiza os agregados da raiz até
        ele e devolve se a palavra é nova -- a mesma regra da Trie tradicional.

        `caminho` termina no próprio destino, de modo que ele também recebe o
        incremento. Custo O(m), o mesmo da descida que já foi feita.
        """
        if destino.formas is None:
            destino.fim_de_palavra = True
            destino.formas = {}
        nova = forma not in destino.formas
        if nova:
            destino.formas[forma] = peso
            self._total_palavras += 1
        elif peso > destino.formas[forma]:
            destino.formas[forma] = peso
        peso_da_forma = destino.formas[forma]

        for ancestral in caminho:
            if nova:
                ancestral.palavras_abaixo += 1
            if peso_da_forma > ancestral.melhor_peso:
                ancestral.melhor_peso = peso_da_forma
        return nova

    def _descer(self, texto):
        """
        Desce seguindo `texto`. Devolve (nó, sobra_do_rótulo) ou None.

        `sobra_do_rótulo` é o pedaço do rótulo do nó que ficou além do texto
        buscado: se for vazio, o texto terminou exatamente sobre o nó — o que
        distingue busca exata de busca por prefixo.
        """
        no = self.raiz
        resto = texto

        while resto:
            filho = no.filhos.get(resto[0])
            if filho is None:
                return None

            if len(resto) < len(filho.rotulo):
                # O texto acaba dentro do rótulo: só serve como prefixo.
                if filho.rotulo.startswith(resto):
                    return (filho, filho.rotulo[len(resto):])
                return None

            if not resto.startswith(filho.rotulo):
                return None

            no = filho
            resto = resto[len(filho.rotulo):]

        return (no, "")

    def buscar(self, palavra):
        """
        Busca exata. Complexidade: O(m).

        Exige sobra de rótulo vazia — caso contrário a palavra é apenas um
        prefixo de alguma chave, e não uma chave armazenada — e a mesma grafia,
        como na Trie tradicional.
        """
        forma = grafia(palavra)
        achado = self._descer(normalizar(forma))
        if achado is None:
            return False
        no, sobra = achado
        return sobra == "" and no.fim_de_palavra and forma in no.formas

    def buscar_prefixo(self, prefixo, limite=None):
        """
        Palavras que começam com o prefixo, em ordem alfabética.

        Complexidade: O(m + p), a mesma da Trie tradicional — mas com p menor,
        já que a estrutura tem menos nós para visitar.
        """
        achado = self._descer(normalizar(prefixo))
        if achado is None:
            return []

        encontradas = []
        pilha = [achado[0]]

        # A travessia em pré-ordem já sai em ordem alfabética, pelo mesmo
        # argumento da Trie tradicional: rótulos irmãos começam por caracteres
        # distintos, então ordená-los pela inicial é ordená-los por inteiro.
        while pilha:
            if limite is not None and len(encontradas) >= limite:
                break
            atual = pilha.pop()

            if atual.fim_de_palavra:
                for forma in sorted(atual.formas):
                    if limite is not None and len(encontradas) >= limite:
                        break
                    encontradas.append(forma)

            for inicial in sorted(atual.filhos, reverse=True):
                pilha.append(atual.filhos[inicial])

        return encontradas

    def contar_prefixo(self, prefixo):
        """
        Quantas palavras começam com o prefixo. O(m), pela mesma razão da Trie
        tradicional: o número já está agregado no nó.

        Quando o prefixo termina no meio de um rótulo, o nó devolvido pela
        descida é o dono daquela aresta — e toda palavra da sua subárvore passa
        por ela, então a contagem continua valendo.
        """
        achado = self._descer(normalizar(prefixo))
        if achado is None:
            return 0
        no, _sobra = achado
        return no.palavras_abaixo

    def total_nos(self):
        """Número de nós alocados — comparado com o da Trie tradicional."""
        return self._total_nos

    def __len__(self):
        return self._total_palavras

    def __contains__(self, palavra):
        return self.buscar(palavra)

    def __repr__(self):
        return f"TrieComprimida(palavras={self._total_palavras}, nos={self._total_nos})"
