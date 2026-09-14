/* ===========================================================================
   trie.js
   Porte de `trie.py` para o navegador: Trie (árvore de prefixos) e a variante
   comprimida (PATRICIA / radix tree), construídas do zero sobre `Map`.

   Referências:
       Fredkin, E. "Trie Memory". Communications of the ACM, 3(9):490-499, 1960.
       Morrison, D. R. "PATRICIA - Practical Algorithm To Retrieve Information
           Coded in Alphanumeric". Journal of the ACM, 15(4):514-534, 1968.

   ---------------------------------------------------------------------------
   Decisão de projeto: chave normalizada, exibição original
   ---------------------------------------------------------------------------
   Palavras do português carregam acentos ("computação"). Se o acento fizesse
   parte da chave, o prefixo "computa" encontraria "computador", mas quem
   digitasse "computacao" não encontraria nada.

     * a CHAVE que percorre a Trie é a forma normalizada (minúscula, sem acento);
     * o NÓ FINAL guarda o conjunto das formas originais já inseridas.

   Ordenar pela chave normalizada reproduz a ordem do exemplo do enunciado
   (compilador, complexidade, computação, computacional, computador), porque
   "computacao" < "computacional" < "computador" na ordem alfabética.

   ---------------------------------------------------------------------------
   Equivalência com a versão Python
   ---------------------------------------------------------------------------
   `verificar_web.py` roda as duas implementações sobre o mesmo léxico e exige
   resultado idêntico, palavra por palavra. Duas escolhas sustentam isso:

     * `Map` no lugar do dicionário, porque a ordem de inserção não interfere
       -- toda travessia que precisa de ordem a impõe explicitamente;
     * comparação de strings pelo operador `<`, que no JavaScript ordena por
       unidade de código UTF-16. Para o alfabeto latino isso coincide com a
       ordem por ponto de código que o `sorted` do Python usa.
   =========================================================================== */

/* Sinais diacríticos decompostos pela forma NFD: é a categoria Unicode "Mark",
   o mesmo conjunto que `unicodedata.combining` marca como não-zero. */
const DIACRITICOS = /\p{M}/gu;

/**
 * Forma canônica de uma palavra: minúscula e sem acentos.
 *
 * A decomposição NFD separa a letra do sinal (ç -> c + cedilha) e o filtro
 * descarta os sinais, restando as letras-base. normalizar("Computação")
 * devolve "computacao". Complexidade O(m).
 */
function normalizar(texto) {
  return String(texto).trim().toLowerCase().normalize('NFD').replace(DIACRITICOS, '');
}

/** Ordem por ponto de código, a mesma que o `sorted` do Python aplica. */
function ordemDeTexto(a, b) {
  return a < b ? -1 : (a > b ? 1 : 0);
}

/** Menor string de um conjunto, equivalente ao `min(...)` do Python. */
function menorForma(formas) {
  let menor = null;
  for (const forma of formas) {
    if (menor === null || forma < menor) menor = forma;
  }
  return menor;
}

/**
 * Distância de Damerau-Levenshtein restrita entre duas cadeias, pela matriz
 * completa: a definição direta, O(|a|·|b|), sem Trie e sem poda.
 *
 * É a referência contra a qual `Trie.buscarAproximado` é conferida e o termo
 * de comparação do experimento no laboratório. As cadeias são percorridas por
 * ponto de código (`Array.from`), como o Python indexa as suas.
 */
function distanciaEdicao(a, b) {
  const x = Array.from(a);
  const y = Array.from(b);
  let avo = null;
  let anterior = Array.from({ length: y.length + 1 }, (_valor, j) => j);

  for (let i = 1; i <= x.length; i += 1) {
    const linha = [i];
    for (let j = 1; j <= y.length; j += 1) {
      const custo = x[i - 1] === y[j - 1] ? 0 : 1;
      let valor = Math.min(linha[j - 1] + 1, anterior[j] + 1, anterior[j - 1] + custo);
      if (i > 1 && j > 1 && x[i - 1] === y[j - 2] && x[i - 2] === y[j - 1]) {
        valor = Math.min(valor, avo[j - 2] + 1);
      }
      linha.push(valor);
    }
    avo = anterior;
    anterior = linha;
  }
  return anterior[y.length];
}

/* =========================================================================
   TRIE TRADICIONAL
   ========================================================================= */

/* =========================================================================
   FILA DE PRIORIDADE (heap binária)
   -------------------------------------------------------------------------
   O JavaScript não tem equivalente ao `heapq` do Python, então a heap usada
   pela busca best-first do autocomplete é construída aqui, em vinte linhas.

   É a heap binária clássica sobre um vetor: o filho de `i` está em `2i+1` e
   `2i+2`, a raiz guarda sempre o menor elemento pelo comparador, e inserir e
   remover custam O(log n) porque só um caminho da árvore é reorganizado.
   ========================================================================= */

class FilaDePrioridade {
  constructor(comparar) {
    this.itens = [];
    this.comparar = comparar;
  }

  get tamanho() {
    return this.itens.length;
  }

  inserir(item) {
    const itens = this.itens;
    itens.push(item);
    let i = itens.length - 1;
    while (i > 0) {                       // sobe enquanto for menor que o pai
      const pai = (i - 1) >> 1;
      if (this.comparar(itens[i], itens[pai]) >= 0) break;
      [itens[i], itens[pai]] = [itens[pai], itens[i]];
      i = pai;
    }
  }

  remover() {
    const itens = this.itens;
    if (!itens.length) return undefined;

    const topo = itens[0];
    const ultimo = itens.pop();
    if (itens.length) {
      itens[0] = ultimo;
      let i = 0;
      for (;;) {                          // desce trocando com o menor filho
        const esquerda = 2 * i + 1;
        const direita = esquerda + 1;
        let menor = i;
        if (esquerda < itens.length &&
            this.comparar(itens[esquerda], itens[menor]) < 0) menor = esquerda;
        if (direita < itens.length &&
            this.comparar(itens[direita], itens[menor]) < 0) menor = direita;
        if (menor === i) break;
        [itens[i], itens[menor]] = [itens[menor], itens[i]];
        i = menor;
      }
    }
    return topo;
  }
}

/**
 * Ordem dos itens da busca best-first, idêntica à da tupla
 * `(-peso, chave, tipo, no)` que o Python empilha no `heapq`:
 * peso decrescente, chave alfabética, palavra antes de nó.
 */
function ordemDaFila(a, b) {
  if (a.peso !== b.peso) return b.peso - a.peso;
  if (a.chave !== b.chave) return ordemDeTexto(a.chave, b.chave);
  return a.tipo - b.tipo;
}

const TIPO_PALAVRA = 0;
const TIPO_NO = 1;

/**
 * Nó de uma Trie tradicional: cada aresta guarda um único caractere.
 *
 * Além do que a Trie clássica exige, o nó guarda dois agregados da sua
 * subárvore -- `palavrasAbaixo` e `melhorPeso` --, mantidos na inserção. São
 * eles que permitem contar um prefixo em O(m) e devolver as k palavras mais
 * relevantes sem varrer a subárvore. O mesmo que a versão Python faz.
 */
class NoTrie {
  constructor() {
    this.filhos = new Map();     // caractere -> NoTrie
    this.fimDePalavra = false;   // marca o término de uma palavra válida
    this.formas = null;          // grafias originais associadas a esta chave

    this.peso = 0;               // relevância da palavra que termina aqui
    this.palavrasAbaixo = 0;     // palavras armazenadas nesta subárvore
    this.melhorPeso = 0;         // maior peso encontrado nesta subárvore
  }
}

/**
 * Árvore de prefixos.
 *
 * Cada aresta carrega um caractere; o caminho da raiz até um nó marcado
 * representa uma palavra. Prefixos comuns compartilham o mesmo caminho, que é
 * exatamente a propriedade explorada pelo autocomplete.
 *
 * Complexidades (m = tamanho da palavra/prefixo, p = nós na subárvore,
 * h = altura da Trie):
 *     inserir(palavra)       O(m)
 *     buscar(palavra)        O(m)
 *     buscarPrefixo(pref)    O(m + p)
 *     contarPrefixo(pref)    O(m)      -- lê o agregado, não varre nada
 *     sugerir(pref, k)       O(m + k·h·σ·log(k·h·σ)) -- não depende de p
 */
class Trie {
  constructor(palavras) {
    this.raiz = new NoTrie();
    this._totalPalavras = 0;   // chaves distintas armazenadas
    this._totalNos = 1;        // a raiz já conta
    this.comparacoes = 0;      // instrumentação usada nos experimentos
    this.nosVisitados = 0;     // nós tocados pela última busca por prefixo

    if (palavras) {
      for (const palavra of palavras) this.inserir(palavra);
    }
  }

  /* -------------------------------------------------------------- inserção */

  /**
   * Insere uma palavra. Percorre a chave normalizada caractere a caractere,
   * criando os nós que faltarem. Devolve true se a palavra é nova e false se
   * a chave já existia -- nesse caso apenas registra a nova grafia.
   *
   * `peso` é a relevância da palavra (no mecanismo, a frequência dela no
   * corpus); reinserir com peso maior atualiza o valor. Os dois agregados são
   * propagados numa segunda passada pelo MESMO caminho já percorrido, então o
   * custo continua O(m).
   */
  inserir(palavra, peso) {
    const original = String(palavra).trim();
    if (!original) return false;

    const chave = normalizar(original);
    if (!chave) return false;

    const relevancia = (peso === undefined) ? 1 : peso;

    // O caminho é guardado na descida porque as agregações sobem da folha
    // para a raiz, e a Trie não mantém ponteiro para o pai.
    const caminho = [this.raiz];
    let no = this.raiz;
    for (const caractere of chave) {
      let proximo = no.filhos.get(caractere);
      if (proximo === undefined) {
        proximo = new NoTrie();
        no.filhos.set(caractere, proximo);
        this._totalNos += 1;
      }
      no = proximo;
      caminho.push(no);
    }

    const nova = !no.fimDePalavra;
    if (nova) {
      no.fimDePalavra = true;
      no.formas = new Set();
      this._totalPalavras += 1;
    }
    no.formas.add(original);

    if (relevancia > no.peso) no.peso = relevancia;

    for (const ancestral of caminho) {
      if (nova) ancestral.palavrasAbaixo += 1;
      if (no.peso > ancestral.melhorPeso) ancestral.melhorPeso = no.peso;
    }
    return nova;
  }

  /* ----------------------------------------------------------------- busca */

  /**
   * Desce a Trie seguindo `texto` e devolve o nó alcançado, ou null se o
   * caminho não existir. Base da busca exata e da busca por prefixo, e também
   * o que o desenho da árvore usa para saber onde começar. O(m).
   */
  descer(texto) {
    let no = this.raiz;
    for (const caractere of texto) {
      this.comparacoes += 1;
      no = no.filhos.get(caractere);
      if (no === undefined) return null;
    }
    return no;
  }

  /**
   * A palavra completa existe na Trie?
   *
   * Não basta o caminho existir: o nó final precisa estar marcado como fim de
   * palavra. É o que distingue uma palavra armazenada de um simples prefixo
   * de outra -- "comp" é caminho de "computador", mas só é palavra se tiver
   * sido inserida. O(m).
   */
  buscar(palavra) {
    const no = this.descer(normalizar(palavra));
    return no !== null && no.fimDePalavra;
  }

  /** Grafias originais registradas para uma chave, em ordem alfabética. */
  formasDe(palavra) {
    const no = this.descer(normalizar(palavra));
    if (no === null || !no.fimDePalavra) return [];
    return Array.from(no.formas).sort(ordemDeTexto);
  }

  /**
   * Palavras que começam com o prefixo, em ordem alfabética.
   *
   * São duas etapas com custos distintos:
   *   1. descer o prefixo            -> O(m)
   *   2. varrer a subárvore restante -> O(p), nós abaixo do prefixo
   *
   * `limite` interrompe a coleta após k resultados, útil quando o prefixo é
   * curto e a subárvore é enorme. O(m + p), ou O(m + k) com limite.
   */
  buscarPrefixo(prefixo, limite) {
    const chave = normalizar(prefixo);
    const no = this.descer(chave);
    if (no === null) return [];

    this.nosVisitados = 0;       // instrumentação: contraste com `sugerir`
    const encontradas = [];
    const pilha = [[no, chave]];

    while (pilha.length) {
      if (limite != null && encontradas.length >= limite) break;
      const [atual, caminho] = pilha.pop();
      this.nosVisitados += 1;

      if (atual.fimDePalavra) {
        // Uma mesma chave pode ter mais de uma grafia; adota-se a menor em
        // ordem alfabética como representante.
        encontradas.push([caminho, menorForma(atual.formas)]);
      }

      // Empilhados em ordem decrescente para que o menor caractere seja
      // desempilhado primeiro. Com isso a travessia em pré-ordem já sai em
      // ordem alfabética -- o nó vem antes dos descendentes, e toda chave da
      // subárvore tem a dele como prefixo --, e não é preciso ordenar no fim.
      const iniciais = Array.from(atual.filhos.keys()).sort(ordemDeTexto).reverse();
      for (const caractere of iniciais) {
        pilha.push([atual.filhos.get(caractere), caminho + caractere]);
      }
    }

    return encontradas.map((par) => par[1]);
  }

  /**
   * Quantas palavras começam com o prefixo. O(m), e não O(m + p): o número já
   * está agregado no nó desde a inserção -- desce-se o prefixo e lê-se um
   * inteiro, sem tocar em nenhum nó da subárvore.
   */
  contarPrefixo(prefixo) {
    const no = this.descer(normalizar(prefixo));
    return no === null ? 0 : no.palavrasAbaixo;
  }

  /**
   * As `limite` palavras mais relevantes que começam com o prefixo, da mais
   * para a menos relevante. Devolve pares [palavra, peso], no mesmo formato
   * da versão Python -- é o que permite ao `verificar_web.py` comparar as
   * duas saídas sem tradução no meio.
   *
   * Busca best-first: `melhorPeso` é um limite superior para toda a subárvore
   * de um nó, então explorar em ordem decrescente desse limite garante que,
   * quando um item-palavra chega ao topo da fila, nenhuma subárvore ainda
   * fechada pode conter algo melhor. Subárvores piores que o k-ésimo
   * resultado nunca chegam a ser abertas -- por isso o custo não depende de
   * p, o tamanho da subárvore do prefixo.
   */
  sugerir(prefixo, limite) {
    const chave = normalizar(prefixo);
    const no = this.descer(chave);
    if (no === null) return [];

    const k = (limite === undefined) ? 10 : limite;
    this.nosVisitados = 0;

    const fila = new FilaDePrioridade(ordemDaFila);
    fila.inserir({ peso: no.melhorPeso, chave: chave, tipo: TIPO_NO, no: no });

    const encontradas = [];
    while (fila.tamanho && encontradas.length < k) {
      const item = fila.remover();

      if (item.tipo === TIPO_PALAVRA) {
        encontradas.push([menorForma(item.no.formas), item.peso]);
        continue;
      }

      this.nosVisitados += 1;
      const atual = item.no;

      if (atual.fimDePalavra) {
        fila.inserir({ peso: atual.peso, chave: item.chave, tipo: TIPO_PALAVRA, no: atual });
      }

      for (const [caractere, filho] of atual.filhos) {
        fila.inserir({
          peso: filho.melhorPeso,
          chave: item.chave + caractere,
          tipo: TIPO_NO,
          no: filho,
        });
      }
    }

    return encontradas;
  }

  /**
   * Palavras a no máximo `distanciaMaxima` edições de `palavra` -- o "você
   * quis dizer?". Devolve trios [palavra, distância, peso], da mais próxima
   * para a mais distante e, empatadas, da mais relevante para a menos.
   *
   * Sem `distanciaMaxima`, a tolerância acompanha o tamanho da palavra: uma
   * edição até quatro letras, duas acima disso. `limite` null devolve todas.
   *
   * Programação dinâmica sobre a própria Trie: a linha i da matriz de edição
   * depende só das linhas i-1 e i-2, e todas as palavras abaixo de um nó
   * dividem a linha do caminho até ele -- então a travessia calcula UMA linha
   * por nó, válida para a subárvore inteira. Como o menor valor de uma linha
   * nunca diminui ao descer, um ramo cujo mínimo passou do limite é podado
   * sem ser visitado. O(n·m), com n = nós que sobrevivem à poda.
   */
  buscarAproximado(palavra, distanciaMaxima = null, limite = 5) {
    const chave = normalizar(palavra);
    if (!chave) return [];

    const letras = Array.from(chave);
    const m = letras.length;
    const tolerancia = distanciaMaxima == null ? (m <= 4 ? 1 : 2) : distanciaMaxima;
    this.nosVisitados = 0;

    const linhaDaRaiz = Array.from({ length: m + 1 }, (_valor, j) => j);
    const candidatas = [];

    // O item carrega o caractere do nó e o do pai: a transposição compara os
    // dois últimos caracteres do caminho com dois vizinhos da consulta.
    const pilha = [];
    for (const [caractere, filho] of this.raiz.filhos) {
      pilha.push({
        no: filho, caminho: caractere, profundidade: 1, atual: caractere, previo: null,
        anterior: linhaDaRaiz, avo: null,
      });
    }

    while (pilha.length) {
      const item = pilha.pop();
      this.nosVisitados += 1;

      const { atual, previo, anterior, avo } = item;
      const linha = new Array(m + 1);
      linha[0] = item.profundidade;
      let menor = linha[0];

      for (let j = 1; j <= m; j += 1) {
        const custo = letras[j - 1] === atual ? 0 : 1;
        let valor = Math.min(linha[j - 1] + 1,          // inserção
                             anterior[j] + 1,           // remoção
                             anterior[j - 1] + custo);  // troca (ou acerto)
        if (avo !== null && j > 1 && atual === letras[j - 2] && previo === letras[j - 1]) {
          valor = Math.min(valor, avo[j - 2] + 1);      // transposição
        }
        linha[j] = valor;
        if (valor < menor) menor = valor;
      }

      if (item.no.fimDePalavra && linha[m] <= tolerancia) {
        candidatas.push({ distancia: linha[m], peso: item.no.peso, caminho: item.caminho, no: item.no });
      }

      if (menor <= tolerancia) {
        for (const [caractere, filho] of item.no.filhos) {
          pilha.push({
            no: filho, caminho: item.caminho + caractere, profundidade: item.profundidade + 1,
            atual: caractere, previo: atual, anterior: linha, avo: anterior,
          });
        }
      }
    }

    // A mesma ordem da tupla (distância, -peso, chave) do Python.
    candidatas.sort((a, b) => (a.distancia - b.distancia) || (b.peso - a.peso) ||
      ordemDeTexto(a.caminho, b.caminho));
    const escolhidas = limite == null ? candidatas : candidatas.slice(0, limite);
    return escolhidas.map((c) => [menorForma(c.no.formas), c.distancia, c.peso]);
  }

  /* -------------------------------------------------------------- métricas */

  /** Número de nós alocados -- métrica de memória usada no relatório. */
  totalNos() {
    return this._totalNos;
  }

  /** Comprimento do caminho mais longo, isto é, o tamanho da maior chave. */
  altura() {
    let maior = 0;
    const pilha = [[this.raiz, 0]];
    while (pilha.length) {
      const [no, profundidade] = pilha.pop();
      if (profundidade > maior) maior = profundidade;
      for (const filho of no.filhos.values()) pilha.push([filho, profundidade + 1]);
    }
    return maior;
  }

  get tamanho() {
    return this._totalPalavras;
  }
}

/* =========================================================================
   TRIE COMPRIMIDA (PATRICIA / RADIX TREE)
   ========================================================================= */

/**
 * Nó de uma Trie comprimida: a aresta guarda uma SUBSTRING, não um caractere.
 *
 * Numa cadeia sem bifurcação -- "e", "x", "c", "e", "ç", "ã", "o" para
 * "exceção" -- a Trie tradicional aloca sete nós; a comprimida aloca um só,
 * rotulado "excecao".
 */
class NoTrieComprimida {
  constructor(rotulo) {
    this.rotulo = rotulo || '';  // trecho da chave consumido nesta aresta
    this.filhos = new Map();     // primeiro caractere do rótulo -> nó filho
    this.fimDePalavra = false;
    this.formas = null;

    this.peso = 0;               // relevância da palavra que termina aqui
    this.palavrasAbaixo = 0;     // palavras armazenadas nesta subárvore
    this.melhorPeso = 0;         // maior peso encontrado nesta subárvore
  }
}

/**
 * Trie comprimida no estilo PATRICIA (Morrison, 1968).
 *
 * Colapsa cadeias de nós de filho único em uma única aresta rotulada com a
 * substring correspondente. Mesma linguagem reconhecida e mesmas
 * complexidades assintóticas da Trie tradicional -- O(m) para inserir e
 * buscar --, com consumo de memória bem menor.
 */
class TrieComprimida {
  constructor(palavras) {
    this.raiz = new NoTrieComprimida('');
    this._totalPalavras = 0;
    this._totalNos = 1;

    if (palavras) {
      for (const palavra of palavras) this.inserir(palavra);
    }
  }

  /** Comprimento do maior prefixo comum entre duas strings. */
  static prefixoComum(a, b) {
    const limite = Math.min(a.length, b.length);
    let i = 0;
    while (i < limite && a[i] === b[i]) i += 1;
    return i;
  }

  /**
   * Insere uma palavra, dividindo arestas quando a chave diverge no meio de
   * um rótulo. Três situações ao comparar o resto da chave com o rótulo:
   *
   *   1. o rótulo é consumido por inteiro  -> desce e continua;
   *   2. a chave termina no meio do rótulo -> divide a aresta e marca o nó
   *      de cima como fim de palavra;
   *   3. os dois divergem no meio          -> divide a aresta e cria um novo
   *      filho para o resto da chave.
   *
   * O(m).
   */
  inserir(palavra, peso) {
    const original = String(palavra).trim();
    if (!original) return false;

    const chave = normalizar(original);
    if (!chave) return false;

    const relevancia = (peso === undefined) ? 1 : peso;

    const caminho = [this.raiz];
    let no = this.raiz;
    let resto = chave;

    for (;;) {
      if (!resto) {
        const nova = !no.fimDePalavra;
        if (nova) {
          no.fimDePalavra = true;
          no.formas = new Set();
          this._totalPalavras += 1;
        }
        no.formas.add(original);
        return TrieComprimida.propagar(caminho, no, relevancia, nova);
      }

      const filho = no.filhos.get(resto[0]);

      if (filho === undefined) {
        // Nada em comum: uma única aresta nova carrega todo o resto.
        const novo = new NoTrieComprimida(resto);
        novo.fimDePalavra = true;
        novo.formas = new Set([original]);
        no.filhos.set(resto[0], novo);
        this._totalNos += 1;
        this._totalPalavras += 1;
        caminho.push(novo);
        return TrieComprimida.propagar(caminho, novo, relevancia, true);
      }

      const comum = TrieComprimida.prefixoComum(resto, filho.rotulo);

      if (comum === filho.rotulo.length) {
        // Caso 1: rótulo inteiramente consumido -- desce um nível.
        no = filho;
        caminho.push(no);
        resto = resto.slice(comum);
        continue;
      }

      // Casos 2 e 3: a aresta precisa ser dividida em `comum`.
      //
      // O intermediário HERDA os agregados do filho: ele passa a encabeçar a
      // mesma subárvore. Sem a herança a contagem se perderia a cada divisão.
      const intermediario = new NoTrieComprimida(filho.rotulo.slice(0, comum));
      intermediario.palavrasAbaixo = filho.palavrasAbaixo;
      intermediario.melhorPeso = filho.melhorPeso;
      no.filhos.set(resto[0], intermediario);
      this._totalNos += 1;

      filho.rotulo = filho.rotulo.slice(comum);
      intermediario.filhos.set(filho.rotulo[0], filho);
      caminho.push(intermediario);

      if (comum === resto.length) {
        // Caso 2: a chave termina exatamente no ponto da divisão.
        intermediario.fimDePalavra = true;
        intermediario.formas = new Set([original]);
        this._totalPalavras += 1;
        return TrieComprimida.propagar(caminho, intermediario, relevancia, true);
      }

      // Caso 3: sobra chave -- vira um segundo filho do intermediário.
      const sobra = resto.slice(comum);
      const novo = new NoTrieComprimida(sobra);
      novo.fimDePalavra = true;
      novo.formas = new Set([original]);
      intermediario.filhos.set(sobra[0], novo);
      this._totalNos += 1;
      this._totalPalavras += 1;
      caminho.push(novo);
      return TrieComprimida.propagar(caminho, novo, relevancia, true);
    }
  }

  /**
   * Atualiza os agregados da raiz até o nó de destino e devolve `nova`.
   * `caminho` termina no próprio destino, que também recebe o incremento.
   */
  static propagar(caminho, destino, peso, nova) {
    if (peso > destino.peso) destino.peso = peso;

    for (const ancestral of caminho) {
      if (nova) ancestral.palavrasAbaixo += 1;
      if (destino.peso > ancestral.melhorPeso) ancestral.melhorPeso = destino.peso;
    }
    return nova;
  }

  /**
   * Desce seguindo `texto`. Devolve [nó, sobraDoRotulo] ou null.
   *
   * `sobraDoRotulo` é o pedaço do rótulo que ficou além do texto buscado: se
   * for vazio, o texto terminou exatamente sobre o nó -- o que distingue
   * busca exata de busca por prefixo.
   */
  descer(texto) {
    let no = this.raiz;
    let resto = texto;

    while (resto) {
      const filho = no.filhos.get(resto[0]);
      if (filho === undefined) return null;

      if (resto.length < filho.rotulo.length) {
        // O texto acaba dentro do rótulo: só serve como prefixo.
        if (filho.rotulo.startsWith(resto)) {
          return [filho, filho.rotulo.slice(resto.length)];
        }
        return null;
      }

      if (!resto.startsWith(filho.rotulo)) return null;

      no = filho;
      resto = resto.slice(filho.rotulo.length);
    }

    return [no, ''];
  }

  /**
   * Busca exata. Exige sobra de rótulo vazia -- caso contrário a palavra é
   * apenas prefixo de alguma chave, e não uma chave armazenada. O(m).
   */
  buscar(palavra) {
    const achado = this.descer(normalizar(palavra));
    if (achado === null) return false;
    const [no, sobra] = achado;
    return sobra === '' && no.fimDePalavra;
  }

  /**
   * Palavras que começam com o prefixo, em ordem alfabética. O(m + p) -- a
   * mesma da Trie tradicional, mas com p menor, já que há menos nós.
   */
  buscarPrefixo(prefixo, limite) {
    const chave = normalizar(prefixo);
    const achado = this.descer(chave);
    if (achado === null) return [];

    const [no, sobra] = achado;
    const encontradas = [];
    const pilha = [[no, chave + sobra]];

    while (pilha.length) {
      if (limite != null && encontradas.length >= limite) break;
      const [atual, caminho] = pilha.pop();

      if (atual.fimDePalavra) {
        encontradas.push([caminho, menorForma(atual.formas)]);
      }

      const iniciais = Array.from(atual.filhos.keys()).sort(ordemDeTexto).reverse();
      for (const inicial of iniciais) {
        const filho = atual.filhos.get(inicial);
        pilha.push([filho, caminho + filho.rotulo]);
      }
    }

    // Já sai ordenado: rótulos irmãos começam por caracteres distintos, então
    // ordená-los pela inicial é ordená-los por inteiro.
    return encontradas.map((par) => par[1]);
  }

  /**
   * Quantas palavras começam com o prefixo. O(m), pela mesma razão da Trie
   * tradicional. Quando o prefixo termina no meio de um rótulo, o nó devolvido
   * é o dono daquela aresta -- e toda palavra da subárvore passa por ela.
   */
  contarPrefixo(prefixo) {
    const achado = this.descer(normalizar(prefixo));
    if (achado === null) return 0;
    return achado[0].palavrasAbaixo;
  }

  /** Número de nós alocados -- comparado com o da Trie tradicional. */
  totalNos() {
    return this._totalNos;
  }

  get tamanho() {
    return this._totalPalavras;
  }
}

export {
  normalizar, ordemDeTexto, distanciaEdicao, NoTrie, Trie, NoTrieComprimida, TrieComprimida,
};
