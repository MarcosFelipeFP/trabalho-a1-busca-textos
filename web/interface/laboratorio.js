/* ===========================================================================
   laboratorio.js
   Os sete experimentos de `benchmark.py`, rodando no navegador.

   ---------------------------------------------------------------------------
   O que muda em relação ao terminal
   ---------------------------------------------------------------------------
   Nada no método: as mesmas comparações, os mesmos tamanhos, a mesma leitura.
   Muda o relógio -- o navegador arredonda `performance.now`, então todo tempo
   medido aqui é média de repetições, e a contagem aparece junto do número.

   Onde é possível, o experimento reporta uma CONTAGEM em vez de um tempo:
   comparações de caractere, nós alocados, colisões. Contagem não depende de
   relógio, de máquina nem de quem está olhando -- é o mesmo número em qualquer
   lugar, e é o que sustenta a análise assintótica.
   =========================================================================== */

'use strict';

window.UI = window.UI || {};

(function (UI) {

  const { numero, escapar, plural, porcentagem, respirar } = UI;
  const tempo = (segundos) => window.A1.formatarDuracao(segundos);

  /**
   * Cede a vez ao navegador, mas só quando faz diferença.
   *
   * Ceder a cada passo do experimento custaria um temporizador por rodada --
   * e em aba oculta o navegador limita temporizadores a um por segundo, o que
   * transformaria um experimento de dois segundos em um de trinta. Cede-se por
   * tempo decorrido: a barra continua andando, sem que a espera vire o
   * experimento.
   */
  let ultimoRespiro = performance.now();
  async function ceder() {
    if (performance.now() - ultimoRespiro < 50) return;
    await respirar();
    ultimoRespiro = performance.now();
  }

  /**
   * Menor leitura de um conjunto de medições.
   *
   * `benchmark.py` usa a mediana, e faz bem: no terminal a distribuição é
   * razoavelmente simétrica. No navegador não é. Todo ruído aqui SOMA tempo --
   * outra aba pedindo a CPU, o coletor de lixo, o compositor desenhando a tela
   * -- e nada jamais faz o algoritmo rodar mais rápido do que ele é. Numa
   * distribuição com cauda só de um lado, a menor leitura é a mais próxima do
   * custo real; a mediana carrega metade do ruído junto.
   */
  function menorLeitura(valores) {
    return Math.min(...valores);
  }

  /**
   * Cronometra `funcao` e devolve o custo POR EXECUÇÃO.
   *
   * O relógio do navegador é arredondado -- em geral para 100 µs, às vezes para
   * 1 ms. Uma consulta à Trie custa dois microssegundos: medida uma vez, ela
   * aparece como zero, e a tabela mostraria "0,0 µs" e uma vantagem infinita.
   *
   * Por isso a função se calibra antes: aumenta o número de repetições até a
   * rodada durar mais que `alvoMs`, e só então mede -- o mesmo recurso que o
   * `lotes` de `benchmark.py` usa no terminal. De `vezes` rodadas fica a menor,
   * pelo motivo explicado em `menorLeitura`.
   */
  function cronometrar(funcao, vezes = 7, alvoMs = 12) {
    // Aquecimento. O JavaScript é compilado em tempo de execução: as primeiras
    // chamadas de uma função rodam interpretadas e custam várias vezes mais que
    // as seguintes, quando o compilador já as otimizou. Medir sem aquecer
    // registra o compilador trabalhando, não o algoritmo -- e foi exatamente
    // isso que apareceu aqui: a primeira leitura dava 32 µs onde as seguintes
    // davam 4 µs. As execuções de aquecimento são descartadas.
    const fimDoAquecimento = performance.now() + 3;
    let aquecidas = 0;
    while (aquecidas < 400 && performance.now() < fimDoAquecimento) {
      funcao();
      aquecidas += 1;
    }

    let repeticoes = 1;
    for (;;) {
      const inicio = performance.now();
      for (let i = 0; i < repeticoes; i += 1) funcao();
      const gasto = performance.now() - inicio;
      if (gasto >= alvoMs || repeticoes >= 1e6) break;
      // `gasto` pode voltar zero; o piso de 0,05 ms evita divisão por zero e
      // limita o salto a vinte vezes por tentativa.
      repeticoes = Math.ceil(repeticoes * alvoMs / Math.max(gasto, 0.05));
    }

    const leituras = [];
    for (let volta = 0; volta < vezes; volta += 1) {
      const inicio = performance.now();
      for (let i = 0; i < repeticoes; i += 1) funcao();
      leituras.push((performance.now() - inicio) / 1000 / repeticoes);
    }
    return menorLeitura(leituras);
  }

  /** Razão entre dois custos, protegida contra a divisão por zero. */
  const razao = (maior, menor) => (menor > 0 ? maior / menor : 0);

  function quadro(linhas) {
    return `<dl class="quadro">${linhas.map(([rotulo, valor]) =>
      `<div><dt>${escapar(rotulo)}</dt><dd>${escapar(valor)}</dd></div>`).join('')}</dl>`;
  }

  function tabela(cabecalho, linhas) {
    return `<div class="rolagem"><table class="tabela">
      <thead><tr>${cabecalho.map((c, i) =>
        `<th${i ? ' class="num"' : ''}>${escapar(c)}</th>`).join('')}</tr></thead>
      <tbody>${linhas.map((linha) => `<tr>${linha.map((celula, i) =>
        `<td${i ? ' class="num"' : ''}>${celula}</td>`).join('')}</tr>`).join('')}</tbody>
    </table></div>`;
  }

  /* =========================================================================
     1 - BUSCA POR PREFIXO: TRIE CONTRA VARREDURA SEQUENCIAL
     ========================================================================= */

  async function trieContraVarredura({ lexico }) {
    // Amostras espaçadas, não os primeiros N do léxico: o arquivo está em ordem
    // alfabética, e uma fatia inicial só teria palavras com "a" e "b" -- os
    // prefixos testados não encontrariam nada e a medição diria que a Trie é
    // instantânea porque não fez trabalho nenhum. Pegar uma palavra a cada k
    // mantém o alfabeto inteiro representado em todos os tamanhos.
    const saltos = [8, 4, 2, 1];
    // Prefixos curtos e comuns, escolhidos para devolverem as dez palavras do
    // limite mesmo na menor amostra: com o número de resultados fixo em todas as
    // linhas, o que resta variando é só o tamanho do léxico.
    const prefixos = ['ap', 'com', 'con', 'des', 'est', 'pre', 'pro', 'tra'];

    const serieTrie = [];
    const serieVarredura = [];
    const linhas = [];

    for (const salto of saltos) {
      const amostra = lexico.filter((_palavra, indice) => indice % salto === 0);
      const trie = new window.A1.Trie(amostra);
      // A varredura sequencial precisa das mesmas chaves normalizadas, senão
      // estaria resolvendo um problema mais fácil que o da Trie.
      const chaves = amostra.map((palavra) => window.A1.normalizar(palavra));

      const devolvidos = prefixos.reduce(
        (soma, prefixo) => soma + trie.buscarPrefixo(prefixo, 10).length, 0);

      const custoTrie = cronometrar(() => {
        for (const prefixo of prefixos) trie.buscarPrefixo(prefixo, 10);
      }) / prefixos.length;

      const custoVarredura = cronometrar(() => {
        for (const prefixo of prefixos) {
          const chave = window.A1.normalizar(prefixo);
          const achadas = [];
          for (const candidata of chaves) {
            if (candidata.startsWith(chave)) {
              achadas.push(candidata);
              if (achadas.length >= 10) break;
            }
          }
        }
      }) / prefixos.length;

      serieTrie.push([amostra.length, custoTrie * 1e6]);
      serieVarredura.push([amostra.length, custoVarredura * 1e6]);
      linhas.push([
        numero(amostra.length),
        numero(devolvidos),
        escapar(tempo(custoTrie)),
        escapar(tempo(custoVarredura)),
        `${razao(custoVarredura, custoTrie).toFixed(1)}×`,
      ]);
      await ceder();
    }

    const ganhoFinal = razao(serieVarredura[serieVarredura.length - 1][1],
                             serieTrie[serieTrie.length - 1][1]);

    return UI.graficoLinhas({
      series: [
        { nome: 'Trie · O(m + k)', pontos: serieTrie },
        { nome: 'varredura sequencial · O(V · m)', pontos: serieVarredura },
      ],
      rotuloX: 'palavras no léxico',
      rotuloY: 'µs por consulta',
      formatarY: (v) => `${v.toFixed(1)}`,
    }) +
    tabela(['léxico', 'resultados', 'Trie', 'varredura', 'vantagem'], linhas) +
    `<p class="conclusao">A coluna <b>resultados</b> é o controle do experimento:
      o limite de dez palavras por prefixo mantém o <b>p</b> do O(m + p) parado, de
      modo que a única coisa que muda de uma linha para a outra é o tamanho do
      léxico. É exatamente o que a Trie ignora — ela desce o prefixo e coleta o que
      pediram, sem olhar o resto da coleção. A varredura não tem esse luxo: precisa
      testar palavra por palavra até juntar dez, e dobra de custo cada vez que o
      léxico dobra. No maior léxico testado, a diferença é de
      <b>${ganhoFinal.toFixed(0)}×</b>.</p>`;
  }

  /* =========================================================================
     2 - TRIE TRADICIONAL CONTRA TRIE COMPRIMIDA (PATRICIA)
     ========================================================================= */

  async function trieContraPatricia({ aplicacao }) {
    const vocabulario = Array.from(aplicacao.mecanismo.vocabulario)
      .sort(window.A1.ordemDeTexto);

    const inicioTrie = performance.now();
    const trie = new window.A1.Trie(vocabulario);
    const construcaoTrie = (performance.now() - inicioTrie) / 1000;
    await ceder();

    const inicioPatricia = performance.now();
    const patricia = new window.A1.TrieComprimida(vocabulario);
    const construcaoPatricia = (performance.now() - inicioPatricia) / 1000;
    await ceder();

    const prefixos = ['com', 'pro', 'est', 'dad', 'alg'];
    const custoTrie = cronometrar(() => {
      for (const p of prefixos) trie.buscarPrefixo(p, 20);
    }) / prefixos.length;
    const custoPatricia = cronometrar(() => {
      for (const p of prefixos) patricia.buscarPrefixo(p, 20);
    }) / prefixos.length;

    const economia = 1 - patricia.totalNos() / trie.totalNos();

    return UI.graficoBarras({
      itens: [
        { nome: 'Trie tradicional', valor: trie.totalNos(), cor: 'a' },
        { nome: 'Trie comprimida', valor: patricia.totalNos(), cor: 'b' },
      ],
      formatar: (v) => `${numero(Math.round(v))} nós`,
    }) +
    `<div class="grade">
      ${quadro([
        ['Palavras armazenadas', numero(trie.tamanho)],
        ['Nós · Trie', numero(trie.totalNos())],
        ['Nós · comprimida', numero(patricia.totalNos())],
        ['Economia de nós', porcentagem(economia)],
      ])}
      ${quadro([
        ['Construção · Trie', tempo(construcaoTrie)],
        ['Construção · comprimida', tempo(construcaoPatricia)],
        ['Consulta · Trie', tempo(custoTrie)],
        ['Consulta · comprimida', tempo(custoPatricia)],
      ])}
    </div>
    <p class="conclusao">As duas reconhecem exatamente as mesmas palavras e têm a
      mesma complexidade assintótica, <b>O(m)</b> para inserir e buscar. A
      comprimida colapsa cadeias sem bifurcação em uma aresta só e economiza
      <b>${porcentagem(economia)}</b> dos nós — o preço é uma comparação de
      substring a cada aresta, em vez de uma comparação de caractere.</p>`;
  }

  /* =========================================================================
     3 - KMP CONTRA FORÇA BRUTA
     ========================================================================= */

  async function kmpContraIngenuo({ aplicacao }) {
    // --- (a) pior caso construído ---
    const tamanhos = [500, 1000, 2000, 4000, 8000];
    const serieKmp = [];
    const serieIngenuo = [];
    const linhas = [];

    for (const n of tamanhos) {
      const texto = 'a'.repeat(n);
      const padrao = 'a'.repeat(19) + 'b';
      const comKmp = window.A1.buscarKmp(texto, padrao);
      const comIngenuo = window.A1.buscarIngenuo(texto, padrao);

      serieKmp.push([n, comKmp.comparacoes]);
      serieIngenuo.push([n, comIngenuo.comparacoes]);
      linhas.push([
        numero(n),
        numero(comKmp.comparacoes),
        numero(comIngenuo.comparacoes),
        `${(comIngenuo.comparacoes / comKmp.comparacoes).toFixed(1)}×`,
      ]);
      await ceder();
    }

    // --- (b) texto natural: o corpus real ---
    const padroes = ['chave pública', 'algoritmo de busca', 'estrutura de dados'];
    const naturais = [];
    for (const padrao of padroes) {
      let comparacoesKmp = 0;
      let comparacoesIngenuo = 0;
      let ocorrencias = 0;

      const inicioKmp = performance.now();
      for (const texto of aplicacao.mecanismo.conteudo.values()) {
        const achado = window.A1.buscarKmp(texto.toLowerCase(), padrao);
        comparacoesKmp += achado.comparacoes;
        ocorrencias += achado.ocorrencias.length;
      }
      const custoKmp = (performance.now() - inicioKmp) / 1000;

      const inicioIngenuo = performance.now();
      for (const texto of aplicacao.mecanismo.conteudo.values()) {
        comparacoesIngenuo += window.A1.buscarIngenuo(texto.toLowerCase(), padrao).comparacoes;
      }
      const custoIngenuo = (performance.now() - inicioIngenuo) / 1000;

      naturais.push([
        escapar(padrao),
        numero(ocorrencias),
        numero(comparacoesKmp),
        numero(comparacoesIngenuo),
        escapar(tempo(custoKmp)),
        escapar(tempo(custoIngenuo)),
      ]);
      await ceder();
    }

    const piorRazao = razao(serieIngenuo[serieIngenuo.length - 1][1],
                            serieKmp[serieKmp.length - 1][1]);

    return UI.graficoLinhas({
      series: [
        { nome: 'KMP · O(n + m)', pontos: serieKmp },
        { nome: 'força bruta · O(n · m)', pontos: serieIngenuo },
      ],
      rotuloX: 'caracteres do texto',
      rotuloY: 'comparações',
    }) +
    `<p class="subtitulo">Pior caso construído — texto "aaa…a", padrão "aaa…ab"</p>` +
    tabela(['texto', 'KMP', 'força bruta', 'razão'], linhas) +
    `<p class="subtitulo">Texto natural — os 24 documentos do corpus</p>` +
    tabela(['padrão', 'ocorrências', 'comparações KMP', 'comparações força bruta',
            'tempo KMP', 'tempo força bruta'], naturais) +
    `<p class="conclusao">No pior caso a distância é a que a teoria prevê:
      <b>${piorRazao.toFixed(1)}×</b> menos comparações no maior texto testado, e a
      curva da força bruta sobe com o produto n·m enquanto a do KMP sobe com n.
      Em texto natural a vantagem quase desaparece — falhas acontecem cedo, e o
      caso ruim raramente aparece. O KMP não é mais rápido em média;
      <b>é mais rápido quando o texto é adversário</b>, e nunca pior.</p>`;
  }

  /* =========================================================================
     4 - TABELA HASH: FATOR DE CARGA E COLISÕES
     ========================================================================= */

  async function hashFatorDeCarga({ aplicacao }) {
    const termos = Array.from(aplicacao.mecanismo.indice.porRadical.keys());
    const capacidades = [512, 1024, 2048, 4096, 8192, 16384];
    const serieCadeia = [];
    const serieColisoes = [];
    const linhas = [];

    for (const capacidade of capacidades) {
      // `CARGA_MAXIMA` faria a tabela crescer sozinha e apagar o efeito que se
      // quer medir; aqui a capacidade é fixada de propósito para observar a
      // degradação.
      const tabelaFixa = new window.A1.TabelaHash(capacidade);
      tabelaFixa._redimensionar = () => {};
      for (const termo of termos) tabelaFixa.inserir(termo, 1);

      const e = tabelaFixa.estatisticas();
      serieCadeia.push([e['fator de carga'], e['cadeia media']]);
      serieColisoes.push([e['fator de carga'], e['maior cadeia']]);
      linhas.push([
        numero(capacidade),
        e['fator de carga'].toFixed(2),
        numero(e['baldes ocupados']),
        numero(e.colisoes),
        e['cadeia media'].toFixed(2),
        numero(e['maior cadeia']),
      ]);
      await ceder();
    }

    return UI.graficoLinhas({
      series: [
        { nome: 'cadeia média', pontos: serieCadeia },
        { nome: 'maior cadeia', pontos: serieColisoes },
      ],
      rotuloX: 'fator de carga α',
      rotuloY: 'comprimento',
      formatarY: (v) => v.toFixed(1),
    }) +
    tabela(['capacidade', 'α', 'baldes ocupados', 'colisões', 'cadeia média', 'maior cadeia'],
           linhas) +
    `<p class="conclusao">A cadeia média acompanha α quase exatamente — é o
      <b>O(1 + α)</b> da teoria aparecendo na medida. A maior cadeia cresce mais
      devagar que α, sinal de que a hash polinomial espalha bem: as chaves não se
      concentram. Manter α abaixo de <b>0,75</b>, que é o que a tabela faz ao
      dobrar de tamanho sozinha, é o que mantém a busca em tempo constante na
      prática.</p>`;
  }

  /* =========================================================================
     5 - ESCALABILIDADE DA INDEXAÇÃO
     ========================================================================= */

  async function escalabilidade({ aplicacao }) {
    const mecanismo = aplicacao.mecanismo;
    const nomes = Array.from(mecanismo.conteudo.keys()).sort(window.A1.ordemDeTexto);

    // Tokeniza uma vez; o experimento mede a CONSTRUÇÃO DO ÍNDICE sobre um
    // número crescente de tokens, sem repetir o pré-processamento a cada
    // rodada -- misturar as duas fases esconderia qual delas cresce.
    const tokensPorDocumento = new Map();
    for (const nome of nomes) {
      tokensPorDocumento.set(nome, mecanismo.preprocessador.processar(mecanismo.conteudo.get(nome)));
      await ceder();
    }

    const cortes = [2, 5, 9, 14, 19, nomes.length].filter((n) => n <= nomes.length);
    const serieTempo = [];
    const linhas = [];

    for (const corte of cortes) {
      const subconjunto = nomes.slice(0, corte);
      const tokens = subconjunto.reduce((soma, nome) =>
        soma + tokensPorDocumento.get(nome).length, 0);

      const custo = cronometrar(() => {
        const indice = new window.A1.IndiceInvertido();
        for (const nome of subconjunto) {
          indice.indexar(nome, tokensPorDocumento.get(nome), mecanismo.preprocessador);
        }
      }, 3, 0);

      const indice = new window.A1.IndiceInvertido();
      for (const nome of subconjunto) {
        indice.indexar(nome, tokensPorDocumento.get(nome), mecanismo.preprocessador);
      }

      serieTempo.push([tokens, custo * 1000]);
      linhas.push([
        numero(corte),
        numero(tokens),
        numero(indice.totalTermos()),
        numero(indice.totalPostagens()),
        escapar(tempo(custo)),
        escapar(tempo(custo / tokens)),
      ]);
      await ceder();
    }

    const primeiro = serieTempo[0];
    const ultimo = serieTempo[serieTempo.length - 1];
    const razaoTokens = razao(ultimo[0], primeiro[0]);
    const razaoTempo = razao(ultimo[1], primeiro[1]);

    return UI.graficoLinhas({
      series: [{ nome: 'construção do índice', pontos: serieTempo }],
      rotuloX: 'tokens indexados',
      rotuloY: 'ms',
      formatarY: (v) => v.toFixed(1),
    }) +
    tabela(['documentos', 'tokens', 'radicais', 'postagens', 'tempo', 'por token'], linhas) +
    `<p class="conclusao">O tempo cresce com o número de tokens, não com o número
      de documentos: <b>${razaoTokens.toFixed(1)}×</b> mais tokens custaram
      <b>${razaoTempo.toFixed(1)}×</b> mais tempo. O custo por token permanece na
      mesma ordem de grandeza em toda a faixa, que é o que caracteriza o
      <b>O(N)</b> da indexação — e o que garante que dobrar o corpus não dobre o
      tempo de RESPOSTA, só o de construção.</p>`;
  }

  /* =========================================================================
     6 - RANQUEAMENTO: BM25 CONTRA TF-IDF
     ========================================================================= */

  async function bm25ContraTfidf({ aplicacao }) {
    const mecanismo = aplicacao.mecanismo;
    const consultas = ['algoritmo', 'dados', 'rede'];
    const blocos = [];

    for (const consulta of consultas) {
      const radical = mecanismo.preprocessador.radicalizar(consulta);
      const bm25 = mecanismo.indice.ranquearBm25([radical]).slice(0, 6);
      const tfidf = mecanismo.indice.ranquearTfidf([radical]).slice(0, 6);
      const frequencias = mecanismo.indice.buscar(radical);

      const linhas = bm25.map(([documento, nota], posicao) => {
        const posicaoTfidf = tfidf.findIndex(([outro]) => outro === documento);
        const tamanho = mecanismo.indice.tamanhoDocumento.get(documento);
        return [
          escapar(documento),
          numero(frequencias[documento] || 0),
          numero(tamanho),
          nota.toFixed(3),
          posicaoTfidf < 0 ? '—' : `${posicaoTfidf + 1}º`,
          posicaoTfidf === posicao ? '=' :
            `<span style="color:var(--ciano)">${posicaoTfidf > posicao ? '↑' : '↓'}</span>`,
        ];
      });

      blocos.push(`<p class="subtitulo">"${escapar(consulta)}" — radical
        <b style="color:var(--ambar)">${escapar(radical)}</b></p>` +
        tabela(['documento', 'ocorrências', 'tokens do doc', 'BM25',
                'posição no TF-IDF', ''], linhas));
      await ceder();
    }

    return blocos.join('') +
      `<p class="conclusao">As duas funções concordam sobre QUAIS documentos são
        relevantes e discordam sobre a ordem. A diferença vem dos dois ajustes do
        BM25: a <b>saturação</b> impede que a vigésima ocorrência valha o mesmo que
        a segunda, e a <b>normalização por tamanho</b> desconta o documento que só
        acumulou ocorrências por ser longo. Onde aparece uma seta, é um desses dois
        efeitos agindo.</p>`;
  }

  /* =========================================================================
     7 - EFEITO DO STEMMING RSLP
     ========================================================================= */

  async function efeitoDoStemming({ aplicacao }) {
    const mecanismo = aplicacao.mecanismo;
    const vocabulario = Array.from(mecanismo.vocabulario);
    const radicais = new Set(vocabulario.map((p) => mecanismo.preprocessador.radicalizar(p)));
    const compressao = 1 - radicais.size / vocabulario.size;

    await ceder();

    const consultas = ['algoritmo', 'dado', 'computação', 'rede', 'programação',
                       'segurança', 'aprendizado'];
    const linhas = [];
    let ganhoTotal = 0;

    for (const consulta of consultas) {
      const radical = mecanismo.preprocessador.radicalizar(consulta);
      const comStemming = Object.keys(mecanismo.indice.buscar(radical, true)).length;
      const semStemming = Object.keys(
        mecanismo.indice.buscar(consulta.toLowerCase(), false)).length;
      ganhoTotal += comStemming - semStemming;

      linhas.push([
        escapar(consulta),
        escapar(radical),
        numero(semStemming),
        numero(comStemming),
        comStemming > semStemming
          ? `<span style="color:var(--ambar)">+${comStemming - semStemming}</span>`
          : '—',
      ]);
    }

    return UI.graficoBarras({
      itens: [
        { nome: 'formas distintas', valor: vocabulario.size, cor: 'b' },
        { nome: 'radicais RSLP', valor: radicais.size, cor: 'a' },
      ],
      formatar: (v) => numero(Math.round(v)),
    }) +
    tabela(['consulta', 'radical', 'forma exata', 'com RSLP', 'ganho'], linhas) +
    `<p class="conclusao">O RSLP reduz o vocabulário em <b>${porcentagem(compressao)}</b>
      e, somadas as sete consultas, alcança <b>${numero(ganhoTotal)}</b>
      ${plural(ganhoTotal, 'documento', 'documentos')} a mais do que a forma exata
      encontraria. É o que o exemplo da seção 3.7.1 do enunciado exige: quem digita
      "algoritmo" no singular precisa encontrar os arquivos que escrevem
      "algoritmos". O preço é o radical não ser uma palavra do português — mas o
      índice não precisa que seja, precisa que seja o MESMO para as duas formas.</p>`;
  }

  /* =========================================================================
     REGISTRO E EXECUÇÃO
     ========================================================================= */

  const EXPERIMENTOS = [
    {
      id: 'trie-varredura',
      titulo: 'Busca por prefixo: Trie contra varredura sequencial',
      resumo: 'O mesmo léxico, as mesmas consultas, duas estruturas. A pergunta é o que acontece com o tempo quando o vocabulário cresce.',
      rodar: trieContraVarredura,
    },
    {
      id: 'patricia',
      titulo: 'Trie tradicional contra Trie comprimida (PATRICIA)',
      resumo: 'Mesma linguagem reconhecida, mesma complexidade, memórias diferentes — a questão conceitual 6 do enunciado, medida.',
      rodar: trieContraPatricia,
    },
    {
      id: 'kmp',
      titulo: 'Casamento de cadeias: KMP contra força bruta',
      resumo: 'Comparações de caractere no pior caso construído e no corpus real. Contagem, não relógio: o número é o mesmo em qualquer máquina.',
      rodar: kmpContraIngenuo,
    },
    {
      id: 'hash',
      titulo: 'Tabela hash: fator de carga e colisões',
      resumo: 'Os radicais do índice inseridos em capacidades crescentes, para ver o O(1 + α) se comportar.',
      rodar: hashFatorDeCarga,
    },
    {
      id: 'escalabilidade',
      titulo: 'Escalabilidade da indexação',
      resumo: 'Quanto custa construir o índice conforme o corpus cresce — a conta que se paga uma vez para não pagar nunca mais.',
      rodar: escalabilidade,
    },
    {
      id: 'ranqueamento',
      titulo: 'Ranqueamento: BM25 contra TF-IDF',
      resumo: 'Os mesmos documentos, duas ordens. Onde elas divergem é onde a saturação e a normalização por tamanho agem.',
      rodar: bm25ContraTfidf,
    },
    {
      id: 'stemming',
      titulo: 'Efeito do stemming RSLP',
      resumo: 'O que o stemmer compacta no vocabulário e o que ele acrescenta na cobertura das consultas.',
      rodar: efeitoDoStemming,
    },
  ];

  /** Desenha os cartões, cada um com seu botão. */
  function montarLaboratorio(elemento) {
    elemento.innerHTML = EXPERIMENTOS.map((experimento, indice) => `
      <article class="experimento" id="exp-${experimento.id}">
        <header class="experimento-cabeca">
          <div>
            <h3>${indice + 1}. ${escapar(experimento.titulo)}</h3>
            <p>${escapar(experimento.resumo)}</p>
          </div>
          <button type="button" class="botao" data-experimento="${experimento.id}">Rodar</button>
        </header>
        <div class="experimento-corpo" data-corpo="${experimento.id}">
          <p class="vazio" style="padding:0">Ainda não rodou.</p>
        </div>
      </article>`).join('');
  }

  /**
   * Roda um experimento e troca o conteúdo do cartão.
   *
   * O `respirar()` dentro de cada experimento é o que mantém a página viva: sem
   * ele, o navegador congelaria até o último cálculo terminar e ninguém veria o
   * progresso.
   */
  async function rodarExperimento(id, contexto) {
    const experimento = EXPERIMENTOS.find((item) => item.id === id);
    const corpo = document.querySelector(`[data-corpo="${id}"]`);
    const botao = document.querySelector(`[data-experimento="${id}"]`);
    if (!experimento || !corpo) return;

    corpo.innerHTML = '<p class="rodando">Rodando…</p>';
    if (botao) { botao.disabled = true; botao.textContent = 'Rodando'; }
    ultimoRespiro = 0;
    await ceder();

    try {
      corpo.innerHTML = await experimento.rodar(contexto);
    } catch (falha) {
      corpo.innerHTML = `<p class="recado falha">O experimento falhou: ${escapar(falha.message)}</p>`;
    } finally {
      if (botao) { botao.disabled = false; botao.textContent = 'Rodar de novo'; }
    }
  }

  async function rodarTodos(contexto) {
    for (const experimento of EXPERIMENTOS) {
      await rodarExperimento(experimento.id, contexto);
    }
  }

  function limpar() {
    for (const experimento of EXPERIMENTOS) {
      const corpo = document.querySelector(`[data-corpo="${experimento.id}"]`);
      if (corpo) corpo.innerHTML = '<p class="vazio" style="padding:0">Ainda não rodou.</p>';
      const botao = document.querySelector(`[data-experimento="${experimento.id}"]`);
      if (botao) botao.textContent = 'Rodar';
    }
  }

  UI.EXPERIMENTOS = EXPERIMENTOS;
  UI.montarLaboratorio = montarLaboratorio;
  UI.rodarExperimento = rodarExperimento;
  UI.rodarTodos = rodarTodos;
  UI.limparLaboratorio = limpar;

})(window.UI);
