# Relatório Técnico

**Trabalho Prático A1 — Processamento e Busca de Textos**
Análise e Otimização de Sistemas — Universidade Veiga de Almeida

---

## Sumário

1. [Visão geral da solução](#1-visão-geral-da-solução)
2. [A Trie e suas operações](#2-a-trie-e-suas-operações)
3. [Autocomplete e busca por prefixo](#3-autocomplete-e-busca-por-prefixo)
4. [Pré-processamento do texto](#4-pré-processamento-do-texto)
5. [Vocabulário e índice invertido](#5-vocabulário-e-índice-invertido)
6. [Uso de Hash](#6-uso-de-hash)
7. [Complexidade das operações](#7-complexidade-das-operações)
8. [Exemplos de consultas e resultados](#8-exemplos-de-consultas-e-resultados)
9. [Questões conceituais da Parte I](#9-questões-conceituais-da-parte-i)
10. [Limitações da solução](#10-limitações-da-solução)
11. [Referências](#11-referências)

---

## 1. Visão geral da solução

O sistema tem duas partes que compartilham a mesma estrutura de dados. A
Parte I constrói uma Trie sobre um léxico de palavras e a usa para
autocomplete. A Parte II reaproveita essa mesma Trie: o vocabulário extraído
dos documentos é inserido nela, e a busca por prefixo passa a servir de porta
de entrada para o índice invertido.

O caminho percorrido por cada tipo de consulta:

```
  palavra exata    consulta ─► RSLP ─► radical ─► índice invertido (hash) ─► documentos

  prefixo          prefixo ─► Trie ─► termos ─► RSLP ─► índice (hash) ─► documentos

  sequência        padrão ─► KMP sobre o conteúdo original ─► posições nos arquivos
```

As três diferem em natureza, e essa diferença é o eixo de toda a análise deste
relatório. A primeira é uma consulta a tabela hash, de custo constante. A
segunda desce um caminho na árvore e varre a subárvore encontrada. A terceira
não usa nenhuma estrutura pré-construída: varre o texto bruto, em tempo linear
no tamanho do corpus.

### Números do corpus utilizado

| Métrica | Valor |
|---|---|
| Documentos processados | 24 |
| Palavras antes das stopwords | 98.718 |
| Palavras após a tokenização e remoção de stopwords | 52.756 |
| Termos distintos (vocabulário) | 10.656 |
| Palavras armazenadas na Trie | 10.595 |
| Radicais distintos no índice | 5.720 |
| Postagens (pares termo–documento) | 18.071 |

A diferença entre 10.656 termos distintos e 10.595 palavras na Trie vem da
normalização de acentos: formas como `análise` e `analise` compartilham a mesma
chave e ocupam um nó só.

### Tempos de construção

Mediana de 5 execuções consecutivas:

| Fase | Tempo | Fração |
|---|---|---|
| Leitura dos 24 arquivos | 6,4 ms | 2 % |
| Pré-processamento (tokenização + stopwords + RSLP) | 132,0 ms | 40 % |
| Construção da Trie | 31,8 ms | 10 % |
| Construção do índice invertido | 166,9 ms | 51 % |
| **Total** | **329,1 ms** | |

Duas observações metodológicas. A primeira: os 6,4 ms de leitura valem para
execuções com o cache de disco do sistema operacional já aquecido — na primeira
execução após o boot, a leitura dos mesmos arquivos custou cerca de **120 ms**,
vinte vezes mais. A segunda: quem domina a construção não é nenhuma das
estruturas de dados, e sim o **pré-processamento e a indexação**, que juntos
respondem por 91 % do tempo. Montar a Trie com 10.595 palavras custa menos de
um décimo do total.

---

## 2. A Trie e suas operações

Uma Trie, ou árvore de prefixos, armazena um conjunto de cadeias de forma que
**o caminho da raiz até um nó representa um prefixo**. Cada aresta carrega um
caractere; um nó marcado como fim de palavra indica que o caminho até ali é uma
palavra completa do conjunto.

A implementação está em `trie.py`. Cada nó guarda três campos:

```python
class NoTrie:
    __slots__ = ("filhos", "fim_de_palavra", "formas")
```

- `filhos` — dicionário `caractere → nó`;
- `fim_de_palavra` — marca o término de uma palavra válida;
- `formas` — as grafias originais associadas àquela chave.

O uso de `__slots__` não é detalhe cosmético: elimina o dicionário de atributos
que todo objeto Python carrega por padrão. Numa estrutura com 31.175 nós isso
representa uma economia substancial, e o consumo de memória é exatamente o
ponto fraco da Trie discutido na seção 9.

### Decisão de projeto: chave normalizada, exibição original

O português é uma língua acentuada, e isso cria um dilema. Se o acento fizesse
parte da chave, o prefixo `computa` encontraria `computador`, mas o usuário que
digitasse `computacao` não encontraria `computação`.

A solução separa as duas coisas:

- a **chave** que percorre a Trie é a forma normalizada — minúscula, sem acento;
- o **nó final** guarda o conjunto das grafias originais.

Assim `computação` é armazenada sob a chave `computacao`. Tanto `computa`
quanto `computaç` a encontram, e o resultado devolvido preserva a acentuação
correta.

Há um efeito colateral bem-vindo: ordenar pela chave normalizada reproduz
exatamente a ordem esperada no enunciado, porque `computacao` < `computacional`
< `computador` na ordem alfabética simples.

### Operações implementadas

| Método | Descrição |
|---|---|
| `inserir(palavra)` | percorre a chave criando os nós que faltarem; devolve `True` se a palavra é nova |
| `buscar(palavra)` | desce o caminho e verifica se o nó final está marcado como fim de palavra |
| `buscar_prefixo(prefixo, limite)` | desce o prefixo e coleta as palavras da subárvore, em ordem alfabética |
| `contar_prefixo(prefixo)` | conta as palavras sob o prefixo sem materializar a lista |
| `formas_de(palavra)` | devolve as grafias registradas para uma chave |
| `total_nos()`, `altura()` | métricas de memória e profundidade |

Um detalhe da busca exata merece destaque: **não basta o caminho existir**. O
prefixo `comp` é caminho de `computador`, mas só é uma palavra armazenada se
tiver sido inserido explicitamente. É a marcação `fim_de_palavra` que faz essa
distinção — sem ela, todo prefixo de toda palavra seria considerado uma palavra
do conjunto.

A coleta da subárvore em `_coletar` usa **pilha explícita, não recursão**. Uma
implementação recursiva desce um nível por caractere e estouraria o limite de
recursão do Python com chaves suficientemente longas.

### Trie comprimida (PATRICIA)

Também está implementada a variante comprimida, em que cada aresta guarda uma
**substring** em vez de um caractere. Cadeias de nós sem bifurcação — os sete
nós de `e-x-c-e-ç-ã-o` — colapsam em um único nó rotulado `excecao`.

Medição sobre o vocabulário real do corpus:

| Estrutura | Nós | Diferença |
|---|---|---|
| Trie tradicional | 31.175 | — |
| Trie comprimida (PATRICIA) | 14.040 | **−55,0 %** |

As duas devolvem resultados idênticos. A verificação é feita por teste
automatizado, que compara as duas implementações em 40 vocabulários gerados
aleatoriamente com prefixos compartilhados — o cenário em que a divisão de
arestas da PATRICIA tem mais chance de falhar.

---

## 3. Autocomplete e busca por prefixo

O autocomplete é a aplicação natural da Trie porque a estrutura **já organiza
as palavras por prefixo**. Não há trabalho de busca a fazer: o prefixo digitado
é literalmente um caminho na árvore.

O algoritmo tem duas etapas com custos distintos:

1. **Descer o prefixo** — segue um caractere por vez a partir da raiz. Se em
   algum ponto o caractere não existir entre os filhos, nenhuma palavra começa
   com aquele prefixo e a resposta é vazia. Custo O(m).

2. **Coletar a subárvore** — a partir do nó alcançado, uma busca em
   profundidade acumula todas as palavras abaixo dele. Cada nó visitado
   contribui com no máximo uma palavra. Custo O(p), com p = número de nós na
   subárvore.

O parâmetro `limite` interrompe a segunda etapa após k resultados. É uma
otimização com efeito prático grande: prefixos curtos alcançam subárvores
enormes — digitar `a` no vocabulário completo alcançaria milhares de palavras —
e um autocomplete real nunca precisa de mais que algumas dezenas de sugestões.
Com o limite, o custo cai para O(m + k).

### Integração com o índice invertido (seção 3.7.2 do enunciado)

Na Parte II a busca por prefixo ganha um segundo estágio. A Trie devolve os
termos do vocabulário; para cada termo, o índice invertido informa em que
documentos ele aparece:

```
prefixo "comp"
    │
    ├─► Trie ─► compilador, complexidade, computação, computador, ...
    │
    └─► para cada termo: RSLP ─► radical ─► índice (hash) ─► documentos
```

O custo total é O(m + p) na Trie mais O(1) por termo recuperado.

---

## 4. Pré-processamento do texto

As quatro etapas obrigatórias estão implementadas como funções separadas em
`preprocessamento.py`, de modo que o pipeline fique rastreável passo a passo.

| Etapa | Função | O que faz |
|---|---|---|
| 1 | `para_minusculas` | caixa baixa, para que `Algoritmo` e `algoritmo` sejam o mesmo termo |
| 2 | `remover_pontuacao` | pontuação e símbolos viram **espaço**, não string vazia |
| 3 | `tokenizar` | extrai sequências maximais de letras via expressão regular |
| 4 | `remover_stopwords` | descarta palavras vazias e tokens com menos de 2 caracteres |

A etapa 2 troca a pontuação por espaço, e não por nada, de propósito:
`banco-de-dados` precisa produzir três tokens, e não o amálgama
`bancodedados`.

A tokenização usa o padrão `[^\W\d_]+`, que significa "caractere de palavra que
não seja dígito nem sublinhado" — ou seja, apenas letras, **incluindo as
acentuadas**, porque o módulo `re` do Python opera em Unicode por padrão.
Números são descartados: `1998` e `x86` não têm prefixo linguístico útil para
um autocomplete.

Verificação com o exemplo do enunciado:

```
Entrada : "Os Algoritmos de Busca são muito importantes."
Saída   : algoritmos | busca | importantes
```

A remoção de stopwords elimina **46,6 %** dos tokens do corpus (de 98.718 para
52.756). São palavras que aparecem em praticamente todos os documentos e por
isso não discriminam nada — mas ocupam a maior parte do índice.

A comparação com a lista de stopwords é feita sobre a forma normalizada, o que
permite escrever `stopwords.txt` sem acentuação e ainda assim capturar `não`,
`está`, `você`.

### Etapa opcional: stemming com RSLP

O enunciado lista stemming como funcionalidade adicional. Neste trabalho ele
não é acessório — **é o que faz o exemplo da própria seção 3.7.1 funcionar**.

Naquele exemplo, o usuário digita `algoritmo` no singular e o sistema encontra
três arquivos. Mas o texto dos documentos traz `algoritmos` no plural. Sem
normalização morfológica, a consulta não retornaria nada.

O algoritmo escolhido é o **RSLP** (Removedor de Sufixos da Língua Portuguesa),
de Orengo e Huyck (SPIRE 2001). É a adaptação ao português do princípio
consolidado por Porter (1980) para o inglês — um dos artigos mais citados da
área de Recuperação de Informação, ainda hoje mantido no projeto Snowball e
usado por Lucene, Elasticsearch e Solr. O RSLP é o stemmer de referência da
língua portuguesa e é o algoritmo embutido no NLTK como `RSLPStemmer`.

O RSLP é baseado em regras, organizadas em oito passos aplicados em ordem. Cada
regra é uma quádrupla `(sufixo, tamanho_mínimo_do_radical, substituição,
exceções)`. Dentro de um passo, as regras são testadas do sufixo mais longo
para o mais curto e **apenas a primeira que casar é aplicada**:

```
se termina em "s"  ─► Passo 1: redução de plural
se termina em "a"  ─► Passo 2: redução de feminino
                      Passo 3: redução de advérbio  (-mente)
                      Passo 4: aumentativo/diminutivo/superlativo
                      Passo 5: sufixo nominal
se o passo 5 não mudou nada:
                      Passo 6: sufixo verbal
    se o passo 6 também não mudou:
                      Passo 7: vogal temática final
                      Passo 8: remoção de acentos
```

A condição de tamanho mínimo é o que impede o algoritmo de destruir palavras
curtas: a regra que remove o `s` final só se aplica se sobrarem pelo menos dois
caracteres.

**Efeito medido no corpus:**

| Métrica | Sem stemming | Com RSLP | Diferença |
|---|---|---|---|
| Chaves distintas no índice | 10.656 | 5.720 | −46,3 % |
| Formas por radical | 1,00 | 1,86 | — |

E na cobertura das consultas — quantos arquivos a mais cada consulta alcança:

| Consulta | Sem stemming | Com stemming | Ganho |
|---|---|---|---|
| `algoritmo` | 14 | 19 | +5 |
| `dado` | 14 | 24 | +10 |
| `programa` | 16 | 23 | +7 |
| `documento` | 4 | 9 | +5 |
| `informação` | 17 | 22 | +5 |
| `computador` | 19 | 23 | +4 |

**Observação honesta sobre o comportamento do RSLP.** O algoritmo é, por
projeto, agressivo: ele busca radicais úteis para indexação, não radicais
linguisticamente corretos. `informação` reduz a `informac` — que não é palavra
do português. Isso não é defeito para o uso pretendido, porque `informações`
também reduz a `informac`, e é a **igualdade entre as formas** que o índice
precisa, não a beleza do radical.

Um limite real do algoritmo aparece nas nominalizações em `-ção`: `computação`
vira `computac` enquanto `computador` vira `comput`, de modo que as duas
palavras **não** se encontram. Isso é comportamento do RSLP publicado, e foi
mantido fiel em vez de "corrigido", para que a implementação continue sendo o
algoritmo da literatura e não uma variante caseira.

As tabelas de regras reproduzem a estrutura publicada, mas as listas de
exceções foram reduzidas às palavras mais frequentes — as tabelas originais
somam algumas centenas de exceções levantadas manualmente pelos autores. O
efeito prático é um pouco mais de *over-stemming* em casos raros.

---

## 5. Vocabulário e índice invertido

### Vocabulário

Depois de processar todos os documentos, o conjunto das palavras distintas
encontradas forma o vocabulário — 10.656 termos no corpus utilizado. Esse
conjunto é inserido na Trie da Parte I, que passa a servir às duas partes do
trabalho.

A inserção é feita sobre o vocabulário **ordenado**, e não na ordem em que as
palavras apareceram. A razão é metodológica: garante que duas execuções sobre a
mesma pasta produzam exatamente a mesma estrutura, tornando as medições de
tempo comparáveis entre si.

### Por que "invertido"

O índice natural de uma coleção de textos é o índice **direto**: documento →
palavras que ele contém. É assim que o arquivo está gravado no disco. Responder
"em quais arquivos aparece a palavra X" com esse índice obriga a abrir e varrer
todos os documentos — custo O(N).

O índice **invertido** troca o papel de chave e valor: palavra → documentos em
que ela ocorre. A relação armazenada é a mesma, lida na direção oposta — daí o
nome. Com ele, a mesma pergunta vira uma única consulta a tabela hash.

```
índice direto      algoritmos.txt ─► {algoritmo, busca, dados, complexidade, ...}
índice invertido   algoritmo      ─► {algoritmos.txt, complexidade_computacional.txt, ...}
```

É a estrutura central de todo motor de busca desde os anos 1960, e continua
sendo o que Lucene, Elasticsearch e Solr usam por baixo.

### Estrutura adotada

O índice é um dicionário de dicionários:

```python
{termo: {documento: frequência}}
```

Guardar a **frequência**, e não apenas o conjunto de documentos, é o que torna
possível ranquear os resultados. O custo extra de memória é pequeno e habilita
TF-IDF e BM25.

O sistema mantém **dois** índices em paralelo:

| Índice | Chave | Para quê |
|---|---|---|
| `por_termo` | palavra exata do texto | atende literalmente ao que a seção 3.5 pede |
| `por_radical` | radical produzido pelo RSLP | faz `algoritmo` encontrar `algoritmos` |

Manter os dois custa pouco e permite comparar as duas estratégias lado a lado —
é de onde vem a tabela de cobertura da seção 4.

### Ranqueamento: BM25

O índice responde **quais** documentos contêm o termo, mas não em que **ordem**
apresentá-los. Para isso foram implementadas duas funções de pontuação.

**TF-IDF** parte da intuição de Spärck Jones (1972): um termo raro na coleção é
mais informativo que um termo comum.

**BM25** (Robertson et al., TREC-3, 1994) corrige duas fraquezas do TF-IDF puro:

```
                       f(t,D) · (k₁ + 1)
score(D,Q) = Σ IDF(t) · ─────────────────────────────────────
             t∈Q        f(t,D) + k₁ · (1 − b + b · |D|/avgdl)
```

- **saturação (k₁ = 1,5)** — repetir a palavra ajuda, mas com retorno
  decrescente: de 1 para 2 ocorrências o ganho é grande, de 20 para 21 é quase
  nulo;
- **normalização (b = 0,75)** — documentos mais longos que a média têm o score
  reduzido, porque acumulam ocorrências apenas por serem grandes.

O IDF usado é a formulação probabilística com a correção do Lucene:

```
IDF(t) = ln( (N − df + 0,5) / (df + 0,5) + 1 )
```

O `+1` dentro do logaritmo não é detalhe de implementação. Sem ele, um termo
presente em mais da metade da coleção receberia peso **negativo**, e um
documento perderia pontos por conter a palavra buscada.

**Achado experimental.** O corpus expõe justamente esse problema no TF-IDF. O
radical `dad` (de "dados") ocorre nos **24 documentos**, ou seja, df = N. O
TF-IDF calcula log₁₀(N/df) = log₁₀(1) = **0** e zera a consulta inteira — todos
os documentos empatam em 0,00 e a ordem exibida passa a ser meramente
alfabética. O BM25, com o `+1`, continua discriminando e coloca
`banco_dados.txt`, `big_data.txt` e `ciencia_de_dados.txt` no topo.

Trinta anos depois de publicado, o BM25 segue sendo a linha de base obrigatória
contra a qual todo modelo neural de recuperação é comparado — o benchmark BEIR
(Thakur et al., NeurIPS 2021) mostrou o BM25 superando vários modelos densos em
cenários fora do domínio de treino.

---

## 6. Uso de Hash

O índice invertido usa o `dict` do Python, como o enunciado autoriza. Para
tornar visível o que o `dict` faz por baixo — e para **medir** o fenômeno das
colisões em vez de apenas descrevê-lo — o projeto inclui também uma tabela hash
própria, em `indice_invertido.py`.

### Função hash

Uma função hash mapeia uma chave de tamanho arbitrário para um inteiro em um
intervalo fixo `[0, capacidade)`. A implementação usa a **hash polinomial**,
avaliada pelo esquema de Horner — a mesma família empregada em `String.hashCode`
do Java:

```
h(s) = (s[0]·B^(m−1) + s[1]·B^(m−2) + ... + s[m−1]) mod C
```

A base B é um primo ímpar (31), o que espalha bem cadeias parecidas: `casa` e
`caso` caem em posições distantes apesar de diferirem em uma única letra. A
máscara `& 0xFFFFFFFF` mantém o acumulador em 32 bits — sem ela, o Python
cresceria o inteiro indefinidamente e a operação deixaria de ser O(1) por
caractere.

Custo de calcular a hash: **O(m)**, no tamanho da chave. Como as palavras têm
tamanho limitado — nenhuma tem 500 letras — esse fator é tratado como constante
na análise, e a busca é considerada O(1).

### Colisões

Como o conjunto de chaves possíveis é infinito e o de posições é finito, duas
chaves distintas inevitavelmente vão para a mesma posição. Isso é uma
**colisão**, e não é defeito da função: é consequência do princípio da casa dos
pombos. O que se pode fazer é tratá-la bem.

A estratégia adotada é o **encadeamento separado**: cada posição guarda uma
lista de pares `(chave, valor)`, e a busca percorre essa lista.

### Complexidade e o fator de carga

Com função hash de boa dispersão e fator de carga α = n/C mantido baixo, o
comprimento médio das listas é α, e a busca custa **O(1 + α) = O(1) em média**.
No pior caso — todas as chaves colidindo na mesma posição — a tabela degenera
em lista ligada e a busca vira **O(n)**.

Medição com os 5.720 termos reais do índice:

| Capacidade | Fator de carga α | Colisões | Maior cadeia | Cadeia média |
|---|---|---|---|---|
| 512 | 11,172 | 5.208 | 23 | 11,172 |
| 2.048 | 2,793 | 3.788 | 11 | 2,961 |
| 8.192 | 0,698 | 1.596 | 6 | 1,387 |
| 32.768 | 0,175 | 482 | 3 | 1,092 |

A cadeia média acompanha o fator de carga quase exatamente — é o α da análise
clássica, medido. É por isso que a tabela **redimensiona** quando α ultrapassa
0,75: dobrar a capacidade e reinserir tudo custa O(n), mas acontece cada vez
mais raramente conforme a tabela cresce. Diluído sobre as n inserções, o custo
**amortizado** por inserção continua O(1) — o mesmo argumento que sustenta o
`append` de listas dinâmicas.

### Comparação com o `dict` nativo

| Estrutura | 2.000 buscas |
|---|---|
| Tabela própria (Python puro) | 1,67 ms |
| `dict` nativo (C) | 0,08 ms |
| Razão | **20,6×** |

Mesma complexidade assintótica nos dois casos. A diferença é o **fator
constante**: o `dict` é implementado em C e usa endereçamento aberto. É um bom
lembrete de que a notação O esconde constantes que importam muito na prática —
e é por isso que o sistema opera sobre o `dict` e a tabela própria fica
reservada à demonstração.

---

## 7. Complexidade das operações

Notação: **m** = tamanho da palavra, **n** = tamanho do texto, **V** = tamanho
do vocabulário, **N** = total de tokens do corpus, **D** = número de
documentos, **p** = nós abaixo de um prefixo, **k** = resultados devolvidos.

### Tabela geral

| Operação | Melhor caso | Caso médio | Pior caso | Espaço |
|---|---|---|---|---|
| Trie: inserir | O(m) | O(m) | O(m) | O(m) por palavra nova |
| Trie: buscar exata | O(1) | O(m) | O(m) | O(1) |
| Trie: buscar prefixo | O(m) | O(m + p) | O(m + p) | O(k) |
| Trie: buscar prefixo com limite | O(m) | O(m + k) | O(m + k) | O(k) |
| Hash: inserir | O(1) | O(1) | O(n) | O(1) |
| Hash: buscar | O(1) | O(1) | O(n) | O(1) |
| Índice: consulta exata | O(1) | O(1) | O(n) | O(d) |
| Índice: ranquear BM25 | O(q) | O(q·d) | O(q·D) | O(D) |
| KMP: função de falha | O(m) | O(m) | O(m) | O(m) |
| KMP: busca no texto | O(n) | O(n + m) | O(n + m) | O(m) |
| Busca ingênua | O(n) | O(n·m) | O(n·m) | O(1) |
| RSLP: radicalizar | O(1) com cache | O(m) | O(R·m) | O(V) do cache |
| Construção completa | — | O(N + V·m) | O(N + V·m) | O(N) |

### Por que a busca na Trie é O(m) e não depende de V

Este é o ponto central da estrutura. A busca desce um nível por caractere da
palavra. O número de passos é o comprimento da palavra — e **nada mais**. Se o
vocabulário tiver mil ou um milhão de palavras, buscar `computador` continua
custando dez passos.

O que muda com o vocabulário é a **largura** dos nós, não a profundidade do
caminho. E consultar um filho é uma operação de dicionário, O(1) em média.

**Verificação experimental** (experimento 1 do `benchmark.py`), com o número de
resultados fixado em 10 por prefixo para isolar o efeito de V:

| Vocabulário | Resultados | Trie | Lista sequencial | Ganho |
|---|---|---|---|---|
| 1.332 | 9 | 17,1 µs | 11.548 µs | 675× |
| 2.664 | 23 | 38,8 µs | 23.360 µs | 602× |
| 5.328 | 23 | 33,8 µs | 44.127 µs | 1.304× |
| 10.656 | 73 | 100,7 µs | 74.805 µs | 743× |

A comparação decisiva está entre a **segunda e a terceira linha**: o vocabulário
dobra, o número de resultados fica igual, e o tempo da Trie **não sobe** (38,8 →
33,8 µs, dentro da variação de medição) enquanto o da lista **dobra** junto com
V (23.360 → 44.127 µs). É a demonstração controlada de que o custo da Trie é
O(m + p) e o da varredura é O(V·m).

### Por que o KMP é linear

A busca ingênua, ao falhar na posição j do padrão, joga fora tudo o que já
tinha descoberto e recomeça uma posição adiante no texto. O KMP observa que os j
caracteres já casados **são conhecidos** — são exatamente os j primeiros do
padrão — e portanto dá para calcular de antemão, olhando só o padrão, quanto é
seguro deslocar sem perder ocorrência nenhuma.

Esse cálculo é a **função de falha**: `falha[j]` é o comprimento do maior
prefixo próprio de `padrao[0..j]` que também é sufixo dele. Para `ababc`:

| j | trecho | maior prefixo = sufixo | `falha[j]` |
|---|---|---|---|
| 0 | `a` | — | 0 |
| 1 | `ab` | — | 0 |
| 2 | `aba` | `a` | 1 |
| 3 | `abab` | `ab` | 2 |
| 4 | `ababc` | — | 0 |

**A prova de linearidade é um argumento de amortização**, e é o detalhe mais
elegante do algoritmo. Duas observações bastam:

- o ponteiro `i` do texto **só avança, nunca retrocede** — no máximo n
  incrementos;
- o ponteiro `j` do padrão cresce no máximo 1 por incremento de `i`, e cada
  retrocesso via função de falha o diminui em pelo menos 1.

Como `j` nunca fica negativo, o total de retrocessos não pode exceder o total de
incrementos. Somando, o laço executa no máximo **2n** vezes.

**Verificação experimental** — pior caso construído, texto `aaa...a` e padrão
`aaa...ab` com m = 60:

| n | KMP (comparações) | Ingênuo (comparações) | Razão |
|---|---|---|---|
| 2.000 | 3.941 | 116.460 | 29,6× |
| 4.000 | 7.941 | 236.460 | 29,8× |
| 8.000 | 15.941 | 476.460 | 29,9× |
| 16.000 | 31.941 | 956.460 | 29,9× |

As comparações do KMP são exatamente ≈ 2n, confirmando o limite teórico.
Dobrando n, ambos dobram — mas a razão entre eles permanece em ≈ m/2, que é o
fator que a busca ingênua perde.

**Em texto natural a vantagem encolhe drasticamente:**

| Padrão | Ocorrências | KMP | Ingênuo | Razão |
|---|---|---|---|---|
| `rede neural` | 53 | 711.492 | 720.617 | 1,01× |
| `chave pública` | 31 | 697.740 | 699.112 | 1,00× |
| `complexidade computacional` | 14 | 697.760 | 711.451 | 1,02× |

O motivo é que, em texto real, o alfabeto é grande e as falhas acontecem no
primeiro ou segundo caractere — a força bruta quase nunca atinge seu pior caso.
Este é um resultado importante e vale registrá-lo com honestidade: **a vantagem
do KMP não é velocidade média em texto natural, é garantia**. O limite O(n+m)
vale para qualquer entrada, inclusive as adversariais, e é isso que permite usar
o algoritmo sem medo de um caso patológico.

### Escalabilidade da indexação

Previsão: O(N) no total de tokens. Se valer, o tempo **por mil tokens** deve
ficar aproximadamente constante conforme o corpus cresce.

| Documentos | Tokens | Trie (ms) | Índice (ms) | Total (ms) | µs / 1k tokens |
|---|---|---|---|---|---|
| 6 | 12.381 | 11,9 | 50,9 | 104,1 | 8.407 |
| 12 | 29.108 | 20,4 | 93,0 | 216,5 | 7.439 |
| 18 | 41.126 | 37,5 | 121,5 | 313,4 | 7.621 |
| 24 | 52.756 | 29,3 | 151,8 | 357,3 | 6.773 |

O corpus quadruplica e o custo normalizado permanece na mesma faixa,
confirmando o comportamento linear previsto.

---

## 8. Exemplos de consultas e resultados

### 8.1 Autocomplete por prefixo (Parte I)

```
Digite o prefixo: comp

Palavras encontradas:
  compacidade
  compacta
  compacto
  companhia
  comparação
  compartilhamento
  compatibilidade
  compilador
  complexidade
  computação
  computador
  ...
  ... e mais 111 (exibindo 40 de 151)

Tempo da consulta: 442.5 us
```

Reproduzindo exatamente o exemplo da seção 2.2 do enunciado, com apenas as oito
palavras cadastradas:

```
Digite um prefixo: comp
Palavras encontradas: compilador, complexidade, computação, computacional, computador
```

A ordem coincide com a esperada, incluindo `computação` antes de
`computacional` — consequência de ordenar pela chave normalizada.

### 8.2 Consulta por palavra exata (seção 3.7.1)

```
Digite a palavra: algoritmo

Encontrada em 19 arquivo(s):
  - algoritmos.txt                               79 ocorrência(s)   BM25 0.614
  - complexidade_computacional.txt               51 ocorrência(s)   BM25 0.601
  - computacao_quantica.txt                      61 ocorrência(s)   BM25 0.594
  - aprendizado_de_maquina.txt                   31 ocorrência(s)   BM25 0.593
  - criptografia.txt                             53 ocorrência(s)   BM25 0.591
  - processamento_linguagem_natural.txt          15 ocorrência(s)   BM25 0.565
  ...

  Sem stemming a forma exata 'algoritmo' apareceria em 14 arquivo(s).
  O radical 'algoritm' (RSLP) alcança 19, reunindo as variantes da palavra.

Tempo da consulta: 46.5 us
```

Observe que `algoritmos.txt` fica em primeiro apesar de `computacao_quantica.txt`
ter frequência parecida (79 contra 61): o BM25 penaliza o documento mais longo,
que acumula ocorrências por tamanho.

### 8.3 Consulta por prefixo integrada ao índice (seção 3.7.2)

```
Digite o prefixo: comp

Palavras encontradas:
  compacidade                ->  1 documento(s)
  compacta                   ->  2 documento(s)
  compacto                   ->  2 documento(s)
  companhia                  ->  1 documento(s)
  compaq                     ->  1 documento(s)
  compara                    ->  6 documento(s)
  comparação                 ->  8 documento(s)
  comparações                ->  8 documento(s)
  comparadas                 ->  8 documento(s)
  comparado                  ->  8 documento(s)
  ...
  compartilha                -> 12 documento(s)
  compartilhada              -> 12 documento(s)
  ... exibindo 25 de 151 termos

Documentos que contêm algum desses termos: 22
  - aprendizado_de_maquina.txt                 BM25 8.226
  - processamento_linguagem_natural.txt        BM25 5.005
  - internet_das_coisas.txt                    BM25 4.259
  - aprendizagem_profunda.txt                  BM25 4.139
  - computacao_nuvem.txt                       BM25 3.906

Tempo da consulta: 218.6 us
```

Repare que `comparação`, `comparações`, `comparadas`, `comparado` e as demais
variantes reportam sempre **8 documentos**: são formas diferentes que o RSLP
reduz ao mesmo radical, e portanto consultam a mesma entrada do índice. A Trie
preserva as grafias para exibição, o índice as unifica para a busca.

### 8.4 Consulta por sequência com KMP (seção 3.7.3 — bônus)

```
Digite a sequência: chave pública

31 ocorrência(s) em 2 arquivo(s):

  criptografia.txt (29 ocorrência(s))
      ...métricos. Os sistemas assimétricos usam uma "chave pública" para cifrar
         uma mensagem e uma "chave privada"...
      ...A vantagem dos sistemas assimétricos é que a chave pública pode ser
         publicada livremente, permitindo que...

  computacao_quantica.txt (2 ocorrência(s))
      ...implicações profundas para a criptografia de chave pública, já que
         muitos sistemas de segurança atuais...

  Comparações de caractere feitas pelo KMP: 697.716

Tempo da consulta: 73.829 ms
```

### 8.5 O contraste que resume o trabalho

| Consulta | Estrutura usada | Custo teórico | Tempo medido |
|---|---|---|---|
| `algoritmo` (palavra exata) | índice invertido (hash) | O(1) | **46,5 µs** |
| `comp` (prefixo, 25 termos) | Trie + índice | O(m + p) | **218,6 µs** |
| `chave pública` (sequência) | KMP sobre o texto bruto | O(N) | **73.829 µs** |

A consulta indexada é cerca de **1.600 vezes** mais rápida que a varredura do
corpus. Essa razão não é uma constante do sistema: ela **cresce com o tamanho
do corpus**, porque um lado é constante e o outro é linear. Dobrar o número de
documentos deixaria a busca por hash igual e dobraria o tempo do KMP.

É exatamente por isso que motores de busca investem em construir índices: paga-
se um custo alto uma vez, na indexação, para tornar cada consulta barata. No
corpus deste trabalho, os 329 ms de construção se pagam a partir da **quinta**
consulta — e o ponto de equilíbrio chega ainda mais cedo à medida que o corpus
cresce, porque a economia por consulta cresce junto com ele.

---

## 9. Questões conceituais da Parte I

### 9.1 Por que uma Trie é adequada para sistemas de autocomplete?

Porque a estrutura **já está organizada pela informação que o autocomplete
usa**: o prefixo digitado é literalmente um caminho na árvore. Não há busca a
fazer no sentido usual — basta descer o caminho e ler o que está abaixo.

Três propriedades tornam o encaixe natural:

1. **Localizar o prefixo custa O(m)**, independente do tamanho do léxico.
2. **Todas as palavras com aquele prefixo estão na subárvore alcançada**, e em
   nenhum outro lugar. Não é preciso examinar mais nada da estrutura.
3. **A ordem alfabética sai de graça**, percorrendo os filhos em ordem de
   caractere — o autocomplete não precisa de um passo de ordenação.

Some-se a isso o comportamento incremental: quando o usuário digita mais uma
letra, o sistema pode partir do nó onde parou em vez de recomeçar da raiz.

### 9.2 Qual a vantagem de uma Trie em relação à busca sequencial em uma lista?

A vantagem está em **de que grandeza o custo depende**.

| | Busca sequencial | Trie |
|---|---|---|
| Custo por prefixo | O(V · m) | O(m + p) |
| Depende do tamanho do léxico? | **Sim** | **Não** |
| Depende do que é devolvido? | Não | Sim |

A busca sequencial testa toda palavra da lista, inclusive as milhares que não
têm relação nenhuma com o prefixo. A Trie descarta esses ramos inteiros já no
primeiro caractere que não casa.

Medido no corpus deste trabalho, com 10.656 palavras: **74.805 µs** para a
lista contra **100,7 µs** para a Trie — cerca de **743 vezes** mais rápido. E a
distância aumenta com o léxico, porque só um dos dois lados cresce.

Vale registrar o outro lado: a Trie é vantajosa para busca por **prefixo**. Para
busca **exata**, uma tabela hash é ainda melhor, com O(1) contra O(m) — mas a
hash não sabe responder nada sobre prefixos. É por isso que este trabalho usa as
duas: Trie para prefixos, hash para termos exatos.

### 9.3 Como palavras com prefixos comuns são representadas na Trie?

Elas **compartilham fisicamente o mesmo caminho** desde a raiz até o ponto em
que divergem. O prefixo comum é armazenado uma única vez.

Com `computador`, `computação` e `computacional`:

```
raiz ─ c ─ o ─ m ─ p ─ u ─ t ─ a ─ c ─┬─ a ─ o •            (computação)
                                       │
                                       ├─ i ─ o ─ n ─ a ─ l • (computacional)
                                       │
                       (de "computa") ─┴─ d ─ o ─ r •        (computador)
```

Os oito primeiros nós são compartilhados pelas três palavras. O `•` marca os nós
com `fim_de_palavra = True`.

Daí decorrem duas consequências importantes. A primeira é a **economia**:
armazenar as três palavras separadamente custaria 34 caracteres; na Trie custa
19 nós. A segunda é que **um nó pode ser fim de palavra e ter filhos ao mesmo
tempo** — se `computa` também fosse inserida, o nó do `a` seria marcado sem
deixar de ser caminho para as outras três.

### 9.4 Qual a complexidade de busca de uma palavra de tamanho m?

**O(m)** — e, decisivamente, **independente do número de palavras armazenadas**.

O algoritmo executa m passos, um por caractere. Cada passo é uma consulta ao
dicionário de filhos, O(1) em média. A busca também pode terminar **antes** de m
passos, assim que um caractere não for encontrado — no caso de `zzz` num
vocabulário sem palavras iniciadas em `z`, a busca falha no primeiro passo.

Uma ressalva de rigor: a análise trata a consulta ao dicionário de filhos como
O(1), o que vale no caso médio. Com uma função hash adversarial o pior caso
seria O(σ) por nó, com σ = tamanho do alfabeto — mas σ é constante, então o
limite O(m) se mantém.

Comparando com as alternativas para busca exata:

| Estrutura | Custo | Observação |
|---|---|---|
| Lista não ordenada | O(V · m) | precisa testar tudo |
| Lista ordenada + busca binária | O(m · log V) | log V comparações de m caracteres |
| Tabela hash | O(m) para calcular a hash, O(1) de acesso | **não responde por prefixo** |
| **Trie** | **O(m)** | **e responde por prefixo** |

### 9.5 Que problema de memória pode ocorrer em uma Trie tradicional?

O problema é o **desperdício em nós de filho único**.

A Trie tradicional aloca **um objeto por caractere**, mesmo quando aquele nó não
representa decisão alguma. Uma palavra rara como `paralelepípedo` não compartilha
nada depois de `paralel`, mas ainda assim ocupa sete nós encadeados, cada um com
exatamente um filho. Cada nó desses carrega um objeto Python e um dicionário —
dezenas de bytes de estrutura para armazenar um caractere.

Medido no corpus:

| Métrica | Valor |
|---|---|
| Palavras armazenadas | 10.595 |
| Caracteres totais | 87.733 |
| Nós alocados | 31.175 |
| **Nós por palavra** | **2,94** |

Note que 31.175 nós para 87.733 caracteres já mostra o compartilhamento
funcionando — os prefixos comuns economizam 64 % do que seria o pior caso. Mas
os 31.175 nós ainda são muito mais do que as 10.595 palavras, e a maior parte
desse excedente é justamente cadeia de filho único.

O problema se agrava em dois cenários: **alfabetos grandes** (Unicode completo,
em vez das ~40 letras do português) e **vocabulários esparsos**, com poucas
palavras longas e pouco prefixo em comum — o caso de identificadores, URLs ou
sequências de DNA.

### 9.6 O que é uma Trie comprimida e como ela reduz esse problema?

Uma **Trie comprimida** — também chamada de árvore radix, ou PATRICIA na
formulação de Morrison (1968) — colapsa toda cadeia de nós de filho único em um
**único nó rotulado com a substring correspondente**.

A aresta deixa de carregar um caractere e passa a carregar um pedaço de texto:

```
Trie tradicional            Trie comprimida
  e                           ┌────────────┐
  └ x                         │  "excecao" │
    └ c                       └────────────┘
      └ e
        └ c                   1 nó
          └ a
            └ o

7 nós
```

A estrutura é mantida por meio da **divisão de arestas**: ao inserir uma palavra
que diverge no meio de um rótulo, o nó é partido em dois e um novo ramo é criado
a partir do ponto de divergência. As três situações possíveis — rótulo consumido
por inteiro, chave terminando no meio do rótulo, e divergência no meio — estão
tratadas em `TrieComprimida.inserir`.

**Resultado medido no vocabulário real:**

| Estrutura | Nós | Nós por palavra |
|---|---|---|
| Trie tradicional | 31.175 | 2,94 |
| Trie comprimida | 14.040 | 1,32 |
| **Economia** | **−55,0 %** | |

O ganho vem inteiramente das cadeias de filho único, que somem. O número de nós
cai para pouco mais de um por palavra armazenada — próximo do mínimo teórico,
que seria exatamente um nó por palavra mais os nós de bifurcação.

**O que a compressão não muda:**

- A **linguagem reconhecida** é idêntica. Verificado por teste automatizado que
  compara as duas implementações em 40 vocabulários aleatórios.
- A **complexidade assintótica** continua O(m) para inserir e buscar. Comparar
  uma substring de tamanho ℓ custa O(ℓ), e a soma dos ℓ percorridos é no máximo
  m.

Na prática a comprimida ainda tende a ser mais **rápida**, não só mais enxuta,
porque visita menos objetos e aproveita melhor a cache do processador — no
experimento 2, o mesmo lote de consultas por prefixo custou **200,6 µs** na
comprimida contra **288,3 µs** na tradicional, cerca de 30 % a menos. A
construção, por outro lado, é mais cara (40,7 ms contra 33,2 ms), porque cada
inserção pode exigir divisão de aresta.

**Custo da escolha:** o código é bem mais complexo. A Trie tradicional insere em
quinze linhas; a comprimida precisa tratar três casos de divisão de aresta, e é
onde erros de implementação se escondem. É a razão de o sistema em produção usar
a tradicional e manter a comprimida como estrutura de comparação.

A ideia continua viva na pesquisa e na indústria: o **Adaptive Radix Tree**
(Leis, Kemper & Neumann, ICDE 2013) é usado em bancos de dados em memória, há
uma *radix tree* no kernel do Linux, e a estrutura `rax` do Redis é uma árvore
radix.

---

## 10. Limitações da solução

### 10.1 Índice inteiramente em memória

Todas as estruturas vivem na RAM e são reconstruídas a cada execução. Para os 24
documentos deste trabalho isso custa ~330 ms e é irrelevante. Para milhões de
documentos seria inviável em duas frentes: a memória não comportaria o índice, e
reconstruir tudo a cada inicialização levaria horas.

A solução usada por sistemas reais é a **persistência com atualização
incremental**: gravar o índice em disco e adicionar apenas os documentos novos.
O Lucene resolve isso com segmentos imutáveis que são periodicamente fundidos.

### 10.2 O `-ção` do RSLP

Como discutido na seção 4, `computação` reduz a `computac` enquanto `computador`
reduz a `comput`, de modo que as duas palavras não se encontram na busca. É
comportamento do algoritmo publicado, mantido fiel de propósito, mas é um limite
real de cobertura.

Um **lematizador** resolveria melhor, por trabalhar com dicionário e classe
gramatical em vez de recorte de sufixos — ao custo de precisar de um léxico
morfológico do português e de análise sintática.

### 10.3 Consultas de um termo só

O ranqueamento BM25 aceita múltiplos termos, mas a interface aceita apenas uma
palavra por consulta. Não há suporte a operadores booleanos (`E`, `OU`, `NÃO`)
nem a busca por frase com termos indexados.

A infraestrutura para isso já existe — a interseção de conjuntos de documentos é
direta, e a busca por frase precisaria apenas armazenar as **posições** de cada
ocorrência no índice, e não só a frequência.

### 10.4 Sem tolerância a erro de digitação

`algoritmo` encontra os documentos; `algortimo` não encontra nada. Nem a Trie nem
a hash toleram a troca de duas letras.

O tratamento clássico é a **busca aproximada por distância de edição**
(Levenshtein, 1966), que pode inclusive ser feita sobre a própria Trie com
programação dinâmica, mantendo uma linha da matriz por nó visitado. É uma
extensão natural desta implementação.

### 10.5 Busca por sequência é linear no corpus

A consulta com KMP varre o conteúdo de todos os documentos a cada chamada:
73,8 ms contra 46,5 µs da consulta indexada. Nenhuma pré-computação é aproveitada.

Estruturas como o **array de sufixos** ou o **índice FM** (Ferragina & Manzini,
2000) responderiam a consultas de substring em tempo proporcional ao padrão, e
não ao texto — ao custo de uma construção bem mais cara e de mais memória.

Para múltiplos padrões simultâneos, o **Aho–Corasick** (1975) seria a evolução
direta do KMP aqui implementado: ele generaliza a mesma função de falha para um
autômato que busca todos os padrões em uma única passada.

### 10.6 Corpus pequeno para conclusões definitivas

99.500 palavras em 24 documentos permitem observar as tendências, mas não
esgotam a análise. As medições de tempo em escala de microssegundos ficam
próximas do ruído do escalonador do sistema operacional — o `benchmark.py`
mitiga isso com lotes e mediana, mas variações de 10-15 % entre execuções
permanecem, como se vê nas tabelas da seção 7.

### 10.7 Stopwords fixas e dependentes de língua

A lista de stopwords é estática e específica do português. Um corpus em inglês
passaria praticamente intacto pelo filtro. Uma alternativa independente de língua
seria derivar as stopwords do próprio corpus, descartando os termos de maior
frequência documental — precisamente o que o IDF já faz de forma contínua, sem
precisar de corte binário.

---

## 11. Referências

**Estruturas de dados**

- FREDKIN, E. Trie Memory. *Communications of the ACM*, v. 3, n. 9, p. 490–499, 1960.
- MORRISON, D. R. PATRICIA — Practical Algorithm To Retrieve Information Coded in Alphanumeric. *Journal of the ACM*, v. 15, n. 4, p. 514–534, 1968.
- BENTLEY, J. L.; SEDGEWICK, R. Fast Algorithms for Sorting and Searching Strings. In: *SODA '97*, p. 360–369, 1997.
- LEIS, V.; KEMPER, A.; NEUMANN, T. The Adaptive Radix Tree: ARTful Indexing for Main-Memory Databases. In: *ICDE 2013*, p. 38–49, 2013.
- KNUTH, D. E. *The Art of Computer Programming*, v. 3: Sorting and Searching. 2. ed. Addison-Wesley, 1998. (cap. 6.3 sobre buscas digitais e 6.4 sobre hashing)

**Casamento de cadeias**

- MORRIS, J. H.; PRATT, V. R. *A linear pattern-matching algorithm*. Technical Report 40, University of California, Berkeley, 1970.
- KNUTH, D. E.; MORRIS, J. H.; PRATT, V. R. Fast Pattern Matching in Strings. *SIAM Journal on Computing*, v. 6, n. 2, p. 323–350, 1977.
- AHO, A. V.; CORASICK, M. J. Efficient String Matching: An Aid to Bibliographic Search. *Communications of the ACM*, v. 18, n. 6, p. 333–340, 1975.
- CROCHEMORE, M.; PERRIN, D. Two-way string-matching. *Journal of the ACM*, v. 38, n. 3, p. 650–674, 1991.
- FERRAGINA, P.; MANZINI, G. Opportunistic Data Structures with Applications. In: *FOCS 2000*, p. 390–398, 2000.

**Recuperação de informação**

- SPÄRCK JONES, K. A statistical interpretation of term specificity and its application in retrieval. *Journal of Documentation*, v. 28, n. 1, p. 11–21, 1972.
- ROBERTSON, S. E.; SPÄRCK JONES, K. Relevance weighting of search terms. *Journal of the American Society for Information Science*, v. 27, n. 3, p. 129–146, 1976.
- ROBERTSON, S. E. et al. Okapi at TREC-3. In: *Proceedings of the Third Text REtrieval Conference (TREC-3)*, p. 109–126, 1994.
- ROBERTSON, S. E.; ZARAGOZA, H. The Probabilistic Relevance Framework: BM25 and Beyond. *Foundations and Trends in Information Retrieval*, v. 3, n. 4, p. 333–389, 2009.
- THAKUR, N. et al. BEIR: A Heterogeneous Benchmark for Zero-shot Evaluation of Information Retrieval Models. In: *NeurIPS 2021 Datasets and Benchmarks Track*, 2021.
- MANNING, C. D.; RAGHAVAN, P.; SCHÜTZE, H. *Introduction to Information Retrieval*. Cambridge University Press, 2008.

**Processamento de linguagem natural**

- PORTER, M. F. An algorithm for suffix stripping. *Program*, v. 14, n. 3, p. 130–137, 1980.
- ORENGO, V. M.; HUYCK, C. A Stemming Algorithm for the Portuguese Language. In: *SPIRE 2001*, p. 186–193, IEEE Computer Society, 2001.
- LEVENSHTEIN, V. I. Binary codes capable of correcting deletions, insertions, and reversals. *Soviet Physics Doklady*, v. 10, n. 8, p. 707–710, 1966.
