/* ===========================================================================
   indice-invertido.js
   Porte de `indice_invertido.py`: índice invertido, tabela hash didática e
   ranqueamento BM25 / TF-IDF.

   ---------------------------------------------------------------------------
   Por que "invertido"
   ---------------------------------------------------------------------------
   O índice natural de uma coleção é o DIRETO: documento -> palavras que ele
   contém. É assim que o arquivo está gravado em disco. Responder "em quais
   arquivos aparece a palavra X" com esse índice obriga a abrir e varrer todos
   os documentos, custo O(N * n).

   O índice INVERTIDO troca o papel de chave e valor: palavra -> documentos em
   que ela ocorre. A relação é a mesma, lida na direção oposta -- daí o nome.
   Com ele a mesma pergunta vira uma consulta de hash, O(1) em média,
   independentemente do tamanho da coleção.

       índice direto      algoritmos.txt -> {algoritmo, busca, dados, ...}
       índice invertido   algoritmo      -> {algoritmos.txt, complexidade.txt}

   ---------------------------------------------------------------------------
   Ranqueamento: TF-IDF e BM25
   ---------------------------------------------------------------------------
   O índice responde QUAIS documentos contêm o termo, não em que ORDEM
   apresentá-los.

     * TF-IDF -- Spärck Jones, K. "A statistical interpretation of term
       specificity and its application in retrieval". Journal of Documentation,
       28(1):11-21, 1972.
     * BM25 (Okapi BM25) -- Robertson, S. E. et al. "Okapi at TREC-3", 1994;
       Robertson, S. E.; Zaragoza, H. "The Probabilistic Relevance Framework:
       BM25 and Beyond". FnTIR, 3(4):333-389, 2009.

   O BM25 corrige duas fraquezas do TF-IDF puro: satura a frequência do termo
   (a décima ocorrência vale muito menos que a segunda) e normaliza pelo
   tamanho do documento, para que textos longos não dominem o ranking só por
   serem longos.
   =========================================================================== */

import { ordemDeTexto } from './trie.js';

/* =========================================================================
   TABELA HASH DIDÁTICA
   ========================================================================= */

/**
 * Tabela hash com tratamento de colisão por encadeamento separado.
 *
 * O sistema em produção usa o `Map` da linguagem, como o enunciado autoriza.
 * Esta classe existe para tornar visível o que o `Map` faz por baixo e para
 * permitir MEDIR o fenômeno das colisões, em vez de apenas descrevê-lo.
 *
 * --- Função hash ---
 * Hash polinomial avaliada pelo esquema de Horner, a mesma família empregada
 * em `String.hashCode` do Java:
 *
 *     h(s) = (s[0]*B^(m-1) + s[1]*B^(m-2) + ... + s[m-1]) mod C
 *
 * A base B é um primo ímpar, o que espalha bem cadeias parecidas: "casa" e
 * "caso" caem em posições distantes, apesar de diferirem em uma letra.
 *
 * --- Colisões ---
 * Como o conjunto de chaves possíveis é infinito e o de posições é finito,
 * duas chaves distintas inevitavelmente vão para a mesma posição. Isso não é
 * defeito da função: é o princípio da casa dos pombos. O que se pode fazer é
 * tratá-la bem -- aqui, encadeando os pares (chave, valor) em uma lista.
 *
 * --- Complexidade ---
 * Com boa dispersão e fator de carga α = n/C mantido baixo, o comprimento
 * médio das listas é α e a busca é O(1 + α) = O(1) em média. No pior caso --
 * todas as chaves colidindo -- a tabela degenera em lista ligada e a busca
 * vira O(n). É para evitar esse cenário que ela redimensiona.
 */
class TabelaHash {
  static get BASE() { return 31; }             // base da hash polinomial
  static get CARGA_MAXIMA() { return 0.75; }

  constructor(capacidade = 1024) {
    this.capacidade = capacidade;
    this.baldes = Array.from({ length: capacidade }, () => []);
    this.n = 0;
    this.colisoes = 0;     // inserções que caíram em balde já ocupado
    this.sondagens = 0;    // comparações feitas dentro dos baldes
  }

  /**
   * Hash polinomial pelo esquema de Horner. O(m) no tamanho da chave.
   *
   * `Math.imul` faz a multiplicação em 32 bits com wrap-around, que é o
   * equivalente exato do `& 0xFFFFFFFF` da versão Python -- sem isso o
   * número viraria ponto flutuante e perderia os dígitos baixos, que são
   * justamente os que a hash usa.
   */
  _hash(chave) {
    let h = 0;
    for (let i = 0; i < chave.length; i += 1) {
      h = (Math.imul(h, TabelaHash.BASE) + chave.charCodeAt(i)) >>> 0;
    }
    return h % this.capacidade;
  }

  /** Insere ou atualiza uma chave. O(1) em média. */
  inserir(chave, valor) {
    const indice = this._hash(chave);
    const balde = this.baldes[indice];

    for (let posicao = 0; posicao < balde.length; posicao += 1) {
      this.sondagens += 1;
      if (balde[posicao][0] === chave) {
        balde[posicao] = [chave, valor];
        return false;
      }
    }

    if (balde.length) this.colisoes += 1;   // já havia algo aqui
    balde.push([chave, valor]);
    this.n += 1;

    if (this.n / this.capacidade > TabelaHash.CARGA_MAXIMA) this._redimensionar();
    return true;
  }

  /** Recupera o valor associado à chave. O(1) em média, O(n) no pior caso. */
  buscar(chave, padrao = null) {
    const balde = this.baldes[this._hash(chave)];
    for (const [chaveAtual, valor] of balde) {
      this.sondagens += 1;
      if (chaveAtual === chave) return valor;
    }
    return padrao;
  }

  /**
   * Dobra a capacidade e reinsere tudo.
   *
   * A operação custa O(n), mas acontece cada vez mais raramente conforme a
   * tabela cresce. Diluído sobre as n inserções, o custo AMORTIZADO por
   * inserção continua O(1) -- o mesmo argumento que sustenta o `push` de
   * vetores dinâmicos.
   */
  _redimensionar() {
    const antigos = this.baldes;
    this.capacidade *= 2;
    this.baldes = Array.from({ length: this.capacidade }, () => []);
    this.n = 0;
    this.colisoes = 0;
    for (const balde of antigos) {
      for (const [chave, valor] of balde) this.inserir(chave, valor);
    }
  }

  /** Métricas de dispersão, usadas na seção de hash do relatório. */
  estatisticas() {
    const ocupados = this.baldes.filter((b) => b.length).map((b) => b.length);
    const soma = ocupados.reduce((a, b) => a + b, 0);
    const arredondar = (v, casas) => Number(v.toFixed(casas));
    return {
      chaves: this.n,
      capacidade: this.capacidade,
      'fator de carga': arredondar(this.n / this.capacidade, 3),
      'baldes ocupados': ocupados.length,
      colisoes: this.colisoes,
      'maior cadeia': ocupados.length ? Math.max(...ocupados) : 0,
      'cadeia media': ocupados.length ? arredondar(soma / ocupados.length, 3) : 0,
    };
  }

  /** Distribuição dos comprimentos de cadeia, para o histograma da tela. */
  distribuicaoDeCadeias() {
    const contagem = new Map();
    for (const balde of this.baldes) {
      contagem.set(balde.length, (contagem.get(balde.length) || 0) + 1);
    }
    return Array.from(contagem.entries())
      .sort((a, b) => a[0] - b[0])
      .map(([tamanho, baldes]) => ({ tamanho, baldes }));
  }
}

/* =========================================================================
   ÍNDICE INVERTIDO
   ========================================================================= */

/**
 * Índice invertido com duas chaves de acesso e ranqueamento por relevância.
 *
 * --- Por que dois índices ---
 * `porTermo` guarda a palavra exata como aparece no texto, atendendo ao que
 * a seção 3.5 do enunciado pede literalmente. `porRadical` guarda o radical
 * produzido pelo RSLP, o que faz "algoritmo" encontrar "algoritmos" -- sem
 * isso o exemplo da seção 3.7.1 do próprio enunciado não funcionaria.
 *
 * --- Estrutura ---
 *     Map{ termo -> Map{ documento -> frequência } }
 *
 * Guardar a frequência, e não só o conjunto de documentos, é o que torna
 * possível ranquear. O custo extra de memória é pequeno e habilita TF-IDF e
 * BM25.
 *
 * --- Complexidade ---
 *     indexar documento     O(t), com t = tokens do documento
 *     buscar termo          O(1) em média
 *     ranquear consulta     O(q * d)
 */
class IndiceInvertido {
  // Parâmetros do BM25, os recomendados por Robertson & Zaragoza (2009) e
  // padrões de Lucene e Elasticsearch.
  static get K1() { return 1.5; }   // saturação da frequência do termo
  static get B() { return 0.75; }   // peso da normalização por tamanho

  constructor() {
    this.porTermo = new Map();          // palavra exata -> Map{doc: freq}
    this.porRadical = new Map();        // radical RSLP  -> Map{doc: freq}
    this.documentos = [];               // nomes, na ordem de indexação
    this.tamanhoDocumento = new Map();  // documento -> tokens indexados
    this.totalTokens = 0;
  }

  /* ----------------------------------------------------------- construção */

  /**
   * Adiciona um documento ao índice, percorrendo os tokens uma única vez e
   * alimentando os dois índices em paralelo. O(t).
   */
  indexar(documento, tokens, preprocessador) {
    if (!this.tamanhoDocumento.has(documento)) this.documentos.push(documento);

    this.tamanhoDocumento.set(documento, tokens.length);
    this.totalTokens += tokens.length;

    for (const token of tokens) {
      const chaveExata = token.toLowerCase();
      let postagem = this.porTermo.get(chaveExata);
      if (postagem === undefined) {
        postagem = new Map();
        this.porTermo.set(chaveExata, postagem);
      }
      postagem.set(documento, (postagem.get(documento) || 0) + 1);

      const chaveRadical = preprocessador.radicalizar(token);
      postagem = this.porRadical.get(chaveRadical);
      if (postagem === undefined) {
        postagem = new Map();
        this.porRadical.set(chaveRadical, postagem);
      }
      postagem.set(documento, (postagem.get(documento) || 0) + 1);
    }
  }

  /* ---------------------------------------------------------------- busca */

  /**
   * Documentos em que o termo aparece, com a frequência em cada um.
   *
   * Devolve um objeto simples {documento: frequência}, vazio se o termo não
   * existir -- objeto, e não Map, porque é o formato que a interface desenha
   * e o mesmo que as rotas JSON do `servidor.py` devolvem. O(1) em média.
   */
  buscar(termo, usarRadical = true) {
    const indice = usarRadical ? this.porRadical : this.porTermo;
    const postagem = indice.get(termo);
    if (postagem === undefined) return {};
    return Object.fromEntries(postagem);
  }

  /** Em quantos documentos o termo aparece (o df da literatura de RI). */
  frequenciaDocumental(termo, usarRadical = true) {
    const indice = usarRadical ? this.porRadical : this.porTermo;
    const postagem = indice.get(termo);
    return postagem === undefined ? 0 : postagem.size;
  }

  /* ---------------------------------------------------------- ranqueamento */

  /**
   * Frequência inversa de documento, na formulação probabilística do BM25.
   *
   *     IDF(t) = ln( (N - df + 0.5) / (df + 0.5) + 1 )
   *
   * O "+1" dentro do logaritmo é a correção adotada pelo Lucene: sem ela um
   * termo presente em mais da metade da coleção receberia peso negativo, e
   * um documento perderia pontos por conter o termo buscado.
   *
   * A intuição de Spärck Jones (1972) está no numerador: quanto MENOR o
   * número de documentos que contêm o termo, MAIOR o seu poder de
   * discriminação.
   */
  idf(termo, usarRadical = true) {
    const n = this.documentos.length;
    const df = this.frequenciaDocumental(termo, usarRadical);
    if (df === 0) return 0;
    return Math.log((n - df + 0.5) / (df + 0.5) + 1);
  }

  /** Tamanho médio dos documentos em tokens -- o avgdl da fórmula BM25. */
  tamanhoMedio() {
    if (!this.documentos.length) return 0;
    return this.totalTokens / this.documentos.length;
  }

  /**
   * Ordena os documentos por relevância, usando BM25.
   *
   *                            f(t,D) * (k1 + 1)
   *     score(D,Q) = Σ IDF(t) ------------------------------------------
   *                  t∈Q      f(t,D) + k1 * (1 - b + b * |D| / avgdl)
   *
   * Leitura dos três fatores:
   *   * IDF(t)           -- termos raros pesam mais;
   *   * saturação (k1)   -- repetir a palavra ajuda, com retorno
   *                         decrescente: de 1 para 2 ocorrências o ganho é
   *                         grande, de 20 para 21 é quase nulo;
   *   * normalização (b) -- documentos mais longos que a média têm o score
   *                         reduzido, porque acumulam ocorrências apenas por
   *                         serem grandes.
   *
   * Devolve [[documento, score], ...] em ordem decrescente. O(q * d).
   */
  ranquearBm25(termos, usarRadical = true) {
    const tamanhoMedio = this.tamanhoMedio();
    if (!tamanhoMedio) return [];

    const pontuacoes = new Map();
    for (const termo of termos) {
      const idf = this.idf(termo, usarRadical);
      if (idf === 0) continue;

      const indice = usarRadical ? this.porRadical : this.porTermo;
      const postagem = indice.get(termo);
      if (postagem === undefined) continue;

      for (const [documento, frequencia] of postagem) {
        const normalizacao = 1 - IndiceInvertido.B + IndiceInvertido.B *
          (this.tamanhoDocumento.get(documento) / tamanhoMedio);
        const contribuicao = idf * (frequencia * (IndiceInvertido.K1 + 1)) /
          (frequencia + IndiceInvertido.K1 * normalizacao);
        pontuacoes.set(documento, (pontuacoes.get(documento) || 0) + contribuicao);
      }
    }

    return Array.from(pontuacoes.entries())
      .sort((a, b) => (b[1] - a[1]) || ordemDeTexto(a[0], b[0]));
  }

  /**
   * Ranqueamento TF-IDF clássico, mantido para comparação com o BM25.
   *
   *     peso(t,D) = (1 + log10 f(t,D)) * log10(N / df(t))
   *
   * A diferença prática aparece em documentos longos: sem o fator de
   * normalização por tamanho, o TF-IDF tende a favorecê-los.
   */
  ranquearTfidf(termos, usarRadical = true) {
    const n = this.documentos.length;
    if (!n) return [];

    const pontuacoes = new Map();
    for (const termo of termos) {
      const df = this.frequenciaDocumental(termo, usarRadical);
      if (df === 0) continue;
      const idf = Math.log10(n / df);

      const indice = usarRadical ? this.porRadical : this.porTermo;
      for (const [documento, frequencia] of indice.get(termo)) {
        const peso = (1 + Math.log10(frequencia)) * idf;
        pontuacoes.set(documento, (pontuacoes.get(documento) || 0) + peso);
      }
    }

    return Array.from(pontuacoes.entries())
      .sort((a, b) => (b[1] - a[1]) || ordemDeTexto(a[0], b[0]));
  }

  /* -------------------------------------------------------------- métricas */

  /** Número de chaves distintas em um dos dois índices. */
  totalTermos(usarRadical = true) {
    return (usarRadical ? this.porRadical : this.porTermo).size;
  }

  /**
   * Número de pares (termo, documento) armazenados.
   *
   * É a medida real de tamanho do índice: um termo que aparece em 10
   * documentos ocupa 10 postagens, não 1.
   */
  totalPostagens(usarRadical = true) {
    const indice = usarRadical ? this.porRadical : this.porTermo;
    let total = 0;
    for (const postagem of indice.values()) total += postagem.size;
    return total;
  }

  /**
   * Copia o índice para a `TabelaHash` própria, para medir colisões e
   * comprimento de cadeia sobre dados reais. O sistema continua operando
   * sobre o `Map`.
   */
  espelharEmTabelaHash(usarRadical = true) {
    const indice = usarRadical ? this.porRadical : this.porTermo;
    const tabela = new TabelaHash(1024);
    for (const [termo, postagem] of indice) tabela.inserir(termo, postagem);
    return tabela;
  }

  /** Os termos mais frequentes do índice, para a tela de métricas. */
  termosMaisFrequentes(quantos = 12, usarRadical = true) {
    const indice = usarRadical ? this.porRadical : this.porTermo;
    const linhas = [];
    for (const [termo, postagem] of indice) {
      let total = 0;
      for (const frequencia of postagem.values()) total += frequencia;
      linhas.push({ termo, documentos: postagem.size, ocorrencias: total });
    }
    linhas.sort((a, b) => (b.ocorrencias - a.ocorrencias) ||
      ordemDeTexto(a.termo, b.termo));
    return linhas.slice(0, quantos);
  }
}

export { TabelaHash, IndiceInvertido };
