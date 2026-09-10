# Processamento e Busca de Textos

Trabalho Prático A1 — **Análise e Otimização de Sistemas**
Universidade Veiga de Almeida

Sistema de autocomplete com **Trie** e mini mecanismo de busca sobre arquivos
de texto, com **índice invertido**, **tabela hash**, **stemming RSLP**,
**ranqueamento BM25** e busca por sequência com **Knuth–Morris–Pratt**.

Escrito em Python usando **apenas a biblioteca padrão** — nenhuma dependência
externa para instalar, e nenhuma biblioteca pronta de Trie, índice invertido ou
motor de busca, conforme a restrição do enunciado.

---

## Sumário

- [Início rápido](#início-rápido)
- [O que o sistema faz](#o-que-o-sistema-faz)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Como usar](#como-usar)
- [Exemplos de sessão](#exemplos-de-sessão)
- [Experimentos de complexidade](#experimentos-de-complexidade)
- [Testes](#testes)
- [Algoritmos implementados](#algoritmos-implementados)
- [Base de documentos](#base-de-documentos)

---

## Início rápido

Requer **Python 3.8 ou superior**. Nada mais.

```bash
git clone <url-do-repositorio>
cd <pasta-do-repositorio>

python main.py
```

O repositório já vem com os 24 documentos de teste em `documentos/` e o léxico
em `palavras.txt`, então o programa roda direto após o clone.

---

## O que o sistema faz

### Parte I — Autocomplete com Trie

Uma Trie construída do zero armazena um léxico de mais de 10 mil palavras em
português e responde a três operações:

| Operação | O que faz | Custo |
|---|---|---|
| `inserir(palavra)` | acrescenta uma palavra ao léxico | O(m) |
| `buscar(palavra)` | informa se a palavra existe | O(m) |
| `buscar_prefixo(prefixo)` | lista todas as palavras que começam com o prefixo | O(m + p) |

Com *m* = tamanho da palavra e *p* = número de nós abaixo do prefixo.

### Parte II — Mecanismo de busca em documentos

Varre automaticamente todos os `.txt` de uma pasta, pré-processa o texto,
monta o vocabulário na Trie e constrói um índice invertido. Oferece três
modalidades de consulta:

1. **Palavra exata** — consulta o índice invertido via hash, O(1) em média.
2. **Prefixo** — a Trie recupera os termos e o índice diz onde cada um aparece.
3. **Sequência de caracteres** — KMP direto sobre o conteúdo original dos
   arquivos, encontrando inclusive fragmentos que a tokenização descarta.

Nenhum nome de arquivo aparece no código: basta soltar um `.txt` novo na pasta
`documentos/` para que ele entre no índice na execução seguinte.

---

## Estrutura do projeto

```
.
├── documentos/              24 arquivos .txt usados nos testes
├── main.py                  interface de linha de comando (Partes I e II)
├── trie.py                  Trie e Trie comprimida (PATRICIA)
├── stemmer_rslp.py          stemmer RSLP para português
├── preprocessamento.py      minúsculas, pontuação, tokenização, stopwords
├── indice_invertido.py      índice invertido, tabela hash, BM25 e TF-IDF
├── kmp.py                   Knuth–Morris–Pratt e busca ingênua
├── mecanismo.py             integração de tudo: varredura, indexação, consultas
├── estatisticas.py          cronometragem e métricas
├── benchmark.py             experimentos de análise de complexidade
├── testes.py                76 testes automatizados
├── gerar_lexico.py          regera palavras.txt a partir do corpus
├── preparar_corpus.py       rebaixa os documentos da Wikipédia
├── palavras.txt             léxico da Parte I (~10.500 palavras)
├── stopwords.txt            stopwords do português
├── README.md                este arquivo
└── RELATORIO.md             relatório técnico
```

---

## Como usar

### Menu principal

```bash
python main.py
```

### Ir direto para uma das partes

```bash
python main.py --parte 1      # autocomplete com Trie
python main.py --parte 2      # busca em documentos
```

### Outras opções

```bash
python main.py --pasta meus_textos    # usa outra pasta de documentos
python main.py --lexico outra.txt     # usa outro léxico na Parte I
python main.py --sem-stemming         # desliga o RSLP, para comparação
python main.py --help                 # lista todas as opções
```

### Usar seus próprios documentos

Coloque arquivos `.txt` codificados em UTF-8 dentro de `documentos/` e rode o
programa. Eles serão descobertos, processados e indexados automaticamente.

Para regerar o léxico da Parte I a partir dos novos documentos:

```bash
python gerar_lexico.py
```

Para rebaixar a base de documentos original:

```bash
python preparar_corpus.py            # baixa apenas o que faltar
python preparar_corpus.py --forcar   # rebaixa tudo
```

---

## Exemplos de sessão

### Autocomplete por prefixo

```
============================================================
                   AUTOCOMPLETE COM TRIE
============================================================
Palavras cadastradas: 10.474

1 - Buscar palavra
2 - Buscar por prefixo
3 - Inserir nova palavra
4 - Sair

Escolha uma opção: 2
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

Tempo da consulta: 442.5 us
```

### Busca por palavra, com ranqueamento BM25

```
Escolha uma opção: 1
Digite a palavra: algoritmo

Encontrada em 19 arquivo(s):
  - algoritmos.txt                               79 ocorrência(s)   BM25 0.614
  - complexidade_computacional.txt               51 ocorrência(s)   BM25 0.601
  - computacao_quantica.txt                      61 ocorrência(s)   BM25 0.594
  - aprendizado_de_maquina.txt                   31 ocorrência(s)   BM25 0.593
  - criptografia.txt                             53 ocorrência(s)   BM25 0.591
  ...

  Sem stemming a forma exata 'algoritmo' apareceria em 14 arquivo(s).
  O radical 'algoritm' (RSLP) alcança 19, reunindo as variantes da palavra.

Tempo da consulta: 46.5 us
```

### Busca por sequência com KMP

```
Escolha uma opção: 3
Digite a sequência: chave pública

31 ocorrência(s) em 2 arquivo(s):

  criptografia.txt (29 ocorrência(s))
      ...métricos. Os sistemas assimétricos usam uma "chave pública" para cifrar...
      ...A vantagem dos sistemas assimétricos é que a chave pública pode ser...

  computacao_quantica.txt (2 ocorrência(s))
      ...implicações profundas para a criptografia de chave pública, já que...

  Comparações de caractere feitas pelo KMP: 697.716

Tempo da consulta: 73.829 ms
```

O contraste entre os dois últimos exemplos é o ponto central do trabalho:
**46 µs** para a consulta indexada contra **74 ms** para a varredura do corpus
inteiro — cerca de 1.600 vezes mais lenta. É a diferença entre O(1) e O(N),
medida na prática.

---

## Experimentos de complexidade

```bash
python benchmark.py
```

Sete experimentos que confrontam o custo assintótico previsto com o tempo
medido:

1. Busca por prefixo: Trie contra varredura sequencial
2. Trie tradicional contra Trie comprimida (PATRICIA)
3. KMP contra força bruta, no pior caso e em texto natural
4. Tabela hash: fator de carga, colisões e comprimento de cadeia
5. Escalabilidade da indexação
6. Ranqueamento: BM25 contra TF-IDF
7. Efeito do stemming RSLP na cobertura das consultas

Os resultados estão discutidos no [RELATORIO.md](RELATORIO.md).

---

## Testes

```bash
python testes.py        # resumo
python testes.py -v     # detalhado
```

76 testes cobrindo os exemplos do enunciado, casos de borda e testes de
propriedade com entradas aleatórias — o KMP é comparado contra a busca ingênua
em 2.000 casos, e a Trie comprimida contra a tradicional em 40 vocabulários
gerados aleatoriamente.

---

## Algoritmos implementados

| Algoritmo / estrutura | Referência |
|---|---|
| Trie | Fredkin, E. *Trie Memory*. CACM 3(9):490–499, 1960 |
| Trie comprimida (PATRICIA) | Morrison, D. R. *PATRICIA*. JACM 15(4):514–534, 1968 |
| Knuth–Morris–Pratt | Knuth, Morris & Pratt. *Fast Pattern Matching in Strings*. SIAM J. Comput. 6(2):323–350, 1977 |
| Stemmer RSLP | Orengo & Huyck. *A Stemming Algorithm for the Portuguese Language*. SPIRE 2001, pp. 186–193 |
| TF-IDF | Spärck Jones, K. *A statistical interpretation of term specificity*. J. Documentation 28(1):11–21, 1972 |
| Okapi BM25 | Robertson et al. *Okapi at TREC-3*, 1994; Robertson & Zaragoza, FnTIR 3(4):333–389, 2009 |
| Hash com encadeamento | Knuth, D. E. *The Art of Computer Programming*, vol. 3, cap. 6.4 |

Todas as estruturas foram implementadas do zero. As únicas bibliotecas usadas
são `re`, `unicodedata`, `math`, `time`, `pathlib`, `argparse`, `random`,
`statistics`, `json`, `urllib` e `unittest` — todas da biblioteca padrão do
Python e todas dentro do que o enunciado autoriza.

---

## Base de documentos

Os 24 arquivos de `documentos/` somam cerca de **99.500 palavras** e foram
extraídos de artigos da Wikipédia em português sobre temas de Computação
(algoritmos, estruturas de dados, inteligência artificial, banco de dados,
redes, criptografia, entre outros).

O conteúdo da Wikipédia está sob licença
[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/deed.pt-br).
O script `preparar_corpus.py` documenta exatamente quais artigos foram usados e
permite reproduzir a base.

---

## Integrantes do grupo

<!-- Preencher com os nomes e matrículas dos integrantes -->

| Nome | Matrícula |
|---|---|
|  |  |
|  |  |
|  |  |
|  |  |
