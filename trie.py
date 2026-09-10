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
"""

import unicodedata

__all__ = ["normalizar", "NoTrie", "Trie", "NoTrieComprimida", "TrieComprimida"]


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
    """

    __slots__ = ("filhos", "fim_de_palavra", "formas")

    def __init__(self):
        self.filhos = {}             # caractere -> NoTrie
        self.fim_de_palavra = False  # marca o término de uma palavra válida
        self.formas = None           # grafias originais associadas a esta chave


class Trie:
    """
    Árvore de prefixos.

    Cada aresta carrega um caractere; o caminho da raiz até um nó marcado
    representa uma palavra. Prefixos comuns compartilham o mesmo caminho, que é
    exatamente a propriedade explorada pelo autocomplete.

    Complexidades (m = tamanho da palavra/prefixo, k = palavras retornadas,
    p = número de nós na subárvore do prefixo):

        inserir(palavra)       O(m)
        buscar(palavra)        O(m)
        buscar_prefixo(pref)   O(m + p)  -- desce o prefixo e varre a subárvore
    """

    def __init__(self, palavras=None):
        self.raiz = NoTrie()
        self._total_palavras = 0   # chaves distintas armazenadas
        self._total_nos = 1        # a raiz já conta
        self.comparacoes = 0       # instrumentação usada nos experimentos

        if palavras:
            for palavra in palavras:
                self.inserir(palavra)

    # ---------------------------------------------------------------- inserção

    def inserir(self, palavra):
        """
        Insere uma palavra na Trie.

        Percorre a chave normalizada caractere a caractere, criando os nós que
        ainda não existirem. Devolve True se a palavra é nova e False se a
        chave já existia — nesse caso apenas registra a nova grafia.

        Complexidade: O(m).
        """
        original = palavra.strip()
        if not original:
            return False

        chave = normalizar(original)
        if not chave:
            return False

        no = self.raiz
        for caractere in chave:
            proximo = no.filhos.get(caractere)
            if proximo is None:
                proximo = NoTrie()
                no.filhos[caractere] = proximo
                self._total_nos += 1
            no = proximo

        nova = not no.fim_de_palavra
        if nova:
            no.fim_de_palavra = True
            no.formas = set()
            self._total_palavras += 1
        no.formas.add(original)
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

        encontradas = []
        self._coletar(no, chave, encontradas, limite)
        encontradas.sort(key=lambda par: par[0])
        return [forma for _, forma in encontradas]

    def _coletar(self, no, prefixo_atual, saida, limite):
        """
        Busca em profundidade que acumula as palavras da subárvore.

        Usa pilha explícita em vez de recursão para não esbarrar no limite de
        recursão do Python quando as chaves são muito longas. Os filhos são
        empilhados em ordem decrescente para que o menor caractere seja
        desempilhado primeiro, deixando a coleta praticamente ordenada.
        """
        pilha = [(no, prefixo_atual)]
        while pilha:
            if limite is not None and len(saida) >= limite:
                return
            atual, caminho = pilha.pop()

            if atual.fim_de_palavra:
                # Uma mesma chave pode ter mais de uma grafia; adota-se a menor
                # em ordem alfabética como representante.
                saida.append((caminho, min(atual.formas)))

            for caractere in sorted(atual.filhos, reverse=True):
                pilha.append((atual.filhos[caractere], caminho + caractere))

    def contar_prefixo(self, prefixo):
        """Quantas palavras começam com o prefixo, sem materializar a lista."""
        no = self._descer(normalizar(prefixo))
        if no is None:
            return 0

        total = 0
        pilha = [no]
        while pilha:
            atual = pilha.pop()
            if atual.fim_de_palavra:
                total += 1
            pilha.extend(atual.filhos.values())
        return total

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

    __slots__ = ("rotulo", "filhos", "fim_de_palavra", "formas")

    def __init__(self, rotulo=""):
        self.rotulo = rotulo         # trecho da chave consumido nesta aresta
        self.filhos = {}             # primeiro caractere do rótulo -> nó filho
        self.fim_de_palavra = False
        self.formas = None


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

    def inserir(self, palavra):
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
                return nova

            filho = no.filhos.get(resto[0])

            if filho is None:
                # Nada em comum: uma única aresta nova carrega todo o resto.
                novo = NoTrieComprimida(resto)
                novo.fim_de_palavra = True
                novo.formas = {original}
                no.filhos[resto[0]] = novo
                self._total_nos += 1
                self._total_palavras += 1
                return True

            comum = self._prefixo_comum(resto, filho.rotulo)

            if comum == len(filho.rotulo):
                # Caso 1: rótulo inteiramente consumido — desce um nível.
                no = filho
                resto = resto[comum:]
                continue

            # Casos 2 e 3: a aresta precisa ser dividida em `comum`.
            intermediario = NoTrieComprimida(filho.rotulo[:comum])
            no.filhos[resto[0]] = intermediario
            self._total_nos += 1

            filho.rotulo = filho.rotulo[comum:]
            intermediario.filhos[filho.rotulo[0]] = filho

            if comum == len(resto):
                # Caso 2: a chave termina exatamente no ponto da divisão.
                intermediario.fim_de_palavra = True
                intermediario.formas = {original}
                self._total_palavras += 1
                return True

            # Caso 3: sobra chave — vira um segundo filho do intermediário.
            sobra = resto[comum:]
            novo = NoTrieComprimida(sobra)
            novo.fim_de_palavra = True
            novo.formas = {original}
            intermediario.filhos[sobra[0]] = novo
            self._total_nos += 1
            self._total_palavras += 1
            return True

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

        encontradas.sort(key=lambda par: par[0])
        return [forma for _, forma in encontradas]

    def total_nos(self):
        """Número de nós alocados — comparado com o da Trie tradicional."""
        return self._total_nos

    def __len__(self):
        return self._total_palavras

    def __contains__(self, palavra):
        return self.buscar(palavra)

    def __repr__(self):
        return f"TrieComprimida(palavras={self._total_palavras}, nos={self._total_nos})"
