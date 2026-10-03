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
- [Onde está cada item do enunciado](#onde-está-cada-item-do-enunciado)
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
git clone https://github.com/MarcosFelipeFP/trabalho-a1-busca-textos.git
cd trabalho-a1-busca-textos

python main.py       # no terminal
python servidor.py   # no navegador
```

O repositório já vem com os 24 documentos de teste em `documentos/` e o léxico
em `palavras.txt`, então o programa roda direto após o clone.

Sem Python instalado, abra **`interface/dist/index.html`** com dois cliques: a
interface inteira funciona offline, no próprio navegador. É essa a versão que
vai no pendrive ou no Google Drive — veja [Interface web](#interface-web).

---

## Onde está cada item do enunciado

As seções são as do enunciado do Trabalho Prático A1; o relatório é o PDF na
raiz do repositório.

| Enunciado | O que pede | No código | No relatório |
|---|---|---|---|
| 2.1 e 2.3 | Trie própria com `inserir`, `buscar` e `buscar_prefixo` | `trie.py`: classe `Trie` | 2.2 |
| 2.2 a 2.4 | Autocomplete: menu, consultas sucessivas, inserção durante a execução | `main.py`: `executar_parte1` | 2.2 e Figura 1 |
| 2.5 | Complexidade da inserção, da busca exata e da busca por prefixo | `trie.py`, nos comentários de cada operação | 2.2 e Quadro 1 |
| 2.6 | Questões conceituais da Parte I | — | 2.8 |
| 3.1 e 4 | A Trie da Parte I reaproveitada na Parte II | `mecanismo.py`: `MecanismoBusca` usa `trie.Trie` | 2.1 |
| 3.2 | Todos os `.txt` da pasta, sem nomes de arquivo no código | `mecanismo.py`: `listar_documentos` | 2.1 |
| 3.3 | Minúsculas, pontuação, tokenização e stopwords; stemming opcional | `preprocessamento.py`, `stemmer_rslp.py`, `stopwords.txt` | 2.3 |
| 3.4 | Vocabulário inserido na Trie | `mecanismo.py`: `MecanismoBusca.construir` | 2.3 |
| 3.5 | Índice invertido palavra → documentos | `indice_invertido.py`: classe `IndiceInvertido` | 2.3 |
| 3.6 | Hash (`dict`), função hash, O(1) em média e colisões | `indice_invertido.py`: classe `TabelaHash` | 2.4 |
| 3.7.1 | Consulta por palavra, com a forma exata destacada | `mecanismo.py`: `buscar_palavra` | 2.3 e 2.7 |
| 3.7.2 | Prefixo: a Trie dá os termos, o índice dá os documentos de cada um | `mecanismo.py`: `buscar_prefixo` | 2.3 e Figura 1 |
| 3.7.3 e 9 | Sequência de caracteres com KMP (opcional, bônus) | `kmp.py`; `mecanismo.py`: `buscar_sequencia` | 2.5 |
| 3.8 | Menu sugerido | `main.py`: `executar_parte2` | — |
| 3.9 | As sete estatísticas, inclusive o tempo de cada consulta | `estatisticas.py`; `main.py`: `exibir_estatisticas` | 2.1 (Tabela 1) e 2.7 (Tabela 3) |
| 3.9 | Tempos relacionados à análise de complexidade | custo previsto ao lado de cada tempo; `benchmark.py` | 2.6 (Tabela 2) e 2.7 |
| 4 | Sem bibliotecas prontas; funções e classes comentadas | todos os módulos `.py` | — |
| 5 | Organização sugerida do projeto | ver [Estrutura do projeto](#estrutura-do-projeto) | — |
| 6 | Código, pasta de `.txt`, README e relatório curto | este repositório | descrição e decisões de implementação em 2.1 |
| 6.1 | Conteúdo mínimo do relatório | — | 2.2 a 2.9 |

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
| `sugerir(prefixo, k)` | as *k* palavras mais frequentes, por busca best-first | não depende de *p* |
| `buscar_aproximado(palavra)` | "você quis dizer?" por distância de edição | O(n·m), *n* = nós após a poda |

Com *m* = tamanho da palavra e *p* = número de nós abaixo do prefixo. As duas
últimas operações são extensões: cada nó mantém a contagem e a maior
frequência da própria subárvore, e a distância de edição (com transposição) é
calculada sobre a Trie, uma linha da matriz por nó.

### Parte II — Mecanismo de busca em documentos

Varre automaticamente todos os `.txt` de uma pasta, pré-processa o texto,
monta o vocabulário na Trie e constrói um índice invertido. Oferece três
modalidades de consulta:

1. **Palavra** — consulta o índice invertido via hash, O(1) em média, pelo
   radical do RSLP; os arquivos que só têm variantes da palavra, e não a forma
   exata, vêm marcados. Aceita vários termos (`rede neural`): os documentos com
   todos eles vêm primeiro, por interseção a partir da menor lista, e termos
   sem resultado ganham sugestão de correção.
2. **Prefixo** — a Trie recupera os termos, e o índice da forma exata diz em
   que documentos cada um aparece.
3. **Sequência de caracteres** — KMP direto sobre o conteúdo original dos
   arquivos, encontrando inclusive fragmentos que a tokenização descarta.

Nenhum nome de arquivo aparece no código: basta soltar um `.txt` novo na pasta
`documentos/` para que ele entre no índice na execução seguinte.

Cada tempo informado vem com o custo que a análise prevê — O(1) por termo na
palavra, O(m + p) no prefixo, O(N) na sequência —, e a tela de estatísticas
lista o tempo de cada consulta e compara as médias dos três tipos.

---

## Estrutura do projeto

```
.
├── documentos/              24 arquivos .txt usados nos testes
├── interface/               a interface web (React + Vite), que abre com ou sem servidor
│   ├── dist/index.html      a interface compilada: um arquivo só, com tudo dentro
│   ├── src/algoritmos/      os módulos Python portados para JavaScript
│   ├── src/dados/           corpus, léxico e stopwords em JSON
│   └── src/busca/           a página de busca: resultados, trechos e leitor
├── main.py                  interface de linha de comando (Partes I e II)
├── servidor.py              serve a interface e expõe as consultas em JSON
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
├── gerar_dados_web.py       empacota o corpus em JSON para a interface
├── gerar_pendrive.py        copia a interface de um arquivo só para o pendrive
├── gerar_lexico.py          regera palavras.txt a partir do corpus
├── preparar_corpus.py       rebaixa os documentos da Wikipédia
├── palavras.txt             léxico da Parte I (~10.500 palavras)
├── stopwords.txt            stopwords do português
├── README.md                este arquivo
└── Relatório Técnico (ABNT) - Trabalho A1 - versão reduzida.pdf    relatório técnico (ABNT)
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

Coloque arquivos `.txt` dentro de `documentos/`, em UTF-8 ou no ANSI que o
Bloco de Notas oferece, e rode o programa. Eles serão descobertos, processados
e indexados automaticamente.

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

A mesma coisa que o terminal faz, com as estruturas desenhadas na tela e o
custo de cada consulta medido à vista. Escrita em React e TypeScript, com
Vite; os algoritmos rodam no próprio navegador.

### Na apresentação, sem instalar nada

Abra **`interface/dist/index.html`** com dois cliques. É um arquivo só, com o
HTML, o CSS, as fontes, os algoritmos e os 24 documentos dentro dele: funciona
sem internet, sem Python e sem servidor. Para levar no pendrive ou no Google
Drive, com um nome legível e um LEIA-ME ao lado:

```bash
python gerar_pendrive.py
```

Sai `pendrive/Busca em textos - Trabalho A1.html` (cerca de 1,6 MB). Vindo do
Drive, baixe o arquivo antes de abrir: a pré-visualização do Drive não executa
páginas.

### Com o Python respondendo

```bash
python servidor.py
```

Constrói as estruturas em Python, serve a mesma página em
`http://localhost:8000` e abre o navegador. Com o servidor no ar, a página
mostra a opção **Python** (no rodapé da tela inicial e no alto das outras
telas): as consultas passam a ser respondidas pelos módulos `.py`, com o mesmo
formato de resposta.

### Como é a página

Quatro telas, em tema claro, que espelham os menus do terminal. Os botões no
alto, à direita, levam de uma a outra:

- **Autocomplete (Parte I)**: as opções do menu da seção 2.4 sobre o léxico de
  `palavras.txt` — buscar uma palavra, listar todas as que começam com um
  prefixo, em ordem alfabética, e inserir palavras novas durante a sessão —,
  cada uma com o tempo medido e o custo previsto;
- **Busca (Parte II)**, a tela inicial: enquanto se digita, a Trie do
  vocabulário sugere as palavras mais frequentes dos documentos; no Enter, a
  caixa sobe e os documentos aparecem ordenados pelo BM25, cada um com um
  trecho em que as palavras encontradas vêm realçadas;
- **Documentos**: a opção 4 do menu da seção 3.8, com o tamanho e as palavras
  indexadas de cada arquivo; clicar num deles abre o texto;
- **Estatísticas**: a opção 5, com as estatísticas obrigatórias da seção 3.9,
  o tempo de cada consulta feita na sessão e quantas vezes a busca por
  sequência custou a busca por palavra, ao lado do custo previsto de cada uma.

Na busca:

- as abas **Palavra**, **Prefixo** e **Sequência** escolhem a pergunta, e o
  seletor **"Respondido por"**, ao lado, escolhe a estrutura que responde;
- esse seletor é a comparação do relatório, ao vivo: a mesma pergunta pelo
  índice invertido O(1) ou varrendo o texto com KMP O(N); pela Trie O(m + p) ou
  percorrendo a lista de palavras O(V·m); pelo KMP O(n + m) ou pela busca
  ingênua O(n·m);
- na aba **Prefixo**, todos os termos que começam com o prefixo aparecem em
  ordem alfabética, cada um com os documentos em que aparece, dez por vez, como
  no terminal (seção 3.7.2); clicar num documento o abre com o termo realçado;
- na aba **Palavra**, o resumo diz quantos documentos têm a forma exata
  digitada, e os que o radical alcançou só por variantes vêm marcados (3.7.1);
- clicar num resultado abre o texto inteiro, com os realces;
- a linha acima dos resultados nomeia a estrutura usada, o custo dela, quantos
  documentos voltaram e quanto tempo a consulta levou.

### Recompilar a interface

Só é preciso ao mudar o código da interface ou os documentos. Requer Node.js:

```bash
python gerar_dados_web.py     # corpus, léxico e stopwords -> interface/src/dados/
cd interface
npm install                   # uma vez
npm run build                 # gera interface/dist/index.html
```

`npm run dev` sobe a versão de desenvolvimento, que conversa com o
`servidor.py` se ele estiver no ar.

### Dois motores, uma resposta

Duas implementações do mesmo algoritmo são uma oportunidade de divergência
silenciosa, e é por isso que existe:

```bash
python verificar_web.py
```

Ele roda o Python e o JavaScript sobre o mesmo corpus e exige resultado
idêntico em doze frentes — normalização, tokenização, stemming, Trie, Trie
comprimida, autocomplete por relevância, busca aproximada, índice invertido,
consultas com BM25 e vários termos, consultas por prefixo, KMP e tabela hash —,
mais de 120 mil casos comparados um a um.

Uma ressalva de método: o navegador arredonda o relógio por segurança (em
`file://`, para cerca de 100 µs). Por isso cada consulta barata é repetida em
lotes até acumular alguns milissegundos, e o tempo exibido é a média por
execução. Antes da primeira consulta, os algoritmos são aquecidos para que o
compilador JIT não seja medido junto. A exceção é a inserção da Parte I:
repetida, ela já não inseriria nada, então é medida uma vez só, e quando fica
abaixo do que o relógio do navegador mede a tela diz isso em vez de mostrar
"0 µs". O relógio do Python tem resolução de nanossegundos e mede a inserção
direto.

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
(Para voltar ao menu, tecle Enter sem digitar nada.)
Digite o prefixo: comp

Palavras encontradas:
  compacidade
  compacta
  compacto
  companhia
  compaq
  compara
  comparação
  ...
  competição
  -- 40 de 151 palavras. Enter mostra mais; 0 encerra a lista: 0

Tempo da consulta: 183,9 µs (custo previsto: O(m + p))
Digite o prefixo:
```

A lista traz todas as palavras que começam com o prefixo, em páginas de 40.
As perguntas têm o texto dos exemplos do enunciado, e cada opção continua
ativa depois da resposta: o programa pede o próximo prefixo, e o Enter sem
nada digitado volta ao menu.

### Busca por prefixo nos documentos: a Trie acha os termos, o índice diz onde estão

```
Escolha uma opção: 2
(Para voltar ao menu, tecle Enter sem digitar nada.)
Digite o prefixo: compil

Palavras encontradas:
  compila                    ->  2 documento(s)
      compiladores.txt, linguagens_programacao.txt
  compilação                 ->  2 documento(s)
      compiladores.txt, linguagens_programacao.txt
  compilações                ->  1 documento(s)
      compiladores.txt
  ...
  compilador                 ->  4 documento(s)
      compiladores.txt, estruturas_de_dados.txt,
      linguagens_programacao.txt, sistemas_operacionais.txt
  ...
  -- 10 de 13 termos. Enter mostra mais; 0 encerra a lista: 0

Mais relevantes (por frequência no corpus):
  1. compilador                    29 ocorrência(s)
  2. compilação                    12 ocorrência(s)
  3. compiladores                  12 ocorrência(s)
  ...

Documentos que contêm algum desses termos: 4
  - compiladores.txt                           BM25 42,446
  - linguagens_programacao.txt                 BM25 32,238
  - estruturas_de_dados.txt                    BM25 2,044
  - sistemas_operacionais.txt                  BM25 1,783

Tempo da consulta: 123,8 µs (custo previsto: O(m + p))
```

Cada termo vem com os documentos em que aquela palavra aparece, consultados no
índice da forma exata: `compila` está em 2 arquivos e `compilador` em 4.

### Busca por palavra, com ranqueamento BM25

```
Escolha uma opção: 1
(Para voltar ao menu, tecle Enter sem digitar nada.)
Digite a palavra: algoritmo

Encontrada em 19 arquivo(s), 14 com a forma exata 'algoritmo':
  - algoritmos.txt                               79 ocorrência(s)   BM25 0,614
  - complexidade_computacional.txt               51 ocorrência(s)   BM25 0,601
  - computacao_quantica.txt                      61 ocorrência(s)   BM25 0,594
  - aprendizado_de_maquina.txt                   31 ocorrência(s)   BM25 0,593
  - criptografia.txt                             53 ocorrência(s)   BM25 0,591
  ...
  - sistemas_operacionais.txt                     1 ocorrência(s)   BM25 0,258   *
  - redes.txt                                     1 ocorrência(s)   BM25 0,166   *

  * sem a forma exata 'algoritmo': o radical 'algoritm' (RSLP)
    alcança esses arquivos pelas variantes da palavra.

Tempo da consulta: 61,5 µs (custo previsto: O(1) por termo)
```

O índice é consultado pelo radical, que reúne as variantes da palavra; os
arquivos marcados com `*` não têm a forma exata digitada, só variantes como
*algoritmos*. Uma palavra digitada sem acento, como `computacao`, acha os
arquivos que escrevem *computação*.

### Busca por sequência com KMP

```
Escolha uma opção: 3
(Para voltar ao menu, tecle Enter sem digitar nada.)
Digite a sequência: chave pública

31 ocorrência(s) em 2 arquivo(s):

  criptografia.txt (29 ocorrência(s))
      ...métricos. Os sistemas assimétricos usam uma "chave pública" para cifrar...
      ...A vantagem dos sistemas assimétricos é que a chave pública pode ser...

  computacao_quantica.txt (2 ocorrência(s))
      ...implicações profundas para a criptografia de chave pública, já que...

  Comparações de caractere feitas pelo KMP: 697.716

Tempo da consulta: 53,1 ms (custo previsto: O(N))
```

O contraste entre os dois últimos exemplos é o ponto central do trabalho: a
consulta indexada leva microssegundos, e a varredura do corpus inteiro,
dezenas de milissegundos. Nas medianas do relatório (Tabela 3), são
**31,0 µs** contra **57,7 ms**, cerca de 1.900 vezes. É a diferença entre O(1)
e O(N), medida na prática.

### Estatísticas: o tempo medido ao lado do custo previsto

```
CONSULTAS REALIZADAS (5)
------------------------------------------------------------
  tipo          qtd   tempo médio   custo previsto
  palavra         3       95,0 µs   O(1) por termo
  prefixo         1      133,2 µs   O(m + p)
  sequência       1       85,8 ms   O(N)

  Em média, a busca por sequência levou 904 vezes o tempo
  da busca por palavra: O(N) contra O(1).

  m = tamanho da palavra ou do prefixo; p = nós da Trie
  abaixo do prefixo; N = caracteres de todos os documentos.

  Tempo de cada consulta:
     1. palavra    'algoritmo'                     19 resultado(s)    112,8 µs
     2. palavra    'rede neural'                   17 resultado(s)     93,8 µs
     3. palavra    'dados'                         24 resultado(s)     78,3 µs
     4. prefixo    'compil'                        13 resultado(s)    133,2 µs
     5. sequência  'chave pública'                  2 resultado(s)     85,8 ms
```

A opção 5 mostra as estatísticas da seção 3.9 e, ao final, esse bloco. Os
tempos de uma sessão variam com a máquina e com a primeira execução de cada
consulta; as medianas do relatório, sobre centenas de execuções, são a
referência.

---

## Experimentos de complexidade

```bash
python benchmark.py
```

Nove experimentos que confrontam o custo assintótico previsto com o tempo
medido:

1. Busca por prefixo: Trie contra varredura sequencial
2. Autocomplete top-k: busca best-first contra varredura da subárvore
3. Trie tradicional contra Trie comprimida (PATRICIA)
4. KMP contra força bruta, no pior caso e em texto natural
5. Tabela hash: fator de carga, colisões e comprimento de cadeia
6. Escalabilidade da indexação
7. Ranqueamento: BM25 contra TF-IDF
8. Efeito do stemming RSLP na cobertura das consultas
9. Busca aproximada: Trie contra comparação palavra a palavra

Os resultados estão discutidos no
[relatório técnico](Relat%C3%B3rio%20T%C3%A9cnico%20%28ABNT%29%20-%20Trabalho%20A1%20-%20vers%C3%A3o%20reduzida.pdf).

---

## Testes

```bash
python testes.py        # resumo
python testes.py -v     # detalhado
```

145 testes cobrindo os exemplos do enunciado, casos de borda e testes de
propriedade com entradas aleatórias — o KMP é comparado contra a busca ingênua
em 2.000 casos, a Trie comprimida contra a tradicional em 40 vocabulários
aleatórios, a busca aproximada contra a distância de edição calculada palavra
a palavra e a lista de documentos de cada termo do prefixo contra os tokens de
cada arquivo. Outros conduzem os menus do terminal com respostas simuladas e
conferem a saída impressa, e os últimos sobem o servidor web em uma porta livre
e conferem cada rota por HTTP.

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

Todas as estruturas foram implementadas do zero, e tudo vem da biblioteca
padrão do Python, dentro do que o enunciado autoriza. O programa usa `re`,
`unicodedata`, `heapq`, `math`, `time`, `textwrap`, `pathlib`, `argparse` e
`sys`. Os scripts de apoio acrescentam `statistics` e `random` (experimentos),
`unittest` (testes), `http.server`, `threading`, `webbrowser` e `mimetypes`
(servidor), além de `json`, `urllib`, `subprocess`, `shutil` e `tempfile`.

---

## Base de documentos

Os 24 arquivos de `documentos/` somam **98.718 palavras** após a tokenização e
foram extraídos de artigos da Wikipédia em português sobre temas de Computação
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
| Giovanni Cardoso Avallone Belo | 1230104729 |
| Luana Cristina de Azevedo Celestino | 1230206514 |
| Marcos Felipe Ferreira Pires | 1230110993 |
| Pedro Henrique Graciliano Taka | 1230119578 |
