/* ===========================================================================
   app.js
   O controlador da bancada: constrói as estruturas, liga os campos às
   consultas e manda desenhar.

   Nenhum algoritmo mora aqui. A Trie, o índice invertido, o RSLP e o KMP estão
   em `web/algoritmos/`, portados de `.py` para `.js` e conferidos caso a caso
   por `verificar_web.py`. Este arquivo decide o que perguntar e onde mostrar a
   resposta.
   =========================================================================== */

'use strict';

(function (UI, A1) {

  const { $, escapar, numero, plural, porcentagem, micro, realcar, esperar, respirar } = UI;
  const $$ = (seletor, raiz = document) => Array.from(raiz.querySelectorAll(seletor));

  const ESPERA_DIGITACAO = 120;
  const LIMITE_PARTE1 = 40;
  const LIMITE_PARTE2 = 30;

  const estado = {
    aplicacao: null,     // motor local, sempre construído
    motor: null,         // quem responde: local ou servidor
    motorLocal: null,
    motorServidor: null,
    modo: 'palavra',
    sequencia: { parte1: 0, parte2: 0 },
    fita: null,
    painelVisitado: { parte1: true },
  };

  /* =========================================================================
     PARTIDA
     ========================================================================= */

  const FASES = {
    leitura: ['leitura', 'preprocessamento'],
    trie: ['trie'],
    'trie-comprimida': ['trie'],
    indice: ['indice'],
  };

  function marcarFase(nome, situacao, texto) {
    const item = $(`.fases li[data-fase="${nome}"]`);
    if (!item) return;
    item.dataset.estado = situacao;
    if (texto) $('.fase-tempo', item).textContent = texto;
  }

  /**
   * Constrói as estruturas mostrando o andamento.
   *
   * A construção é o próprio assunto: um mecanismo de busca paga um custo alto
   * uma vez, na indexação, para que cada consulta depois custe quase nada.
   * Esconder isso atrás de um passo-a-passo genérico jogaria fora a melhor
   * explicação que a página tem para dar.
   */
  async function construir() {
    const partida = $('#partida');
    const progresso = $('#partida-progresso');
    const recado = $('#partida-nota');

    await respirar();

    const aplicacao = new A1.Aplicacao({
      documentos: window.DADOS.corpus,
      lexico: window.DADOS.lexico,
      stopwords: window.DADOS.stopwords,
      usarStemming: true,
    });
    estado.aplicacao = aplicacao;

    const etapas = aplicacao.construirEmEtapas();
    const total = window.DADOS.corpus.length;
    let fasesAnteriores = [];

    // Ceder a vez ao navegador a cada documento faria a construção esperar 24
    // quadros sem necessidade. Cede-se por tempo: só quando já se passaram uns
    // 40 ms desde a última pausa, que é o bastante para a barra andar na tela
    // sem transformar a espera em espetáculo.
    let ultimoRespiro = performance.now();

    for (;;) {
      const passo = etapas.next();
      if (passo.done) break;
      const { fase, nome, posicao } = passo.value;

      // Quando a fase muda, a anterior ganha o tempo que o cronômetro mediu.
      const atuais = FASES[fase] || [];
      for (const anterior of fasesAnteriores) {
        if (!atuais.includes(anterior)) {
          marcarFase(anterior, 'feito', tempoDaFase(aplicacao, anterior));
        }
      }
      for (const nomeFase of atuais) marcarFase(nomeFase, 'fazendo');
      fasesAnteriores = atuais;

      if (fase === 'leitura') {
        progresso.style.width = `${(posicao / total) * 72}%`;
        recado.textContent = `${posicao}/${total} · ${nome}`;
      } else if (fase === 'trie') {
        progresso.style.width = '80%';
        recado.textContent = `inserindo ${numero(passo.value.total)} palavras na Trie`;
      } else if (fase === 'trie-comprimida') {
        progresso.style.width = '88%';
        recado.textContent = 'montando a Trie comprimida, para comparar a memória';
      } else if (fase === 'indice') {
        progresso.style.width = '94%';
        recado.textContent = 'construindo o índice invertido';
      }

      if (performance.now() - ultimoRespiro > 40) {
        await respirar();
        ultimoRespiro = performance.now();
      }
    }

    for (const nomeFase of ['leitura', 'preprocessamento', 'trie', 'indice']) {
      marcarFase(nomeFase, 'feito', tempoDaFase(aplicacao, nomeFase));
    }
    progresso.style.width = '100%';

    const construcao = aplicacao.estado().parte2.tempo_construcao;
    recado.textContent = `pronto em ${A1.formatarDuracao(construcao)}`;

    estado.motorLocal = new UI.MotorLocal(aplicacao);
    estado.motor = estado.motorLocal;

    await new Promise((seguir) => setTimeout(seguir, 320));
    partida.hidden = true;
    $('#barra').hidden = false;
    $('#fita').hidden = false;
    $('#console').hidden = false;
    $('#regua').hidden = false;
  }

  function tempoDaFase(aplicacao, fase) {
    const e = aplicacao.mecanismo.estatisticas;
    const mapa = {
      leitura: e.tempoLeitura,
      preprocessamento: e.tempoPreprocessamento,
      trie: e.tempoTrie,
      indice: e.tempoIndice,
    };

    // No navegador o corpus chega embutido no próprio pacote de scripts: não há
    // arquivo a abrir, e medir a "leitura" daria zero. Dizer "em memória" é mais
    // honesto do que exibir um zero que pareceria um erro de medição.
    if (fase === 'leitura' && mapa.leitura < 1e-5) return 'em memória';
    return A1.formatarDuracao(mapa[fase] || 0);
  }

  /* =========================================================================
     MOTOR
     ========================================================================= */

  async function prepararMotor() {
    const botao = $('#trocar-motor');
    const disponivel = await UI.servidorDisponivel();

    if (disponivel) {
      estado.motorServidor = new UI.MotorServidor();
      estado.motor = estado.motorServidor;
      botao.addEventListener('click', trocarMotor);
      botao.title = 'Alterna entre o Python do servidor e o JavaScript do navegador';
    } else {
      botao.dataset.indisponivel = 'sim';
      botao.title = 'A página está rodando sem servidor: os algoritmos executam ' +
        'aqui, no navegador.';
    }

    mostrarMotor();
  }

  function mostrarMotor() {
    $('#motor-atual').textContent = estado.motor.nome;
    $('#ajuda-motor').innerHTML = estado.motor === estado.motorServidor
      ? `As consultas estão indo para o <b>Python</b>, pelas rotas de
         <code>servidor.py</code>. O botão do topo alterna para o JavaScript do
         navegador — as duas implementações respondem o mesmo, e
         <code>verificar_web.py</code> confere isso caso a caso.`
      : `Os algoritmos estão rodando em <b>JavaScript</b>, aqui no navegador:
         nenhum servidor, nenhuma rede. É o modo que funciona a partir de um
         pendrive. Para ver o Python respondendo, rode <code>python servidor.py</code>
         e abra <code>http://localhost:8000</code>.`;
  }

  function trocarMotor() {
    if (!estado.motorServidor) return;
    estado.motor = estado.motor === estado.motorServidor
      ? estado.motorLocal
      : estado.motorServidor;
    mostrarMotor();
    carregarEstado();
    if ($('#entrada-parte1').value.trim()) consultarPrefixo();
    if ($('#entrada-parte2').value.trim()) consultarDocumentos();
  }

  /* =========================================================================
     CABEÇALHO
     ========================================================================= */

  async function carregarEstado() {
    try {
      const dados = await estado.motor.estado();
      const campos = {
        documentos: dados.parte2.documentos,
        palavras: dados.parte2.palavras,
        termos: dados.parte2.termos,
        radicais: dados.parte2.radicais,
        postagens: dados.parte2.postagens,
        lexico: dados.parte1.palavras,
      };
      for (const [campo, valor] of Object.entries(campos)) {
        const alvo = $(`[data-campo="${campo}"]`);
        if (alvo) alvo.textContent = numero(valor);
      }
    } catch (falha) {
      recadoDe('parte1', mensagemDeFalha(falha), true);
    }
  }

  function recadoDe(parte, mensagem, falhou = false) {
    const alvo = $(`#recado-${parte}`);
    if (!alvo) return;
    alvo.innerHTML = mensagem || '';
    alvo.classList.toggle('falha', falhou);
  }

  function mensagemDeFalha(falha) {
    if (falha instanceof TypeError) {
      return 'O servidor não respondeu. Confira se <code>python servidor.py</code> ' +
        'ainda está rodando, ou volte para o motor JavaScript.';
    }
    return escapar(falha.message || 'Não foi possível completar a consulta.');
  }

  /* =========================================================================
     PARTE I -- AUTOCOMPLETE
     ========================================================================= */

  async function consultarPrefixo() {
    const prefixo = $('#entrada-parte1').value.trim();
    const saida = $('#saida-parte1');
    const meu = ++estado.sequencia.parte1;

    if (!prefixo) {
      saida.innerHTML = '<p class="vazio">Digite um prefixo para ver a Trie responder.</p>';
      $('#contagem-parte1').textContent = '';
      desenharArvore('');
      recadoDe('parte1', '');
      return;
    }

    try {
      const dados = await estado.motor.autocompletar(prefixo, LIMITE_PARTE1);
      if (meu !== estado.sequencia.parte1) return;   // chegou consulta mais nova

      UI.Regua.marcar({
        segundos: dados.tempo,
        rotulo: `Trie · prefixo "${prefixo}"`,
        via: 'trie',
        repeticoes: dados.repeticoes || 1,
      });

      desenharArvore(prefixo);

      if (!dados.palavras.length) {
        $('#contagem-parte1').textContent = '0 palavras';
        saida.innerHTML = `<p class="vazio">Nenhuma palavra do léxico começa com
          <b>${escapar(prefixo)}</b>. Use <b>Inserir no léxico</b> para acrescentá-la.</p>`;
        return;
      }

      $('#contagem-parte1').textContent = dados.truncado
        ? `${numero(dados.palavras.length)} de ${numero(dados.total)} · ${A1.formatarDuracao(dados.tempo)}`
        : `${numero(dados.total)} ${plural(dados.total, 'palavra', 'palavras')} · ${A1.formatarDuracao(dados.tempo)}`;

      saida.innerHTML = UI.feixe(dados.palavras, prefixo.length);
    } catch (falha) {
      if (meu === estado.sequencia.parte1) recadoDe('parte1', mensagemDeFalha(falha), true);
    }
  }

  function desenharArvore(prefixo) {
    const caixa = $('#arvore-parte1');
    if (!$('#mostrar-arvore').checked) {
      caixa.innerHTML = '<p class="vazio">Desenho desligado.</p>';
      return;
    }
    // O desenho sempre usa a Trie local: é a estrutura que está em memória
    // aqui, e o servidor não devolve a forma da árvore, só a resposta.
    caixa.innerHTML = UI.desenharArvore(estado.aplicacao.trie, prefixo);
  }

  async function verificarPalavra() {
    const palavra = $('#entrada-parte1').value.trim();
    if (!palavra) return recadoDe('parte1', 'Escreva a palavra que quer verificar.');

    try {
      const dados = await estado.motor.buscarNoLexico(palavra);
      UI.Regua.marcar({
        segundos: dados.tempo,
        rotulo: `Trie · busca exata "${palavra}"`,
        via: 'trie',
        repeticoes: dados.repeticoes || 1,
      });

      if (dados.existe) {
        const continua = dados.continuacoes
          ? ` Outras <b>${numero(dados.continuacoes)}</b> palavras continuam a partir dela.`
          : '';
        recadoDe('parte1', `<b>${escapar(dados.formas.join(', '))}</b> está no léxico.${continua}`);
      } else if (dados.continuacoes) {
        // A distinção que a Trie torna barata: o caminho existir não faz da
        // sequência uma palavra; só o nó marcado como fim de palavra faz.
        recadoDe('parte1', `<b>${escapar(palavra)}</b> não está no léxico, mas é prefixo de
          <b>${numero(dados.continuacoes)}</b> ${plural(dados.continuacoes, 'palavra', 'palavras')} —
          o caminho existe na Trie; o nó final é que não está marcado como fim de palavra.`);
      } else {
        recadoDe('parte1', `<b>${escapar(palavra)}</b> não está no léxico, e nenhuma palavra
          começa por essa sequência.`);
      }
    } catch (falha) {
      recadoDe('parte1', mensagemDeFalha(falha), true);
    }
  }

  async function inserirPalavra() {
    const palavra = $('#entrada-parte1').value.trim();
    if (!palavra) return recadoDe('parte1', 'Escreva a palavra que quer inserir.');

    try {
      const dados = await estado.motor.inserirNoLexico(palavra);

      // Com o motor no servidor, a Trie local também recebe a palavra: é ela
      // que o desenho percorre, e as duas precisam contar a mesma história.
      if (estado.motor !== estado.motorLocal) estado.aplicacao.inserirNoLexico(palavra);

      UI.Regua.marcar({
        segundos: dados.tempo,
        rotulo: `Trie · inserção de "${dados.palavra}"`,
        via: 'trie',
        repeticoes: 1,
      });

      $('[data-campo="lexico"]').textContent = numero(dados.palavras);
      recadoDe('parte1', dados.nova
        ? `<b>${escapar(dados.palavra)}</b> entrou na Trie. O léxico agora tem
           <b>${numero(dados.palavras)}</b> palavras em <b>${numero(dados.nos)}</b> nós —
           vale enquanto esta página estiver aberta.`
        : `<b>${escapar(dados.palavra)}</b> já estava na Trie; nenhum nó novo foi criado.`);

      consultarPrefixo();
    } catch (falha) {
      recadoDe('parte1', mensagemDeFalha(falha), true);
    }
  }

  /* =========================================================================
     PARTE II -- BUSCA NOS DOCUMENTOS
     ========================================================================= */

  const MODOS = {
    palavra: {
      via: 'indice',
      exemplo: 'algoritmo',
      aoVivo: true,
      tese: 'A palavra digitada passa pelo mesmo pré-processamento dos documentos e ' +
        'vira um radical; esse radical é a chave consultada no <b>índice invertido</b>, ' +
        'que responde por hash em <b>O(1)</b> médio. O BM25 ordena o que voltou.',
    },
    prefixo: {
      via: 'trie',
      exemplo: 'comput',
      aoVivo: true,
      tese: 'Duas estruturas encadeadas: a <b>Trie</b> devolve os termos do vocabulário ' +
        'que começam com o prefixo, e o <b>índice invertido</b> diz em que documentos ' +
        'cada um deles aparece. A Trie responde em duas ordens — a alfabética, que o ' +
        'enunciado pede, e a de <b>relevância</b>, que a busca best-first alcança sem ' +
        'varrer a subárvore.',
    },
    sequencia: {
      via: 'kmp',
      exemplo: 'chave pública',
      aoVivo: false,
      tese: 'O <b>KMP</b> varre o conteúdo original de todos os documentos, sem passar ' +
        'pelo índice: encontra pedaços de palavra e expressões com pontuação, ao custo ' +
        'de ser linear no tamanho do corpus. É a única modalidade que só roda quando ' +
        'você pede — ela custa milissegundos, não microssegundos.',
    },
  };

  function trocarModo(modo) {
    estado.modo = modo;
    for (const botao of $$('.modo')) {
      const ativo = botao.dataset.modo === modo;
      botao.classList.toggle('ativo', ativo);
      botao.setAttribute('aria-checked', String(ativo));
    }

    $('#tese-parte2').innerHTML = MODOS[modo].tese;
    $('#entrada-parte2').placeholder = MODOS[modo].exemplo;
    recadoDe('parte2', '');

    if ($('#entrada-parte2').value.trim()) consultarDocumentos();
  }

  async function consultarDocumentos() {
    const consulta = $('#entrada-parte2').value.trim();
    const saida = $('#saida-parte2');
    const modo = MODOS[estado.modo];
    const meu = ++estado.sequencia.parte2;

    if (!consulta) {
      saida.innerHTML = '<p class="vazio">Escolha uma modalidade e faça a primeira consulta.</p>';
      recadoDe('parte2', '');
      return;
    }

    try {
      let dados;
      if (estado.modo === 'palavra') dados = await estado.motor.buscarPalavra(consulta);
      else if (estado.modo === 'prefixo') dados = await estado.motor.buscarPrefixo(consulta, LIMITE_PARTE2);
      else dados = await estado.motor.buscarSequencia(consulta);

      if (meu !== estado.sequencia.parte2) return;

      UI.Regua.marcar({
        segundos: dados.tempo,
        rotulo: `${estado.modo} · "${consulta}"`,
        via: modo.via,
        repeticoes: dados.repeticoes || 1,
      });
      recadoDe('parte2', '');

      if (estado.modo === 'palavra') saida.innerHTML = desenharPalavra(dados);
      else if (estado.modo === 'prefixo') saida.innerHTML = desenharPrefixo(dados, consulta);
      else {
        saida.innerHTML = desenharSequencia(dados, consulta);
        montarFita(dados, consulta);
      }

      ligarDocumentosClicaveis(saida, consulta);
    } catch (falha) {
      if (meu === estado.sequencia.parte2) recadoDe('parte2', mensagemDeFalha(falha), true);
    }
  }

  /* ------------------------------------------------------------- palavra */

  /** A trilha do RSLP: qual regra transformou o quê, até chegar ao radical. */
  function trilhaDoRadical(termo) {
    const stemmer = estado.aplicacao.mecanismo.preprocessador.stemmer;
    const explicacao = stemmer.explicar(termo);
    if (!explicacao.etapas.length) {
      return `<p class="nota">O RSLP não encontrou sufixo a remover em
        <b>${escapar(termo)}</b>: o radical é a própria palavra.</p>`;
    }

    const passos = [{ passo: 'digitado', para: explicacao.palavra }]
      .concat(explicacao.etapas.map((etapa) => ({ passo: etapa.passo, para: etapa.para })));

    return `<div class="trilha">${passos.map((etapa, indice) => {
      const final = indice === passos.length - 1;
      return `${indice ? '<span class="trilha-seta">→</span>' : ''}
        <span class="trilha-passo${final ? ' final' : ''}">
          <span>${escapar(etapa.passo)}</span><b>${escapar(etapa.para)}</b>
        </span>`;
    }).join('')}</div>`;
  }

  function desenharPalavra(dados) {
    if (!dados.documentos.length) {
      return `<p class="vazio">Nenhum documento contém <b>${escapar(dados.termo || '')}</b>.
        Experimente a busca por sequência: ela procura no texto bruto, sem índice.</p>`;
    }

    const total = dados.documentos.length;
    const exatos = Object.keys(dados.exatos || {}).length;

    let nota = `<p class="nota">O radical <b>${escapar(dados.radical)}</b> é a chave
      consultada no índice.`;
    if (exatos && exatos < total) {
      nota += ` A forma exata <b>${escapar(dados.termo)}</b> apareceria em
        ${numero(exatos)} ${plural(exatos, 'arquivo', 'arquivos')}; o radical alcança
        <b>${numero(total)}</b>, reunindo as variantes da palavra.`;
    }
    nota += '</p>';

    return `<p class="subtitulo">Do que você digitou até a chave do índice</p>` +
      trilhaDoRadical(dados.termo) +
      `<p class="subtitulo">${numero(total)} ${plural(total, 'arquivo', 'arquivos')} · ordenados por BM25</p>` +
      UI.barras(dados.documentos, dados.frequencias, { clicavel: true }) +
      nota;
  }

  /* ------------------------------------------------------------- prefixo */

  function desenharPrefixo(dados, consulta) {
    if (!dados.termos.length) {
      return `<p class="vazio">Nenhum termo do vocabulário começa com
        <b>${escapar(consulta)}</b>.</p>`;
    }

    const contagem = (termo) => {
      const quantos = (dados.por_termo[termo] || []).length;
      return `${quantos} ${plural(quantos, 'doc', 'docs')}`;
    };

    const cabeca = dados.truncado
      ? `${numero(dados.termos.length)} de ${numero(dados.total_disponivel)} termos`
      : `${numero(dados.termos.length)} ${plural(dados.termos.length, 'termo', 'termos')}`;

    const ranking = dados.ranking.slice(0, 8);
    const documentos = ranking.length
      ? `<p class="subtitulo">${numero(dados.documentos.length)} documentos alcançados · 8 melhores por BM25</p>` +
        UI.barras(ranking, null, { clicavel: true })
      : '';

    return sugestoesRelevantes(dados, consulta) +
      `<p class="subtitulo">${cabeca} no vocabulário do corpus · ordem alfabética</p>` +
      UI.feixe(dados.termos, consulta.length, contagem) + documentos;
  }

  /**
   * As palavras mais frequentes sob o prefixo, na ordem que um autocomplete de
   * verdade usaria.
   *
   * Vale mostrar ao lado da lista alfabética porque as duas respondem à mesma
   * pergunta e discordam: para "com", o alfabeto entrega "combate" e a
   * relevância entrega "computador". A lista alfabética é a que o enunciado
   * pede; esta é a que a Trie consegue produzir sem varrer a subárvore, pela
   * busca best-first sobre os pesos.
   */
  function sugestoesRelevantes(dados, consulta) {
    const sugestoes = dados.sugestoes || [];
    if (!sugestoes.length) return '';

    const maior = Math.max(...sugestoes.map(([, peso]) => peso), 1);
    const linhas = sugestoes.map(([palavra, peso]) => `
      <li class="postagem">
        <span class="arquivo"><span class="eco">${escapar(palavra.slice(0, consulta.length))}</span>${escapar(palavra.slice(consulta.length))}</span>
        <span class="barra-nota secundaria"><i style="width:${Math.max(2, (peso / maior) * 100).toFixed(1)}%"></i></span>
        <span class="numero">${numero(peso)}×</span>
        <span class="vezes"></span>
      </li>`).join('');

    return `<p class="subtitulo">Mais relevantes · por frequência no corpus</p>
      <ul class="postagens">${linhas}</ul>`;
  }

  /* ----------------------------------------------------------- sequência */

  function desenharSequencia(dados, consulta) {
    const rodape = `<p class="nota">O KMP fez <b>${numero(dados.comparacoes)}</b>
      comparações de caractere para varrer o corpus inteiro. Compare com a busca por
      palavra: lá o índice já sabia a resposta antes de você perguntar.</p>`;

    if (!dados.resultados.length) {
      return `<p class="vazio">A sequência <b>${escapar(consulta)}</b> não aparece em
        nenhum documento.</p>` + rodape;
    }

    const blocos = dados.resultados.map((item) => `
      <article class="trecho">
        <div class="trecho-cabeca">
          <button type="button" class="arquivo" data-documento="${escapar(item.documento)}">
            <b>${escapar(item.documento)}</b></button>
          <span>${numero(item.ocorrencias)} ${plural(item.ocorrencias, 'ocorrência', 'ocorrências')}</span>
        </div>
        ${item.contextos.map((contexto) => `<p>${realcar(contexto, consulta)}</p>`).join('')}
      </article>`).join('');

    return `<p class="subtitulo">${numero(dados.total_ocorrencias)}
      ${plural(dados.total_ocorrencias, 'ocorrência', 'ocorrências')} em
      ${numero(dados.resultados.length)} ${plural(dados.resultados.length, 'arquivo', 'arquivos')}</p>` +
      blocos +
      `<p class="subtitulo">O algoritmo, passo a passo</p>
       <div class="fita-kmp" id="fita-kmp"></div>` +
      rodape;
  }

  /** Monta a fita sobre o documento em que o padrão mais aparece. */
  function montarFita(dados, consulta) {
    const caixa = $('#fita-kmp');
    if (!caixa) return;

    const conteudo = estado.aplicacao.mecanismo.conteudo;
    const escolhido = dados.resultados.length
      ? dados.resultados[0].documento
      : Array.from(conteudo.keys())[0];

    estado.fita = new UI.FitaKMP(caixa);
    estado.fita.montar(conteudo.get(escolhido), consulta, { rotulo: escolhido });
  }

  /* =========================================================================
     LEITOR DE DOCUMENTOS
     ========================================================================= */

  function ligarDocumentosClicaveis(raiz, consulta) {
    for (const botao of $$('[data-documento]', raiz)) {
      botao.addEventListener('click', () => abrirDocumento(botao.dataset.documento, consulta));
    }
  }

  function abrirDocumento(nome, realce = '') {
    const texto = estado.aplicacao.mecanismo.conteudo.get(nome);
    if (texto === undefined) return;

    abrirPainel('documentos');

    // O leitor mora fora de `#saida-documentos` de propósito: abrir a tela pela
    // primeira vez dispara `carregarDocumentos`, que reescreve aquele bloco
    // inteiro -- e levaria junto o documento recém-aberto.
    const leitor = $('#leitor-documento');

    const corpo = realce ? realcar(texto, realce) : escapar(texto);
    const ocorrencias = realce
      ? A1.buscarKmp(texto.toLowerCase(), realce.toLowerCase()).ocorrencias.length
      : 0;

    leitor.className = 'leitor';
    leitor.innerHTML = `
      <div class="leitor-cabeca">
        <b>${escapar(nome)}</b>
        <span>${numero(texto.length)} caracteres${realce
          ? ` · ${numero(ocorrencias)} ${plural(ocorrencias, 'ocorrência', 'ocorrências')} de "${escapar(realce)}"`
          : ''}</span>
      </div>
      <pre class="leitor-texto">${corpo}</pre>`;

    leitor.scrollIntoView({ block: 'nearest' });

    const primeiro = $('mark', leitor);
    if (primeiro) primeiro.scrollIntoView({ block: 'center' });
  }

  async function carregarDocumentos() {
    const saida = $('#saida-documentos');
    let lista;
    try {
      lista = (await estado.motor.documentos()).documentos;
    } catch (falha) {
      saida.innerHTML = `<p class="recado falha">${mensagemDeFalha(falha)}</p>`;
      return;
    }

    const totalBytes = lista.reduce((soma, item) => soma + item.bytes, 0);
    const totalTokens = lista.reduce((soma, item) => soma + item.tokens, 0);

    saida.innerHTML = `<p class="subtitulo">${numero(lista.length)} arquivos ·
      ${(totalBytes / 1024).toFixed(0)} KB · ${numero(totalTokens)} tokens indexados</p>
      <div class="rolagem"><table class="tabela">
        <thead><tr><th>arquivo</th><th class="num">KB</th><th class="num">tokens</th>
          <th class="num">termos distintos</th></tr></thead>
        <tbody>${lista.map((documento) => {
          const distintos = contarDistintos(documento.documento);
          return `<tr>
            <td><button type="button" data-documento="${escapar(documento.documento)}">${escapar(documento.documento)}</button></td>
            <td class="num">${(documento.bytes / 1024).toFixed(1)}</td>
            <td class="num">${numero(documento.tokens)}</td>
            <td class="num">${numero(distintos)}</td></tr>`;
        }).join('')}</tbody>
      </table></div>`;

    ligarDocumentosClicaveis(saida, '');
  }

  /** Termos distintos de um documento, lidos do índice já construído. */
  function contarDistintos(nome) {
    let total = 0;
    for (const postagem of estado.aplicacao.mecanismo.indice.porRadical.values()) {
      if (postagem.has(nome)) total += 1;
    }
    return total;
  }

  /* =========================================================================
     COMPARAÇÃO ENTRE AS DUAS VIAS
     ========================================================================= */

  /**
   * A mesma consulta pelas duas estradas: o índice e a varredura.
   *
   * É o resultado central do trabalho, e o único jeito de mostrá-lo sem margem
   * a dúvida é rodar as duas coisas, uma atrás da outra, na mesma máquina e no
   * mesmo instante.
   */
  async function compararVias() {
    const consulta = $('#entrada-parte2').value.trim();
    if (!consulta) return recadoDe('parte2', 'Escreva o que quer procurar.');

    recadoDe('parte2', 'Rodando as duas vias…');
    await respirar();

    try {
      const porIndice = await estado.motor.buscarPalavra(consulta);
      const porKmp = await estado.motor.buscarSequencia(consulta);

      UI.Regua.marcar({
        segundos: porIndice.tempo, rotulo: `índice · "${consulta}"`,
        via: 'indice', repeticoes: porIndice.repeticoes || 1,
      });
      UI.Regua.marcar({
        segundos: porKmp.tempo, rotulo: `KMP · "${consulta}"`,
        via: 'kmp', repeticoes: porKmp.repeticoes || 1,
      });

      const razao = porKmp.tempo / porIndice.tempo;
      $('#saida-parte2').innerHTML = `
        <p class="subtitulo">A mesma consulta, duas estradas</p>
        ${UI.graficoBarras({
          itens: [
            { nome: 'índice invertido', valor: porIndice.tempo * 1e6, cor: 'a' },
            { nome: 'varredura com KMP', valor: porKmp.tempo * 1e6, cor: 'c' },
          ],
          formatar: (v) => A1.formatarDuracao(v / 1e6),
        })}
        <div class="grade">
          <dl class="quadro">
            <div><dt>Índice · documentos</dt><dd>${numero(porIndice.documentos.length)}</dd></div>
            <div><dt>Índice · tempo</dt><dd>${escapar(A1.formatarDuracao(porIndice.tempo))}</dd></div>
            <div><dt>Índice · classe</dt><dd>O(1) médio</dd></div>
          </dl>
          <dl class="quadro">
            <div><dt>KMP · documentos</dt><dd>${numero(porKmp.resultados.length)}</dd></div>
            <div><dt>KMP · tempo</dt><dd>${escapar(A1.formatarDuracao(porKmp.tempo))}</dd></div>
            <div><dt>KMP · comparações</dt><dd>${numero(porKmp.comparacoes)}</dd></div>
          </dl>
        </div>
        <p class="conclusao">A varredura custou <b>${razao >= 10 ? numero(Math.round(razao)) : razao.toFixed(1)}×</b>
          o tempo da consulta indexada. As duas respondem à mesma pergunta; a diferença é
          que o índice fez o trabalho antes, na construção, e a varredura faz tudo agora,
          a cada consulta. Na régua abaixo, as duas marcas estão a
          <b>${(Math.log10(razao)).toFixed(1)}</b> casas decimais de distância.</p>`;

      recadoDe('parte2', '');
    } catch (falha) {
      recadoDe('parte2', mensagemDeFalha(falha), true);
    }
  }

  /* =========================================================================
     MÉTRICAS
     ========================================================================= */

  const NOMES = {
    leitura: 'Leitura dos arquivos',
    preprocessamento: 'Pré-processamento',
    trie: 'Construção da Trie',
    indice: 'Construção do índice',
    total: 'Total',
    chaves: 'Chaves',
    capacidade: 'Capacidade',
    'fator de carga': 'Fator de carga',
    'baldes ocupados': 'Baldes ocupados',
    colisoes: 'Colisões',
    'maior cadeia': 'Maior cadeia',
    'cadeia media': 'Cadeia média',
    'stopwords carregadas': 'Stopwords carregadas',
    stemming: 'Stemming',
    'tamanho minimo do token': 'Tamanho mínimo do token',
  };

  const nomear = (chave) => NOMES[chave] || chave.charAt(0).toUpperCase() + chave.slice(1);

  function quadro(titulo, linhas) {
    const itens = linhas.map(([rotulo, valor]) =>
      `<div><dt>${escapar(rotulo)}</dt><dd>${escapar(valor)}</dd></div>`).join('');
    return `<section><p class="subtitulo">${escapar(titulo)}</p>
      <dl class="quadro">${itens}</dl></section>`;
  }

  async function carregarMetricas() {
    const saida = $('#saida-metricas');
    saida.innerHTML = '<p class="vazio">Lendo as estruturas…</p>';

    let dados;
    try {
      dados = await estado.motor.estatisticas();
    } catch (falha) {
      saida.innerHTML = `<p class="recado falha">${mensagemDeFalha(falha)}</p>`;
      return;
    }

    const c = dados.corpus;
    const m = dados.memoria;

    const quadros = [
      quadro('Corpus', [
        ['Documentos processados', numero(c.documentos)],
        ['Palavras após a tokenização', numero(c.palavras)],
        ['Palavras antes das stopwords', `${numero(c.palavras_brutas)} (−${porcentagem(c.reducao_stopwords)})`],
        ['Termos distintos', numero(c.termos)],
        ['Palavras na Trie', numero(c.palavras_na_trie)],
        ['Radicais no índice', numero(c.radicais)],
        ['Postagens termo-documento', numero(c.postagens)],
      ]),
      quadro('Memória das estruturas', [
        ['Nós na Trie tradicional', numero(m.nos_trie)],
        ['Nós na Trie comprimida', numero(m.nos_trie_comprimida)],
        ['Economia da compressão', porcentagem(m.economia)],
      ]),
      quadro('Tempos de construção', Object.entries(dados.construcao).map(
        ([fase, valor]) => [nomear(fase), micro(valor)])),
      quadro('Tabela hash do índice', Object.entries(dados.hash).map(
        ([chave, valor]) => [nomear(chave), numero(valor)])),
      quadro('Pré-processamento', Object.entries(dados.preprocessamento).map(
        ([chave, valor]) => [nomear(chave), valor])),
    ].join('');

    const porTipo = Object.entries(dados.consultas.por_tipo || {});
    const consultas = porTipo.length
      ? `<p class="subtitulo">Consultas desta sessão (${numero(dados.consultas.total)})</p>
         <div class="rolagem"><table class="tabela">
           <thead><tr><th>modalidade</th><th class="num">consultas</th>
             <th class="num">tempo total</th><th class="num">tempo médio</th></tr></thead>
           <tbody>${porTipo.map(([tipo, valores]) => `<tr>
             <td>${escapar(tipo)}</td><td class="num">${numero(valores.quantidade)}</td>
             <td class="num">${escapar(micro(valores.total))}</td>
             <td class="num">${escapar(micro(valores.media))}</td></tr>`).join('')}
           </tbody></table></div>
         <p class="subtitulo">Últimas consultas</p>
         <div class="rolagem"><table class="tabela">
           <thead><tr><th>modalidade</th><th>texto</th><th class="num">resultados</th>
             <th class="num">tempo</th></tr></thead>
           <tbody>${dados.consultas.ultimas.slice().reverse().map((linha) => `<tr>
             <td>${escapar(linha.tipo)}</td><td>${escapar(linha.texto)}</td>
             <td class="num">${numero(linha.resultados)}</td>
             <td class="num">${escapar(micro(linha.tempo))}</td></tr>`).join('')}
           </tbody></table></div>`
      : '<p class="vazio">Nenhuma consulta feita ainda nesta sessão.</p>';

    const frequentes = estado.aplicacao.mecanismo.indice.termosMaisFrequentes(12);
    const tabelaFrequentes = `<p class="subtitulo">Radicais mais frequentes</p>
      <div class="rolagem"><table class="tabela">
        <thead><tr><th>radical</th><th class="num">documentos</th>
          <th class="num">ocorrências</th></tr></thead>
        <tbody>${frequentes.map((linha) => `<tr>
          <td>${escapar(linha.termo)}</td><td class="num">${numero(linha.documentos)}</td>
          <td class="num">${numero(linha.ocorrencias)}</td></tr>`).join('')}
        </tbody></table></div>`;

    const dispersao = estado.aplicacao.mecanismo.indice.espelharEmTabelaHash()
      .distribuicaoDeCadeias();
    const grafico = `<p class="subtitulo">Dispersão da tabela hash</p>` +
      UI.graficoBarras({
        itens: dispersao.map((linha) => ({
          nome: `${linha.tamanho} ${plural(linha.tamanho, 'chave', 'chaves')}`,
          valor: linha.baldes,
          cor: linha.tamanho <= 1 ? 'b' : (linha.tamanho <= 3 ? 'a' : 'c'),
        })),
        formatar: (v) => `${numero(Math.round(v))} baldes`,
      }) +
      `<p class="conclusao">Cada barra é um comprimento de cadeia. Quanto mais massa à
        esquerda, melhor a dispersão: são os baldes que respondem em uma comparação só.</p>`;

    saida.innerHTML = `<div class="grade">${quadros}</div>${grafico}${tabelaFrequentes}${consultas}`;
  }

  /* =========================================================================
     NAVEGAÇÃO, TEMA E TECLADO
     ========================================================================= */

  function abrirPainel(nome) {
    for (const botao of $$('.canal-botao')) {
      const ativo = botao.dataset.painel === nome;
      botao.classList.toggle('ativo', ativo);
      if (ativo) botao.setAttribute('aria-current', 'true');
      else botao.removeAttribute('aria-current');
    }

    for (const painel of $$('.painel')) {
      const ativo = painel.id === nome;
      painel.classList.toggle('ativo', ativo);
      painel.hidden = !ativo;
    }

    $('.area').scrollTop = 0;

    // A primeira abertura já traz um exemplo pronto, para que a tela nunca
    // apareça vazia esperando que alguém adivinhe o que digitar.
    if (!estado.painelVisitado[nome]) {
      estado.painelVisitado[nome] = true;
      if (nome === 'parte2') {
        $('#entrada-parte2').value = MODOS[estado.modo].exemplo;
        consultarDocumentos();
      }
      if (nome === 'metricas') carregarMetricas();
      if (nome === 'documentos') carregarDocumentos();
      if (nome === 'laboratorio') UI.montarLaboratorio($('#experimentos'));
    }
  }

  function guardar(chave, valor) {
    try { localStorage.setItem(chave, valor); } catch (falha) { /* sessão anônima */ }
  }

  function lembrar(chave, padrao) {
    try { return localStorage.getItem(chave) ?? padrao; } catch (falha) { return padrao; }
  }

  function aplicarTema(tema) {
    document.documentElement.dataset.tema = tema;
    $('#icone-tema').textContent = tema === 'escuro' ? '☾' : '☀';
    guardar('tema', tema);
  }

  function aplicarProjetor(ligado) {
    document.documentElement.dataset.projetor = ligado ? 'sim' : 'nao';
    $('#trocar-projetor').setAttribute('aria-pressed', String(ligado));
    guardar('projetor', ligado ? 'sim' : 'nao');
  }

  function atalhos(evento) {
    const ajuda = $('#ajuda');

    if (evento.key === 'Escape') {
      if (ajuda.open) ajuda.close();
      return;
    }

    const digitando = ['INPUT', 'TEXTAREA'].includes(document.activeElement.tagName);
    if (digitando || evento.ctrlKey || evento.altKey || evento.metaKey) return;

    const paineis = ['parte1', 'parte2', 'laboratorio', 'metricas', 'documentos'];
    const indice = Number(evento.key) - 1;
    if (indice >= 0 && indice < paineis.length) {
      evento.preventDefault();
      return abrirPainel(paineis[indice]);
    }

    if (evento.key === '/') {
      evento.preventDefault();
      const painelAtivo = $('.painel.ativo');
      const campo = $('input[type="search"]', painelAtivo);
      if (campo) campo.focus();
      else $('#entrada-parte2').focus();
      return;
    }

    if (evento.key === '?') { evento.preventDefault(); ajuda.showModal(); return; }
    if (evento.key.toLowerCase() === 't') {
      aplicarTema(document.documentElement.dataset.tema === 'escuro' ? 'claro' : 'escuro');
      return;
    }
    if (evento.key.toLowerCase() === 'p') {
      aplicarProjetor(document.documentElement.dataset.projetor !== 'sim');
    }
  }

  /* =========================================================================
     LIGAÇÕES
     ========================================================================= */

  function ligar() {
    for (const botao of $$('.canal-botao')) {
      botao.addEventListener('click', () => abrirPainel(botao.dataset.painel));
    }

    // --- Parte I ---
    const digitouParte1 = esperar(consultarPrefixo, ESPERA_DIGITACAO);
    $('#entrada-parte1').addEventListener('input', digitouParte1);
    $('#forma-parte1').addEventListener('submit', (evento) => {
      evento.preventDefault();
      consultarPrefixo();
    });
    $('[data-acao="verificar"]').addEventListener('click', verificarPalavra);
    $('[data-acao="inserir"]').addEventListener('click', inserirPalavra);
    $('#mostrar-arvore').addEventListener('change', () =>
      desenharArvore($('#entrada-parte1').value.trim()));

    // --- Parte II ---
    for (const botao of $$('.modo')) {
      botao.addEventListener('click', () => trocarModo(botao.dataset.modo));
    }
    $('#forma-parte2').addEventListener('submit', (evento) => {
      evento.preventDefault();
      consultarDocumentos();
    });
    $('#comparar-vias').addEventListener('click', compararVias);

    // Só as modalidades indexadas consultam a cada tecla. O KMP varre o corpus
    // inteiro; dispará-lo a cada caractere mediria a digitação, não o algoritmo.
    const digitouParte2 = esperar(() => {
      if (MODOS[estado.modo].aoVivo) consultarDocumentos();
    }, ESPERA_DIGITACAO + 90);
    $('#entrada-parte2').addEventListener('input', digitouParte2);

    // --- laboratório ---
    $('#experimentos').addEventListener('click', (evento) => {
      const botao = evento.target.closest('[data-experimento]');
      if (botao) UI.rodarExperimento(botao.dataset.experimento, { ...contextoDoLab() });
    });
    $('#rodar-tudo').addEventListener('click', () => UI.rodarTodos(contextoDoLab()));
    $('#limpar-lab').addEventListener('click', UI.limparLaboratorio);

    // --- métricas e documentos ---
    $('#atualizar-metricas').addEventListener('click', carregarMetricas);

    // --- barra ---
    $('#trocar-tema').addEventListener('click', () =>
      aplicarTema(document.documentElement.dataset.tema === 'escuro' ? 'claro' : 'escuro'));
    $('#trocar-projetor').addEventListener('click', () =>
      aplicarProjetor(document.documentElement.dataset.projetor !== 'sim'));
    $('#abrir-ajuda').addEventListener('click', () => $('#ajuda').showModal());
    $('#fechar-ajuda').addEventListener('click', () => $('#ajuda').close());

    document.addEventListener('keydown', atalhos);
  }

  function contextoDoLab() {
    return {
      aplicacao: estado.aplicacao,
      lexico: window.DADOS.lexico,
      corpus: window.DADOS.corpus,
    };
  }

  /* =========================================================================
     PARTIDA
     ========================================================================= */

  async function comecar() {
    aplicarTema(lembrar('tema', 'escuro'));
    aplicarProjetor(lembrar('projetor', 'nao') === 'sim');

    await construir();

    UI.Regua.montar();
    ligar();
    await prepararMotor();
    await carregarEstado();

    $('#tese-parte2').innerHTML = MODOS.palavra.tese;
    $('#entrada-parte1').value = 'comp';
    consultarPrefixo();
    $('#entrada-parte1').focus();
  }

  document.addEventListener('DOMContentLoaded', comecar);

})(window.UI, window.A1);
