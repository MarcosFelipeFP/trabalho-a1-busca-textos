/* ===========================================================================
   mecanismo.js
   Porte de `mecanismo.py` e da classe `Aplicacao` de `servidor.py`: integra
   todas as peças da Parte II e expõe as mesmas operações que as rotas JSON do
   servidor oferecem.

   ---------------------------------------------------------------------------
   O caminho de uma consulta
   ---------------------------------------------------------------------------
       palavra exata   consulta -> RSLP -> radical -> índice (hash) -> documentos
                       O(1) em média

       prefixo         prefixo -> Trie -> termos do vocabulário -> RSLP ->
                       índice (hash) -> documentos
                       O(m + p) na Trie, mais O(1) por termo recuperado

       sequência       padrão -> KMP sobre o texto ORIGINAL de cada documento
                       O(n + m) por documento

   A terceira difere das outras em natureza: não passa pelo índice. Varre o
   conteúdo bruto, por isso encontra o que a indexação descarta -- pedaços de
   palavra, pontuação, números -- ao custo de ser linear no tamanho do corpus.

   ---------------------------------------------------------------------------
   Por que as respostas usam chaves com underline
   ---------------------------------------------------------------------------
   `total_disponivel`, `total_ocorrencias`, `por_termo`: não é descuido de
   estilo. São exatamente as chaves que as rotas de `servidor.py` devolvem, e
   manter os dois formatos idênticos é o que permite à interface trocar de
   motor -- Python ou JavaScript -- sem uma linha de adaptação no meio.
   =========================================================================== */

import { Cronometro, Estatisticas, formatarDuracao, medir } from './estatisticas.js';
import { IndiceInvertido } from './indice-invertido.js';
import { buscarKmp, contextoDaOcorrencia } from './kmp.js';
import { Preprocessador } from './preprocessamento.js';
import { Trie, TrieComprimida, normalizar, ordemDeTexto } from './trie.js';

/** Ordena nomes de documento, como o `sorted` do Python faz. */
const ordenarNomes = (nomes) => Array.from(nomes).sort(ordemDeTexto);

/**
 * Mecanismo de busca sobre uma coleção de documentos.
 *
 * No Python a coleção é uma pasta varrida com `Path.glob("*.txt")`; aqui é a
 * lista que `gerar_dados_web.py` produziu a partir daquela mesma varredura.
 * Nenhum nome de arquivo aparece no código nos dois casos, que é o que a
 * seção 3.2 do enunciado exige.
 */
class MecanismoBusca {
  constructor({ documentos = [], stopwords = [], usarStemming = true } = {}) {
    this.documentosBrutos = documentos;
    this.preprocessador = new Preprocessador({ stopwords, usarStemming });
    this.indice = new IndiceInvertido();
    this.trie = new Trie();                      // vocabulário do autocomplete
    this.trieComprimida = new TrieComprimida();  // mesma coisa, para comparar
    this.estatisticas = new Estatisticas();

    // O texto original de cada documento fica em memória porque a busca por
    // sequência (KMP) trabalha sobre o conteúdo bruto, não sobre os tokens.
    this.conteudo = new Map();

    // A versão em caixa baixa é calculada UMA vez, na indexação. A busca por
    // sequência ignora maiúsculas, e baixar a caixa do corpus inteiro custa
    // O(N) -- fazer isso dentro da consulta significava pagar esse O(N) a
    // cada tecla digitada, trabalho que superava o do próprio KMP.
    this.conteudoMinusculo = new Map();

    this.tamanhos = new Map();
    this.vocabulario = new Set();
    this.frequencia = new Map();   // token -> ocorrências no corpus inteiro
  }

  /* ------------------------------------------------------------ construção */

  /**
   * Executa o pipeline completo, cronometrando cada fase, e PAUSA entre os
   * documentos.
   *
   * A versão Python é uma função só: constrói tudo e devolve. No navegador
   * isso trava a tela por cerca de um segundo, sem nada na tela explicando o
   * porquê. Como gerador, cada `yield` devolve o andamento e devolve o
   * controle ao navegador, que aproveita para desenhar a barra de progresso.
   *
   * O trabalho e a ordem são os mesmos; só o momento de ceder a vez muda.
   * Complexidade O(N + V*m), com N = tokens do corpus, V = vocabulário e
   * m = tamanho médio das palavras.
   */
  * construirEmEtapas() {
    const documentos = this.documentosBrutos;
    if (!documentos.length) return 0;

    const tokensPorDocumento = new Map();

    // --- fases 1 e 2: leitura e pré-processamento ---
    let posicao = 0;
    for (const documento of documentos) {
      posicao += 1;
      yield { fase: 'leitura', nome: documento.nome, posicao, total: documentos.length };

      const relogioLeitura = Cronometro.iniciar();
      const texto = documento.texto;
      this.conteudo.set(documento.nome, texto);
      this.conteudoMinusculo.set(documento.nome, texto.toLowerCase());
      this.tamanhos.set(documento.nome, documento.bytes ?? texto.length);
      this.estatisticas.tempoLeitura += relogioLeitura.parar();

      const relogio = Cronometro.iniciar();
      const [brutos, tokens] = this.preprocessador.processarDetalhado(texto);
      this.estatisticas.tempoPreprocessamento += relogio.parar();

      tokensPorDocumento.set(documento.nome, tokens);
      this.estatisticas.totalPalavrasBrutas += brutos.length;
      this.estatisticas.totalPalavras += tokens.length;
      for (const token of tokens) {
        this.vocabulario.add(token);
        // Contagem de frequência na mesma passada: O(t). É ela que dá ao
        // autocomplete o critério de relevância.
        this.frequencia.set(token, (this.frequencia.get(token) || 0) + 1);
      }
    }

    // --- fase 3: construção da Trie a partir do vocabulário ---
    // Ordenar antes de inserir mantém o resultado determinístico e permite
    // repetir a medição de tempo em condições idênticas.
    const vocabularioOrdenado = ordenarNomes(this.vocabulario);
    yield { fase: 'trie', posicao: 0, total: vocabularioOrdenado.length };

    // Duas grafias diferentes ("computação" e "computacao") viram a mesma
    // chave na Trie; os pesos delas precisam somar, não competir. O peso de
    // cada palavra fica pronto ANTES do cronômetro: normalizar a chave para
    // consultar a soma não é trabalho da Trie.
    const pesoDaChave = new Map();
    for (const [token, ocorrencias] of this.frequencia) {
      const chave = normalizar(token);
      pesoDaChave.set(chave, (pesoDaChave.get(chave) || 0) + ocorrencias);
    }
    const pesos = vocabularioOrdenado.map((palavra) => pesoDaChave.get(normalizar(palavra)) || 1);

    const relogioTrie = Cronometro.iniciar();
    vocabularioOrdenado.forEach((palavra, posicao) => this.trie.inserir(palavra, pesos[posicao]));
    this.estatisticas.tempoTrie = relogioTrie.parar();

    yield { fase: 'trie-comprimida', posicao: 0, total: vocabularioOrdenado.length };
    for (const palavra of vocabularioOrdenado) this.trieComprimida.inserir(palavra);

    // --- fase 4: construção do índice invertido ---
    yield { fase: 'indice', posicao: 0, total: documentos.length };

    const relogioIndice = Cronometro.iniciar();
    for (const [documento, tokens] of tokensPorDocumento) {
      this.indice.indexar(documento, tokens, this.preprocessador);
    }
    this.estatisticas.tempoIndice = relogioIndice.parar();

    // --- métricas finais ---
    this.estatisticas.documentos = documentos.length;
    this.estatisticas.termosDistintos = this.vocabulario.size;
    this.estatisticas.palavrasNaTrie = this.trie.tamanho;
    this.estatisticas.nosNaTrie = this.trie.totalNos();
    this.estatisticas.nosNaTrieComprimida = this.trieComprimida.totalNos();
    this.estatisticas.postagens = this.indice.totalPostagens();

    return documentos.length;
  }

  /** Drena o gerador de uma vez só -- o caminho que os testes usam. */
  construir() {
    const etapas = this.construirEmEtapas();
    let passo = etapas.next();
    while (!passo.done) passo = etapas.next();
    return passo.value || 0;
  }

  /* -------------------------------------------------------- consulta exata */

  /**
   * Consulta por palavra (seção 3.7.1), com um ou mais termos.
   *
   * Cada palavra digitada passa pelo MESMO pré-processamento aplicado aos
   * documentos e vira um radical, a chave consultada no índice -- é o que
   * permite "algoritmo" encontrar "algoritmos".
   *
   * Com vários termos, cada um é uma consulta O(1) ao índice, e os resultados
   * são combinados em duas leituras: `documentos` traz todo documento com
   * ALGUM termo, primeiro os que contêm mais termos e depois pelo BM25 da
   * consulta inteira; `todos` traz só os que contêm TODOS, por interseção que
   * começa pela menor lista -- O(q·d_min), limitada pelo termo mais raro.
   *
   * Termo sem documento nenhum ganha sugestões por distância de edição,
   * buscadas na Trie do vocabulário e cronometradas à parte.
   */
  buscarPalavra(consulta, ranquear = true) {
    const medida = medir(() => {
      const [termos, ignorados] = this.preprocessador.termosDaConsulta(consulta);

      const detalhes = [];     // um por radical distinto, na ordem digitada
      const postagens = [];    // [radical, Map{documento: frequência}]
      const vistos = new Set();
      for (const termo of termos) {
        const radical = this.preprocessador.radicalizar(termo);
        if (vistos.has(radical)) continue;   // "algoritmo algoritmos" é um termo só
        vistos.add(radical);
        const postagem = this.indice.porRadical.get(radical) || new Map();
        postagens.push([radical, postagem]);
        detalhes.push({
          termo, radical, documentos: postagem.size,
          exatos: this.indice.frequenciaDocumental(termo.toLowerCase(), false),
        });
      }

      const cobertura = new Map();     // documento -> termos da consulta que contém
      const frequencias = new Map();   // documento -> ocorrências somadas
      for (const [, postagem] of postagens) {
        for (const [documento, frequencia] of postagem) {
          cobertura.set(documento, (cobertura.get(documento) || 0) + 1);
          frequencias.set(documento, (frequencias.get(documento) || 0) + frequencia);
        }
      }

      // Interseção a partir da menor postagem.
      const listas = postagens.map(([, postagem]) => postagem).sort((a, b) => a.size - b.size);
      const todos = (listas.length && listas[0].size)
        ? ordenarNomes(Array.from(listas[0].keys())
          .filter((documento) => listas.slice(1).every((outra) => outra.has(documento))))
        : [];

      const pontuacao = (ranquear && cobertura.size)
        ? new Map(this.indice.ranquearBm25(postagens.map(([radical]) => radical)))
        : new Map();
      const documentos = Array.from(cobertura.keys())
        .map((documento) => [documento, pontuacao.get(documento) || 0])
        .sort((a, b) => (cobertura.get(b[0]) - cobertura.get(a[0])) || (b[1] - a[1]) ||
          ordemDeTexto(a[0], b[0]));

      return {
        ignorados, detalhes, documentos, todos,
        frequencias: Object.fromEntries(frequencias),
        cobertura: Object.fromEntries(cobertura),
      };
    });

    const { ignorados, detalhes, documentos, todos, frequencias, cobertura } = medida.resultado;

    // Fora do cronômetro da consulta: o "você quis dizer?" só roda quando falta
    // resultado, e o seu custo não é o custo O(1) do índice.
    const aproximacao = medir(() => {
      const achadas = new Map();
      for (const detalhe of detalhes) {
        if (detalhe.documentos === 0) achadas.set(detalhe.termo, this.sugerirCorrecao(detalhe.termo));
      }
      return achadas;
    }, { alvoMs: 0 });
    const aproximadas = aproximacao.resultado;

    // A consulta corrigida troca cada termo sem resultado pela sugestão mais
    // próxima e mantém as demais palavras, stopwords inclusive, no lugar.
    let correcao = null;
    if (Array.from(aproximadas.values()).some((lista) => lista.length)) {
      correcao = this.preprocessador.processarConsulta(consulta)
        .map((token) => (aproximadas.get(token)?.length ? aproximadas.get(token)[0][0] : token))
        .join(' ');
    }

    const primeiro = detalhes[0] || null;
    const resposta = {
      consulta,
      termo: primeiro ? primeiro.termo : consulta,
      radical: primeiro ? primeiro.radical : null,
      termos: detalhes,
      ignorados,
      documentos,
      frequencias,
      cobertura,
      todos,
      aproximadas: Object.fromEntries(aproximadas),
      correcao,
      tempo: medida.tempo,
      repeticoes: medida.repeticoes,
      tempo_aproximacao: aproximacao.tempo,
    };
    this.estatisticas.registrarConsulta('palavra', consulta, documentos.length, medida.tempo);
    return resposta;
  }

  /**
   * Palavras do vocabulário parecidas com `termo`, para o "você quis dizer?".
   * Só entram as que levam a algum documento e que não são o próprio termo.
   * Devolve trios [palavra, distância, frequência].
   */
  sugerirCorrecao(termo, limite = 5) {
    const sugestoes = [];
    for (const [palavra, distancia, peso] of this.trie.buscarAproximado(termo, null, null)) {
      if (distancia === 0) continue;
      if (!this.indice.frequenciaDocumental(this.preprocessador.radicalizar(palavra))) continue;
      sugestoes.push([palavra, distancia, peso]);
      if (sugestoes.length >= limite) break;
    }
    return sugestoes;
  }

  /* ------------------------------------------------------ consulta prefixo */

  /**
   * Consulta por prefixo (seção 3.7.2): a integração Trie + índice.
   *
   *   1. a Trie devolve os termos do vocabulário que começam com o prefixo;
   *   2. para cada termo, o índice informa em que documentos ele aparece.
   *
   * O(m + p) na Trie, mais O(1) por termo no índice.
   *
   * Além da lista alfabética que o enunciado pede, a resposta traz as
   * `sugestoes`: as palavras mais frequentes no corpus que começam com o
   * prefixo, pela busca best-first da Trie -- sem varrer a subárvore.
   */
  buscarPrefixo(prefixo, limite = 50) {
    const medida = medir(() => {
      const termos = this.trie.buscarPrefixo(prefixo, limite);
      const totalDisponivel = this.trie.contarPrefixo(prefixo);
      const sugestoes = this.trie.sugerir(prefixo, 10);

      const porTermo = {};
      const documentos = new Set();
      const radicais = new Set();
      for (const termo of termos) {
        const radical = this.preprocessador.radicalizar(termo);
        radicais.add(radical);
        const encontrados = Object.keys(this.indice.buscar(radical, true));
        porTermo[termo] = ordenarNomes(encontrados);
        for (const documento of encontrados) documentos.add(documento);
      }

      const ranking = radicais.size
        ? this.indice.ranquearBm25(ordenarNomes(radicais))
        : [];

      return {
        prefixo,
        termos,
        sugestoes,
        total_disponivel: totalDisponivel,
        truncado: totalDisponivel > termos.length,
        por_termo: porTermo,
        documentos: ordenarNomes(documentos),
        ranking,
      };
    });

    const resposta = medida.resultado;
    resposta.tempo = medida.tempo;
    resposta.repeticoes = medida.repeticoes;
    this.estatisticas.registrarConsulta(
      'prefixo', prefixo, resposta.termos.length, medida.tempo);
    return resposta;
  }

  /* --------------------------------------------------- consulta sequência */

  /**
   * Consulta por sequência de caracteres com KMP (seção 3.7.3).
   *
   * Procura o padrão diretamente no conteúdo ORIGINAL dos documentos, sem
   * tokenização nem índice. Por isso encontra o que a indexação não alcança:
   * fragmentos de palavra, expressões com pontuação, trechos no meio de um
   * termo.
   *
   * O(n + m) por documento, portanto O(N + D*m) no corpus inteiro -- linear,
   * mas sem o O(1) que o índice oferece. É o preço de não depender de
   * estrutura pré-construída.
   */
  buscarSequencia(sequencia, ignorarCaixa = true, maxContextos = 3) {
    const medida = medir(() => {
      const padrao = ignorarCaixa ? sequencia.toLowerCase() : sequencia;
      const resultados = [];
      let totalOcorrencias = 0;
      let totalComparacoes = 0;

      for (const documento of ordenarNomes(this.conteudo.keys())) {
        const texto = this.conteudo.get(documento);
        // Sem recalcular: a cópia em caixa baixa foi feita na indexação.
        const alvo = ignorarCaixa ? this.conteudoMinusculo.get(documento) : texto;

        const encontrado = buscarKmp(alvo, padrao);
        totalComparacoes += encontrado.comparacoes;
        if (!encontrado.ocorrencias.length) continue;

        totalOcorrencias += encontrado.ocorrencias.length;
        const contextos = encontrado.ocorrencias.slice(0, maxContextos).map(
          (posicao) => contextoDaOcorrencia(texto, posicao, padrao.length));

        resultados.push({
          documento,
          ocorrencias: encontrado.ocorrencias.length,
          posicoes: encontrado.ocorrencias,
          contextos,
        });
      }

      resultados.sort((a, b) => (b.ocorrencias - a.ocorrencias) ||
        ordemDeTexto(a.documento, b.documento));

      return {
        sequencia,
        resultados,
        total_ocorrencias: totalOcorrencias,
        comparacoes: totalComparacoes,
      };
    }, { alvoMs: 0 });   // o KMP varre o corpus inteiro: uma execução basta

    const resposta = medida.resultado;
    resposta.tempo = medida.tempo;
    resposta.repeticoes = medida.repeticoes;
    this.estatisticas.registrarConsulta(
      'sequencia', sequencia, resposta.resultados.length, medida.tempo);
    return resposta;
  }

  /* ------------------------------------------------------------- apoio */

  /** Nome, tamanho em bytes e total de tokens indexados de cada documento. */
  resumoDocumentos() {
    return ordenarNomes(this.conteudo.keys()).map((documento) => ({
      documento,
      bytes: this.tamanhos.get(documento) || 0,
      tokens: this.indice.tamanhoDocumento.get(documento) || 0,
    }));
  }
}

/* =========================================================================
   APLICAÇÃO -- o mesmo estado que `servidor.Aplicacao` mantém
   ========================================================================= */

/**
 * Reúne as estruturas das duas partes, construídas uma única vez.
 *
 * O custo de indexar o corpus é pago na abertura da página, não a cada
 * consulta -- é exatamente essa a proposta do índice invertido, e repetir a
 * construção por consulta inverteria o resultado de todas as medições.
 */
class Aplicacao {
  constructor({ documentos, lexico, stopwords, usarStemming = true } = {}) {
    this.lexico = lexico || [];
    this.usarStemming = usarStemming;

    // --- Parte I: Trie do léxico, a mesma que `main.py --parte 1` monta ---
    const relogio = Cronometro.iniciar();
    this.trie = new Trie();
    for (const palavra of this.lexico) this.trie.inserir(palavra);
    this.tempoTrie = relogio.parar();

    // --- Parte II: mecanismo de busca sobre os documentos ---
    this.mecanismo = new MecanismoBusca({ documentos, stopwords, usarStemming });
  }

  /** Constrói a Parte II em etapas, para a tela poder mostrar o andamento. */
  * construirEmEtapas() {
    yield* this.mecanismo.construirEmEtapas();
  }

  /* ---------------------------------------------------------------- estado */

  /** Números que a interface mostra no cabeçalho, antes de qualquer consulta. */
  estado() {
    const e = this.mecanismo.estatisticas;
    return {
      parte1: {
        lexico: 'palavras.txt',
        palavras: this.trie.tamanho,
        nos: this.trie.totalNos(),
        altura: this.trie.altura(),
        tempo_construcao: this.tempoTrie,
      },
      parte2: {
        pasta: 'documentos/',
        documentos: e.documentos,
        palavras: e.totalPalavras,
        palavras_brutas: e.totalPalavrasBrutas,
        termos: e.termosDistintos,
        radicais: this.mecanismo.indice.totalTermos(),
        postagens: e.postagens,
        stemming: this.mecanismo.preprocessador.usarStemming,
        tempo_construcao: e.tempoTotalConstrucao(),
      },
    };
  }

  /* --------------------------------------------------------------- Parte I */

  /**
   * Parte I, seção 2.3: as palavras do léxico que começam com o prefixo.
   *
   * A cronometragem cerca apenas as duas operações da Trie -- descer o
   * prefixo e varrer a subárvore.
   */
  autocompletar(prefixo, limite = 60) {
    const medida = medir(() => ({
      palavras: this.trie.buscarPrefixo(prefixo, limite),
      total: this.trie.contarPrefixo(prefixo),
    }));

    const { palavras, total } = medida.resultado;
    return {
      prefixo,
      palavras,
      total,
      truncado: total > palavras.length,
      tempo: medida.tempo,
      repeticoes: medida.repeticoes,
    };
  }

  /** Parte I, seção 2.3: a palavra existe no léxico? Custo O(m). */
  buscarNoLexico(palavra) {
    const medida = medir(() => ({
      existe: this.trie.buscar(palavra),
      formas: this.trie.formasDe(palavra),
      abaixo: this.trie.contarPrefixo(palavra),
    }));

    const { existe, formas, abaixo } = medida.resultado;

    // Quando a palavra não existe, as parecidas vêm da mesma Trie, pela busca
    // aproximada -- cronometrada à parte, porque não é o custo da busca exata.
    const aproximacao = medir(
      () => (existe ? [] : this.trie.buscarAproximado(palavra).filter((trio) => trio[1] > 0)),
      { alvoMs: 0 });

    return {
      palavra,
      existe,
      formas,
      continuacoes: Math.max(0, abaixo - (existe ? 1 : 0)),
      aproximadas: aproximacao.resultado,
      tempo: medida.tempo,
      repeticoes: medida.repeticoes,
      tempo_aproximacao: aproximacao.tempo,
    };
  }

  /**
   * Parte I, seção 2.4: insere uma palavra em tempo de execução.
   *
   * Vale só para esta sessão da página; `palavras.txt` não é reescrito. Quem
   * quiser gravar um léxico novo roda `python gerar_lexico.py`.
   *
   * Diferente das consultas, a inserção MUDA a estrutura -- repeti-la para
   * medir inseriria a mesma palavra várias vezes. Por isso aqui o cronômetro
   * é o simples, de uma execução só.
   */
  inserirNoLexico(palavra) {
    const relogio = Cronometro.iniciar();
    const nova = this.trie.inserir(palavra);
    const tempo = relogio.parar();

    return {
      palavra: String(palavra).trim(),
      nova,
      palavras: this.trie.tamanho,
      nos: this.trie.totalNos(),
      tempo,
      repeticoes: 1,
    };
  }

  /* --------------------------------------------------------- estatísticas */

  /**
   * As mesmas sete métricas obrigatórias da seção 3.9 que o terminal imprime
   * e que a rota `/api/estatisticas` devolve, no mesmo formato.
   */
  resumirEstatisticas() {
    const mecanismo = this.mecanismo;
    const e = mecanismo.estatisticas;
    const formatar = formatarDuracao;

    return {
      corpus: {
        documentos: e.documentos,
        palavras: e.totalPalavras,
        palavras_brutas: e.totalPalavrasBrutas,
        reducao_stopwords: e.taxaReducaoStopwords(),
        termos: e.termosDistintos,
        palavras_na_trie: e.palavrasNaTrie,
        radicais: mecanismo.indice.totalTermos(),
        postagens: e.postagens,
      },
      memoria: {
        nos_trie: e.nosNaTrie,
        nos_trie_comprimida: e.nosNaTrieComprimida,
        economia: e.economiaTrieComprimida(),
      },
      construcao: {
        leitura: formatar(e.tempoLeitura),
        preprocessamento: formatar(e.tempoPreprocessamento),
        trie: formatar(e.tempoTrie),
        indice: formatar(e.tempoIndice),
        total: formatar(e.tempoTotalConstrucao()),
      },
      preprocessamento: Object.fromEntries(
        Object.entries(mecanismo.preprocessador.descrever())
          .map(([chave, valor]) => [chave, String(valor)])),
      consultas: {
        total: e.consultas.length,
        por_tipo: Object.fromEntries(e.resumoPorTipo().map(
          ({ tipo, quantidade, total, media }) => [tipo, {
            quantidade, total: formatar(total), media: formatar(media),
          }])),
        ultimas: e.consultas.slice(-8).map(
          ({ tipo, texto, resultados, segundos }) => ({
            tipo, texto, resultados, tempo: formatar(segundos),
          })),
      },
      hash: mecanismo.indice.espelharEmTabelaHash().estatisticas(),
    };
  }
}

export { MecanismoBusca, Aplicacao };
