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
Decisão de projeto: chave normalizada, exibição original
--------------------------------------------------------------------------
Palavras do português carregam acentos ("computação"). Se o acento fizesse
parte da chave, o prefixo "computa" encontraria "computador", mas o usuário que
digitasse "computacao" não encontraria nada.

A solução adotada separa as duas coisas:

  * a CHAVE que percorre a Trie é a forma normalizada (minúscula, sem acento);
  * o NÓ FINAL guarda o conjunto das formas originais já inseridas.

Assim "computação" é armazenada sob a chave "computacao", e tanto o prefixo
"computa" quanto "computaç" (normalizado para "computac") a encontram — mas o
resultado devolvido ao usuário preserva a acentuação correta.

Efeito colateral bem-vindo: ordenar pela chave normalizada reproduz exatamente
a ordem do exemplo do enunciado
(compilador, complexidade, computação, computacional, computador), porque
"computacao" < "computacional" < "computador" na ordem alfabética.

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

__all__ = ["normalizar", "distancia_edicao", "NoTrie", "Trie",
           "NoTrieComprimida", "TrieComprimida"]


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
                 "peso", "palavras_abaixo", "melhor_peso")

    def __init__(self):
        self.filhos = {}             # caractere -> NoTrie
        self.fim_de_palavra = False  # marca o término de uma palavra válida
        self.formas = None           # grafias originais associadas a esta chave

        self.peso = 0                # relevância da palavra que termina aqui
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
        self._total_palavras = 0   # chaves distintas armazenadas
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

        Percorre a chave normalizada caractere a caractere, criando os nós que
        ainda não existirem. Devolve True se a palavra é nova e False se a
        chave já existia — nesse caso apenas registra a nova grafia.

        `peso` é a relevância da palavra (no mecanismo de busca, a frequência
        dela no corpus). Reinserir a mesma palavra com peso maior atualiza o
        valor; o padrão 1 deixa todas as palavras equivalentes, que é o
        comportamento esperado de uma Trie comum.

        Complexidade: O(m). Os dois agregados são atualizados numa segunda
        passada pelo MESMO caminho de m+1 nós já visitados, portanto o custo
        continua linear no tamanho da palavra.
        """
        original = palavra.strip()
        if not original:
            return False

        chave = normalizar(original)
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

        nova = not no.fim_de_palavra
        if nova:
            no.fim_de_palavra = True
            no.formas = set()
            self._total_palavras += 1
        no.formas.add(original)

        if peso > no.peso:
            no.peso = peso

        for ancestral in caminho:
            if nova:
                ancestral.palavras_abaixo += 1
            if no.peso > ancestral.melhor_peso:
                ancestral.melhor_peso = no.peso
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

        Complexidade: O(m).
        """
        no = self._descer(normalizar(palavra))
        return no is not None and no.fim_de_palavra

    def formas_de(self, palavra):
        """Devolve as grafias originais registradas para uma chave, ou conjunto vazio."""
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

        O parâmetro `limite` interrompe a coleta após k resultados, útil quando
        o prefixo é curto e a subárvore é enorme: digitar "a" pode alcançar
        milhares de palavras.

        Complexidade: O(m + p), ou O(m + k) quando `limite` é informado.
        """
        chave = normalizar(prefixo)
        no = self._descer(chave)
        if no is None:
            return []

        self.nos_visitados = 0      # instrumentação: contraste com `sugerir`
        encontradas = []
        self._coletar(no, chave, encontradas, limite)
        return [forma for _, forma in encontradas]

    def _coletar(self, no, prefixo_atual, saida, limite):
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
        """
        pilha = [(no, prefixo_atual)]
        while pilha:
            if limite is not None and len(saida) >= limite:
                return
            atual, caminho = pilha.pop()
            self.nos_visitados += 1

            if atual.fim_de_palavra:
                # Uma mesma chave pode ter mais de uma grafia; adota-se a menor
                # em ordem alfabética como representante.
                saida.append((caminho, min(atual.formas)))

            for caractere in sorted(atual.filhos, reverse=True):
                pilha.append((atual.filhos[caractere], caminho + caractere))

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
          * um item-NÓ é expandido: gera o item-palavra dele (se for fim de
            palavra) e um item por filho.

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

        Empates de peso são desfeitos pela ordem alfabética da chave, o que
        mantém a saída determinística — condição para os testes automatizados e
        para a comparação com o motor JavaScript.
        """
        chave = normalizar(prefixo)
        no = self._descer(chave)
        if no is None:
            return []

        self.nos_visitados = 0

        # Itens da heap: (-peso, chave, tipo, nó). Os três primeiros campos
        # bastam para ordenar e são únicos — cada nó gera no máximo um item de
        # cada tipo —, de modo que a heap nunca precisa comparar dois objetos
        # NoTrie, que não definem ordem entre si.
        TIPO_PALAVRA, TIPO_NO = 0, 1
        fila = [(-no.melhor_peso, chave, TIPO_NO, no)]
        encontradas = []

        while fila and len(encontradas) < limite:
            peso_negativo, caminho, tipo, atual = heapq.heappop(fila)

            if tipo == TIPO_PALAVRA:
                encontradas.append((min(atual.formas), -peso_negativo))
                continue

            self.nos_visitados += 1

            if atual.fim_de_palavra:
                heapq.heappush(fila, (-atual.peso, caminho, TIPO_PALAVRA, atual))

            for caractere, filho in atual.filhos.items():
                heapq.heappush(
                    fila,
                    (-filho.melhor_peso, caminho + caractere, TIPO_NO, filho),
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
                candidatas.append((linha[m], -no.peso, caminho, no))

            if min(linha) <= distancia_maxima:
                for caractere, filho in no.filhos.items():
                    pilha.append((filho, caminho + caractere, linha, anterior))

        # Mais perto primeiro; empate pela relevância e, por fim, pela chave,
        # para a saída ser determinística (e igual à do motor JavaScript).
        candidatas.sort(key=lambda item: (item[0], item[1], item[2]))
        if limite is not None:
            candidatas = candidatas[:limite]
        return [(min(no.formas), distancia, -peso_negativo)
                for distancia, peso_negativo, _caminho, no in candidatas]

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
                 "peso", "palavras_abaixo", "melhor_peso")

    def __init__(self, rotulo=""):
        self.rotulo = rotulo         # trecho da chave consumido nesta aresta
        self.filhos = {}             # primeiro caractere do rótulo -> nó filho
        self.fim_de_palavra = False
        self.formas = None

        self.peso = 0                # relevância da palavra que termina aqui
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
        original = palavra.strip()
        if not original:
            return False

        chave = normalizar(original)
        if not chave:
            return False

        # Assim como na Trie tradicional, o caminho é guardado na descida para
        # que os agregados possam ser propagados de volta até a raiz.
        caminho = [self.raiz]
        no = self.raiz
        resto = chave

        while True:
            if not resto:
                nova = not no.fim_de_palavra
                if nova:
                    no.fim_de_palavra = True
                    no.formas = set()
                    self._total_palavras += 1
                no.formas.add(original)
                return self._propagar(caminho, no, peso, nova)

            filho = no.filhos.get(resto[0])

            if filho is None:
                # Nada em comum: uma única aresta nova carrega todo o resto.
                novo = NoTrieComprimida(resto)
                novo.fim_de_palavra = True
                novo.formas = {original}
                no.filhos[resto[0]] = novo
                self._total_nos += 1
                self._total_palavras += 1
                caminho.append(novo)
                return self._propagar(caminho, novo, peso, True)

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
                intermediario.fim_de_palavra = True
                intermediario.formas = {original}
                self._total_palavras += 1
                return self._propagar(caminho, intermediario, peso, True)

            # Caso 3: sobra chave — vira um segundo filho do intermediário.
            sobra = resto[comum:]
            novo = NoTrieComprimida(sobra)
            novo.fim_de_palavra = True
            novo.formas = {original}
            intermediario.filhos[sobra[0]] = novo
            self._total_nos += 1
            self._total_palavras += 1
            caminho.append(novo)
            return self._propagar(caminho, novo, peso, True)

    @staticmethod
    def _propagar(caminho, destino, peso, nova):
        """
        Atualiza os agregados da raiz até o nó de destino e devolve `nova`.

        `caminho` termina no próprio destino, de modo que ele também recebe o
        incremento. Custo O(m), o mesmo da descida que já foi feita.
        """
        if peso > destino.peso:
            destino.peso = peso

        for ancestral in caminho:
            if nova:
                ancestral.palavras_abaixo += 1
            if destino.peso > ancestral.melhor_peso:
                ancestral.melhor_peso = destino.peso
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
        prefixo de alguma chave, e não uma chave armazenada.
        """
        achado = self._descer(normalizar(palavra))
        if achado is None:
            return False
        no, sobra = achado
        return sobra == "" and no.fim_de_palavra

    def buscar_prefixo(self, prefixo, limite=None):
        """
        Palavras que começam com o prefixo, em ordem alfabética.

        Complexidade: O(m + p), a mesma da Trie tradicional — mas com p menor,
        já que a estrutura tem menos nós para visitar.
        """
        chave = normalizar(prefixo)
        achado = self._descer(chave)
        if achado is None:
            return []

        no, sobra = achado
        encontradas = []
        pilha = [(no, chave + sobra)]

        while pilha:
            if limite is not None and len(encontradas) >= limite:
                break
            atual, caminho = pilha.pop()

            if atual.fim_de_palavra:
                encontradas.append((caminho, min(atual.formas)))

            for inicial in sorted(atual.filhos, reverse=True):
                filho = atual.filhos[inicial]
                pilha.append((filho, caminho + filho.rotulo))

        # A travessia em pré-ordem já sai em ordem alfabética, pelo mesmo
        # argumento da Trie tradicional: rótulos irmãos começam por caracteres
        # distintos, então ordená-los pela inicial é ordená-los por inteiro.
        return [forma for _, forma in encontradas]

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
