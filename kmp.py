"""
kmp.py
------
Algoritmo de Knuth-Morris-Pratt para casamento exato de cadeias, usado na
consulta opcional da seção 3.7.3 do enunciado: procurar uma sequência de
caracteres diretamente no conteúdo original dos documentos.

Referências:
    Morris, J. H.; Pratt, V. R. "A linear pattern-matching algorithm".
        Technical Report 40, University of California, Berkeley, 1970.
    Knuth, D. E.; Morris, J. H.; Pratt, V. R. "Fast Pattern Matching in
        Strings". SIAM Journal on Computing, 6(2):323-350, 1977.

--------------------------------------------------------------------------
Por que este algoritmo
--------------------------------------------------------------------------
O KMP é o representante canônico do casamento de cadeias em tempo linear e
tem meio século de literatura contínua atrás de si. Sua ideia central -- a
função de falha, que registra o maior prefixo próprio que também é sufixo --
foi generalizada por Aho e Corasick (CACM, 1975) para múltiplos padrões
simultâneos, e é essa generalização que roda hoje dentro do `grep -F`, de
sistemas de detecção de intrusão e de motores de antivírus. A mesma linhagem
segue viva em variantes modernas: o algoritmo two-way de Crochemore e Perrin
(1991) é o que a glibc usa em `strstr` e `memmem`, e o casamento em tempo
sublinear sobre fluxos (Porat & Porat, FOCS 2009) continua sendo área de
pesquisa ativa, assim como o casamento sobre índices comprimidos FM/BWT
usados em bioinformática.

--------------------------------------------------------------------------
A ideia, em uma frase
--------------------------------------------------------------------------
A busca ingênua, ao falhar na posição j do padrão, joga fora tudo o que já
tinha descoberto e recomeça uma posição adiante no texto. O KMP observa que os
j caracteres já casados SÃO CONHECIDOS -- são exatamente os j primeiros do
padrão -- e portanto dá para calcular de antemão, olhando só o padrão, quanto
é seguro deslocar sem perder ocorrência nenhuma.

Exemplo com o padrão "ababc" e o texto "ababab...":

    texto   a b a b a b ...
    padrão  a b a b c
                    ^ falha aqui, com "abab" já casado

    "abab" tem "ab" como maior prefixo que também é sufixo. Logo o algoritmo
    desliza o padrão para alinhar esse "ab" e retoma a comparação a partir do
    terceiro caractere do padrão -- sem NUNCA voltar atrás no texto.

--------------------------------------------------------------------------
Complexidade
--------------------------------------------------------------------------
    função de falha    O(m)
    varredura do texto O(n)
    total              O(n + m), com O(m) de memória

A prova de que a varredura é linear é um argumento de amortização, e é o
detalhe mais elegante do algoritmo. Duas observações bastam:

  * o ponteiro `i` do texto só avança, nunca retrocede: no máximo n incrementos;
  * o ponteiro `j` do padrão cresce no máximo 1 por incremento de `i`, e cada
    retrocesso via função de falha o diminui em pelo menos 1.

Como `j` nunca fica negativo, o total de retrocessos não pode exceder o total
de incrementos. Somando, o laço executa no máximo 2n vezes: O(n).

A busca ingênua, em contraste, é O(n * m) no pior caso -- fácil de exibir com
texto "aaaa...a" e padrão "aaa...ab", em que toda tentativa avança quase até o
fim do padrão antes de falhar no último caractere.
"""

__all__ = ["tabela_falha", "buscar_kmp", "buscar_ingenuo", "ResultadoBusca"]


class ResultadoBusca:
    """Resultado de uma busca: onde casou e quanto custou."""

    __slots__ = ("ocorrencias", "comparacoes")

    def __init__(self, ocorrencias, comparacoes):
        self.ocorrencias = ocorrencias      # posições iniciais no texto
        self.comparacoes = comparacoes      # comparações de caractere feitas

    def __len__(self):
        return len(self.ocorrencias)

    def __bool__(self):
        return bool(self.ocorrencias)

    def __repr__(self):
        return (
            f"ResultadoBusca(ocorrencias={len(self.ocorrencias)}, "
            f"comparacoes={self.comparacoes})"
        )


def tabela_falha(padrao):
    """
    Constrói a função de falha (também chamada de vetor de bordas) do padrão.

    `falha[j]` é o comprimento do maior prefixo PRÓPRIO de padrao[0..j] que
    também é sufixo de padrao[0..j]. "Próprio" significa que não vale o
    prefixo inteiro -- senão a resposta seria sempre o próprio j+1 e o
    algoritmo não sairia do lugar.

    Para "ababc":

        j   trecho   maior prefixo = sufixo   falha[j]
        0   a        (nenhum)                 0
        1   ab       (nenhum)                 0
        2   aba      "a"                      1
        3   abab     "ab"                     2
        4   ababc    (nenhum)                 0

    A construção é o próprio KMP aplicado ao padrão contra ele mesmo, e o mesmo
    argumento de amortização garante custo O(m).
    """
    m = len(padrao)
    falha = [0] * m
    comprimento = 0        # tamanho do prefixo-sufixo atual
    i = 1

    while i < m:
        if padrao[i] == padrao[comprimento]:
            comprimento += 1
            falha[i] = comprimento
            i += 1
        elif comprimento > 0:
            # Não avança i: apenas encurta o candidato e tenta de novo.
            comprimento = falha[comprimento - 1]
        else:
            falha[i] = 0
            i += 1

    return falha


def buscar_kmp(texto, padrao, primeira_apenas=False):
    """
    Encontra todas as ocorrências de `padrao` em `texto` pelo algoritmo KMP.

    Devolve um `ResultadoBusca` com as posições iniciais e o número de
    comparações de caractere efetuadas -- a instrumentação existe para o
    experimento do relatório, que compara o custo real contra a busca ingênua.

    Ocorrências sobrepostas são todas encontradas: procurar "aa" em "aaa"
    devolve as posições 0 e 1. Após um casamento completo o algoritmo continua
    de `falha[m-1]`, exatamente como faz numa falha comum.

    Complexidade: O(n + m) de tempo, O(m) de espaço.
    """
    n, m = len(texto), len(padrao)
    if m == 0 or m > n:
        return ResultadoBusca([], 0)

    falha = tabela_falha(padrao)
    ocorrencias = []
    comparacoes = 0

    i = 0   # ponteiro do texto  -- só avança
    j = 0   # ponteiro do padrão -- pode retroceder pela função de falha

    while i < n:
        comparacoes += 1
        if texto[i] == padrao[j]:
            i += 1
            j += 1
            if j == m:
                ocorrencias.append(i - m)
                if primeira_apenas:
                    break
                j = falha[j - 1]
        elif j > 0:
            j = falha[j - 1]      # desliza o padrão sem mexer em i
        else:
            i += 1                # falhou no primeiro caractere: só anda

    return ResultadoBusca(ocorrencias, comparacoes)


def buscar_ingenuo(texto, padrao, primeira_apenas=False):
    """
    Busca por força bruta, implementada apenas como termo de comparação.

    Testa o padrão em cada uma das n - m + 1 posições possíveis, reiniciando do
    zero a cada falha. Complexidade O(n * m) no pior caso.

    O contraste com o KMP fica evidente no experimento do `benchmark.py`: com
    texto "aaa...a" e padrão "aaa...ab", o número de comparações do ingênuo
    cresce com o produto n*m, enquanto o do KMP cresce linearmente com n.
    """
    n, m = len(texto), len(padrao)
    if m == 0 or m > n:
        return ResultadoBusca([], 0)

    ocorrencias = []
    comparacoes = 0

    for inicio in range(n - m + 1):
        j = 0
        while j < m:
            comparacoes += 1
            if texto[inicio + j] != padrao[j]:
                break
            j += 1
        if j == m:
            ocorrencias.append(inicio)
            if primeira_apenas:
                break

    return ResultadoBusca(ocorrencias, comparacoes)


def contexto_da_ocorrencia(texto, posicao, tamanho_padrao, margem=45):
    """
    Recorta um trecho ao redor da ocorrência, para exibir na interface.

    Não faz parte do algoritmo; é apoio de apresentação. Quebras de linha viram
    espaço para o trecho caber em uma linha do terminal.
    """
    inicio = max(0, posicao - margem)
    fim = min(len(texto), posicao + tamanho_padrao + margem)

    trecho = texto[inicio:fim].replace("\n", " ").replace("\r", " ")
    trecho = " ".join(trecho.split())

    if inicio > 0:
        trecho = "..." + trecho
    if fim < len(texto):
        trecho = trecho + "..."
    return trecho
