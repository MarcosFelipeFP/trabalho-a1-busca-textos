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
- [Interface web](#interface-web)
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

python main.py       # no terminal
python servidor.py   # no navegador
```

O repositório já vem com os 24 documentos de teste em `documentos/` e o léxico
em `palavras.txt`, então o programa roda direto após o clone.

Sem Python instalado, abra **`web/index.html`** com dois cliques: a interface
inteira funciona offline, no próprio navegador. É essa a versão que vai no
pendrive — veja [Interface web](#interface-web).

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
├── web/                     a interface, que abre com ou sem servidor
│   ├── index.html           a página
│   ├── estilo.css           a folha de estilo
│   ├── algoritmos/          os módulos Python portados para JavaScript
│   ├── dados/               corpus, léxico e stopwords empacotados
│   └── interface/           motor, desenho, fita do KMP, laboratório e controle
├── main.py                  interface de linha de comando (Partes I e II)
├── servidor.py              interface web: serve web/ e expõe as consultas em JSON
├── trie.py                  Trie e Trie comprimida (PATRICIA)
├── stemmer_rslp.py          stemmer RSLP para português
├── preprocessamento.py      minúsculas, pontuação, tokenização, stopwords
├── indice_invertido.py      índice invertido, tabela hash, BM25 e TF-IDF
├── kmp.py                   Knuth–Morris–Pratt e busca ingênua
├── mecanismo.py             integração de tudo: varredura, indexação, consultas
├── estatisticas.py          cronometragem e métricas
├── benchmark.py             experimentos de análise de complexidade
├── testes.py                testes automatizados
├── verificar_web.py         confere o motor JavaScript contra o Python
├── gerar_dados_web.py       empacota o corpus para a versão offline
├── gerar_pendrive.py        reduz a interface a um arquivo .html só
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

## Interface web

A mesma coisa que o terminal faz, com a estrutura desenhada na tela e o custo
de cada consulta medido à vista. Há dois jeitos de abrir, e eles servem a
situações diferentes.

### Com o Python, para ver o servidor respondendo

```bash
python servidor.py
```

Constrói as estruturas, sobe um servidor em `http://localhost:8000` e abre o
navegador. `Ctrl+C` encerra.

```bash
python servidor.py --porta 9000       # outra porta
python servidor.py --sem-navegador    # não abre o navegador sozinho
python servidor.py --sem-stemming     # desliga o RSLP, para comparação
python servidor.py --help             # lista todas as opções
```

### Sem nada instalado, para levar no pendrive

Abra **`web/index.html`** com dois cliques. Não precisa de servidor, de Python,
nem de internet: a pasta `web/` é autossuficiente.

Para reduzir tudo a um arquivo só — mais difícil de chegar quebrado no
computador da apresentação:

```bash
python gerar_pendrive.py
```

Sai `pendrive/Bancada - Trabalho A1.html`, com cerca de 1 MB: o HTML, o CSS, os
algoritmos e os 24 documentos dentro do mesmo arquivo. Copie para o pendrive e
clique duas vezes em qualquer máquina.

### Como a versão offline funciona

Uma página aberta por `file://` não tem origem própria, e o navegador recusa
qualquer `fetch` para arquivos vizinhos — não dá para ler `documentos/` do
disco como o servidor faz. Duas peças resolvem isso:

| Peça | O que faz |
|---|---|
| `gerar_dados_web.py` | varre a pasta de documentos e grava corpus, léxico e stopwords como atribuições JavaScript em `web/dados/` |
| `web/algoritmos/` | a Trie, o RSLP, o KMP e o índice invertido portados de `.py` para `.js`, arquivo a arquivo |

Quando a página abre sem servidor, os algoritmos rodam no navegador; quando
abre pelo `servidor.py`, as consultas vão para o Python. O botão **motor**, no
canto superior direito, alterna entre os dois durante a apresentação — a mesma
consulta, as duas implementações, lado a lado.

Duas implementações do mesmo algoritmo é uma oportunidade de divergência
silenciosa, e é por isso que existe:

```bash
python verificar_web.py
```

Ele roda as duas sobre o mesmo corpus e exige resultado idêntico em nove
frentes — normalização, tokenização, stemming, Trie, Trie comprimida, índice
invertido, BM25, KMP e tabela hash —, mais de cem mil casos comparados um a
um. Precisa do Node.js, e só ele: a página no navegador não usa Node.

### As cinco telas

| Tela | O que dá para fazer |
|---|---|
| **1 · Autocomplete** | buscar por prefixo no léxico, com a subárvore da Trie desenhada ao lado; verificar se uma palavra existe e inserir palavras novas em tempo de execução |
| **2 · Busca** | as três modalidades da Parte II: palavra com BM25, prefixo (em ordem alfabética e por relevância) e sequência com KMP, esta com o algoritmo passo a passo sobre a fita de caracteres |
| **3 · Laboratório** | os sete experimentos do `benchmark.py`, rodando na máquina em que a página abriu, com os gráficos desenhados na hora |
| **4 · Métricas** | as sete métricas obrigatórias da seção 3.9, a memória das duas Tries, a dispersão da tabela hash e o histórico das consultas da sessão |
| **5 · Documentos** | o corpus indexado, com o texto de cada arquivo e as ocorrências destacadas |

Atalhos: `1` a `5` trocam de tela, `/` vai para a busca, `T` alterna claro e
escuro, `P` aumenta o corpo do texto para projeção, `?` lista todos.

### A régua de custo

No rodapé, uma escala logarítmica de 1 µs a 1 s atravessa todas as telas. Cada
consulta da sessão deixa uma marca nela, colorida pelo caminho que percorreu —
âmbar para o índice invertido, ciano para a Trie, brasa para a varredura com
KMP.

Escala logarítmica porque a distância entre o que se quer comparar é de três
ordens de grandeza: em escala linear, todas as consultas indexadas ficariam
empilhadas contra o zero. Depois de alguns minutos de demonstração, a régua
mostra dois aglomerados bem separados, e essa imagem é o resultado do trabalho.

O botão **comparar as duas vias**, na tela de busca, força o contraste: roda a
mesma consulta pelo índice e pelo KMP, uma atrás da outra, e põe as duas marcas
na régua. A diferença medida fica na casa das **mil vezes**.

Uma ressalva de método: o navegador arredonda `performance.now` por segurança,
em geral para 100 µs. Uma consulta de 40 µs medida uma vez apareceria como zero
— por isso cada leitura é a média de muitas execuções, e a interface informa
quantas entraram na conta. É o mesmo recurso que o `benchmark.py` já usa no
terminal, pelo mesmo motivo.

Nenhuma biblioteca externa é carregada, nem no Python nem no navegador: os
gráficos, o desenho da Trie e a fita do KMP são SVG escrito à mão. Em um
pendrive, sem rede, não haveria CDN de onde baixar nada.

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

88 testes cobrindo os exemplos do enunciado, casos de borda e testes de
propriedade com entradas aleatórias — o KMP é comparado contra a busca ingênua
em 2.000 casos, e a Trie comprimida contra a tradicional em 40 vocabulários
gerados aleatoriamente. Os doze últimos sobem o servidor web em uma porta
livre e conferem cada rota por HTTP.

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

| Nome | Matrícula |
|---|---|
| Marcos Felipe Ferreira Pires |  |
| Luana Cristina de Azevedo Celestino |  |
| Pedro Henrique Graciliano Taka |  |
| Giovanni Cardoso Avallone Belo |  |
