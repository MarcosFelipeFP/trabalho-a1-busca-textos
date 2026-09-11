/* =========================================================================
   app.js
   Liga a interface às rotas de `servidor.py`.

   Nenhuma lógica de busca vive aqui: a Trie, o índice invertido e o KMP rodam
   no Python. Este arquivo só envia a consulta, desenha o resultado e mostra o
   tempo que o servidor mediu -- o mesmo cronômetro que a versão de terminal
   usa, para que os dois números possam ser comparados.
   ========================================================================= */

'use strict';

const $ = (seletor, raiz = document) => raiz.querySelector(seletor);
const $$ = (seletor, raiz = document) => Array.from(raiz.querySelectorAll(seletor));

const ESPERA_DIGITACAO = 130;   // ms de silêncio antes de consultar
const LIMITE_PARTE1 = 40;
const LIMITE_PARTE2 = 30;

const historico = { parte1: [], parte2: [] };
const sequencia = { parte1: 0, parte2: 0 };

/* ------------------------------------------------------------- utilidades */

function escapar(texto) {
  return String(texto)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/** Mesma regra de `estatisticas.formatar_duracao`, com o símbolo de micro. */
function duracao(segundos) {
  if (segundos >= 1) return `${segundos.toFixed(3)} s`;
  if (segundos >= 1e-3) return `${(segundos * 1e3).toFixed(3)} ms`;
  return `${(segundos * 1e6).toFixed(1)} µs`;
}

const numero = (valor) => Number(valor).toLocaleString('pt-BR');
const plural = (n, singular, pluralForma) => (n === 1 ? singular : pluralForma);

/** Envolve em <mark> cada ocorrência da consulta dentro do trecho. */
function realcar(texto, consulta) {
  const seguro = escapar(texto);
  const alvo = escapar(consulta).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  if (!alvo) return seguro;
  return seguro.replace(new RegExp(alvo, 'gi'), (achado) => `<mark>${achado}</mark>`);
}

function esperar(funcao, atraso) {
  let marcador = null;
  return (...argumentos) => {
    clearTimeout(marcador);
    marcador = setTimeout(() => funcao(...argumentos), atraso);
  };
}

async function pedir(rota, parametros = {}) {
  const endereco = new URL(rota, window.location.origin);
  Object.entries(parametros).forEach(([chave, valor]) => {
    endereco.searchParams.set(chave, valor);
  });

  const resposta = await fetch(endereco, { headers: { Accept: 'application/json' } });
  const dados = await resposta.json();
  if (!resposta.ok) throw new Error(dados.erro || `falha ${resposta.status}`);
  return dados;
}

/* ---------------------------------------------------------------- medidor */

/**
 * Escreve a leitura de custo e empilha mais uma barra no histórico.
 *
 * A altura da barra é logarítmica: entre 1 µs e 100 ms a diferença é de cinco
 * ordens de grandeza, e em escala linear as consultas indexadas sumiriam
 * embaixo de qualquer varredura.
 */
function medir(parte, segundos, classe, via) {
  const medidor = $(`#medidor-${parte}`);
  const lenta = segundos >= 1e-3;

  medidor.classList.toggle('lenta', lenta);
  $('.leitura', medidor).textContent = duracao(segundos);
  $('.classe', medidor).textContent = classe;
  $('.via', medidor).textContent = via;

  const registro = historico[parte];
  registro.push({ segundos, lenta });
  if (registro.length > 14) registro.shift();

  $('.historico', medidor).innerHTML = registro.map(({ segundos: s, lenta: l }) => {
    const micros = Math.max(s * 1e6, 1);
    const altura = 2 + 26 * Math.min(Math.log10(micros) / 5, 1);
    return `<i class="${l ? 'lenta' : ''}" style="height:${altura.toFixed(1)}px"
             title="${duracao(s)}"></i>`;
  }).join('');
}

function avisar(parte, mensagem, falhou = false) {
  const aviso = $(`#aviso-${parte}`);
  aviso.textContent = mensagem || '';
  aviso.classList.toggle('falha', falhou);
}

/* ------------------------------------------------------------------ feixe */

/**
 * Desenha a lista de palavras com o prefixo compartilhado desenhado uma vez só,
 * como a Trie o armazena: tinta cheia na primeira linha, eco nas seguintes, e o
 * traço vertical marcando onde o caminho comum termina e os ramos começam.
 */
function feixe(palavras, tamanhoPrefixo, contagem) {
  const linhas = palavras.map((palavra) => {
    const eco = escapar(palavra.slice(0, tamanhoPrefixo));
    const sufixo = escapar(palavra.slice(tamanhoPrefixo));
    const extra = contagem ? `<span class="contagem">${contagem(palavra)}</span>` : '';
    return `<li><span class="eco">${eco}</span><span class="sufixo">${sufixo}</span>${extra}</li>`;
  }).join('');

  return `<ul class="feixe" style="--haste:${tamanhoPrefixo}ch">${linhas}</ul>`;
}

/* ========================================================================
   PARTE I -- AUTOCOMPLETE
   ======================================================================== */

async function consultarPrefixo() {
  const prefixo = $('#entrada-parte1').value.trim();
  const saida = $('#saida-parte1');
  const meu = ++sequencia.parte1;

  if (!prefixo) {
    saida.innerHTML = '<p class="vazio">Digite um prefixo para ver a Trie responder.</p>';
    avisar('parte1', '');
    return;
  }

  try {
    const dados = await pedir('/api/parte1/prefixo', { q: prefixo, limite: LIMITE_PARTE1 });
    if (meu !== sequencia.parte1) return;   // chegou uma consulta mais nova

    medir('parte1', dados.tempo, 'O(m + p)', 'Trie · léxico em memória');

    if (!dados.palavras.length) {
      saida.innerHTML = `<p class="vazio">Nenhuma palavra do léxico começa com
        <b>${escapar(prefixo)}</b>. Use <b>Inserir no léxico</b> para acrescentá-la.</p>`;
      return;
    }

    const contador = dados.truncado
      ? `${numero(dados.palavras.length)} de ${numero(dados.total)} palavras`
      : `${numero(dados.total)} ${plural(dados.total, 'palavra', 'palavras')}`;

    saida.innerHTML = `<p class="subtitulo">${contador}</p>` +
      feixe(dados.palavras, prefixo.length);
  } catch (falha) {
    if (meu === sequencia.parte1) avisar('parte1', mensagemDeFalha(falha), true);
  }
}

async function verificarPalavra() {
  const palavra = $('#entrada-parte1').value.trim();
  if (!palavra) return avisar('parte1', 'Escreva a palavra que quer verificar.');

  try {
    const dados = await pedir('/api/parte1/palavra', { q: palavra });
    medir('parte1', dados.tempo, 'O(m)', 'Trie · busca exata');

    if (dados.existe) {
      const grafias = dados.formas.join(', ');
      const continua = dados.continuacoes
        ? ` Outras ${numero(dados.continuacoes)} palavras continuam a partir dela.`
        : '';
      avisar('parte1', `"${grafias}" está no léxico.${continua}`);
    } else if (dados.continuacoes) {
      // A distinção que a Trie torna barata: o caminho existir não faz da
      // sequência uma palavra; só o nó marcado como fim de palavra faz.
      avisar('parte1', `"${palavra}" não está no léxico, mas é prefixo de ` +
        `${numero(dados.continuacoes)} ${plural(dados.continuacoes, 'palavra', 'palavras')} — ` +
        `o caminho existe na Trie; o nó final é que não está marcado como fim de palavra.`);
    } else {
      avisar('parte1', `"${palavra}" não está no léxico, e nenhuma palavra começa ` +
        `por essa sequência. Use "Inserir no léxico" para acrescentá-la.`);
    }
  } catch (falha) {
    avisar('parte1', mensagemDeFalha(falha), true);
  }
}

async function inserirPalavra() {
  const palavra = $('#entrada-parte1').value.trim();
  if (!palavra) return avisar('parte1', 'Escreva a palavra que quer inserir.');

  try {
    const resposta = await fetch('/api/parte1/inserir', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ palavra }),
    });
    const dados = await resposta.json();
    if (!resposta.ok) throw new Error(dados.erro);

    medir('parte1', dados.tempo, 'O(m)', 'Trie · inserção');
    $('[data-campo="lexico"]').textContent = numero(dados.palavras);

    avisar('parte1', dados.nova
      ? `"${dados.palavra}" entrou na Trie. O léxico agora tem ${numero(dados.palavras)} ` +
        `palavras em ${numero(dados.nos)} nós — vale enquanto o servidor estiver no ar.`
      : `"${dados.palavra}" já estava na Trie; nenhum nó novo foi criado.`);

    consultarPrefixo();
  } catch (falha) {
    avisar('parte1', mensagemDeFalha(falha), true);
  }
}

/* ========================================================================
   PARTE II -- BUSCA NOS DOCUMENTOS
   ======================================================================== */

const MODOS = {
  palavra: {
    rota: '/api/parte2/palavra',
    classe: 'O(1) médio',
    via: 'índice invertido · tabela hash · BM25',
    exemplo: 'algoritmo',
    aoVivo: true,
    nota: 'A palavra digitada passa pelo mesmo pré-processamento dos documentos e ' +
          'vira um radical; esse radical é a chave consultada no índice invertido, ' +
          'que responde por <b>hash</b>. O BM25 ordena os documentos encontrados.',
  },
  prefixo: {
    rota: '/api/parte2/prefixo',
    classe: 'O(m + p)',
    via: 'Trie · índice invertido',
    exemplo: 'comput',
    aoVivo: true,
    nota: 'Duas estruturas encadeadas: a <b>Trie</b> devolve os termos do vocabulário ' +
          'que começam com o prefixo, e o <b>índice invertido</b> diz em que documentos ' +
          'cada um deles aparece.',
  },
  sequencia: {
    rota: '/api/parte2/sequencia',
    classe: 'O(N + m)',
    via: 'KMP · texto original, sem índice',
    exemplo: 'chave pública',
    aoVivo: false,
    nota: 'O <b>KMP</b> varre o conteúdo original de todos os documentos, sem passar ' +
          'pelo índice: encontra pedaços de palavra e expressões com pontuação, ao ' +
          'custo de ser linear no tamanho do corpus. É a única modalidade que só roda ' +
          'quando você pede — ela custa milissegundos, não microssegundos.',
  },
};

let modoAtual = 'palavra';

function trocarModo(modo) {
  modoAtual = modo;
  $$('.modo').forEach((botao) => {
    const ativo = botao.dataset.modo === modo;
    botao.classList.toggle('ativo', ativo);
    botao.setAttribute('aria-checked', String(ativo));
  });

  $('#nota-parte2').innerHTML = MODOS[modo].nota;
  $('#entrada-parte2').placeholder = MODOS[modo].exemplo;
  avisar('parte2', '');

  const entrada = $('#entrada-parte2');
  if (entrada.value.trim()) consultarDocumentos();
}

async function consultarDocumentos() {
  const consulta = $('#entrada-parte2').value.trim();
  const saida = $('#saida-parte2');
  const modo = MODOS[modoAtual];
  const meu = ++sequencia.parte2;

  if (!consulta) {
    saida.innerHTML = '<p class="vazio">Escolha uma modalidade e faça a primeira consulta.</p>';
    avisar('parte2', '');
    return;
  }

  try {
    const dados = await pedir(modo.rota, { q: consulta, limite: LIMITE_PARTE2 });
    if (meu !== sequencia.parte2) return;

    medir('parte2', dados.tempo, modo.classe, modo.via);
    avisar('parte2', '');

    if (modoAtual === 'palavra') saida.innerHTML = desenharPalavra(dados);
    else if (modoAtual === 'prefixo') saida.innerHTML = desenharPrefixo(dados, consulta);
    else saida.innerHTML = desenharSequencia(dados, consulta);
  } catch (falha) {
    if (meu === sequencia.parte2) avisar('parte2', mensagemDeFalha(falha), true);
  }
}

function barras(ranking, frequencias) {
  const maior = Math.max(...ranking.map(([, nota]) => nota), 1e-9);

  return `<ul class="postagens">${ranking.map(([documento, nota]) => {
    const largura = Math.max(2, (nota / maior) * 100);
    const vezes = frequencias && frequencias[documento];
    return `<li class="postagem">
      <span class="arquivo">${escapar(documento)}</span>
      <span class="barra" title="BM25 ${nota.toFixed(3)}"><i style="width:${largura.toFixed(1)}%"></i></span>
      <span class="numero">${nota.toFixed(3)}</span>
      <span class="vezes">${vezes ? `${numero(vezes)}×` : ''}</span>
    </li>`;
  }).join('')}</ul>`;
}

function desenharPalavra(dados) {
  if (!dados.documentos.length) {
    return `<p class="vazio">Nenhum documento contém <b>${escapar(dados.termo || '')}</b>.
      Experimente a busca por sequência: ela procura no texto bruto, sem índice.</p>`;
  }

  const total = dados.documentos.length;
  const exatos = Object.keys(dados.exatos || {}).length;

  let radical = `<p class="nota">O RSLP reduziu <b>${escapar(dados.termo)}</b> ao radical
    <b>${escapar(dados.radical)}</b>, e é esse radical que serve de chave no índice.`;
  if (exatos && exatos < total) {
    radical += ` A forma exata apareceria em ${numero(exatos)}
      ${plural(exatos, 'arquivo', 'arquivos')}; o radical alcança ${numero(total)},
      reunindo as variantes da palavra.`;
  }
  radical += '</p>';

  return `<p class="subtitulo">${numero(total)} ${plural(total, 'arquivo', 'arquivos')} · ordenados por BM25</p>` +
    barras(dados.documentos, dados.frequencias) + radical;
}

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
      barras(ranking, null)
    : '';

  return `<p class="subtitulo">${cabeca} no vocabulário</p>` +
    feixe(dados.termos, consulta.length, contagem) + documentos;
}

function desenharSequencia(dados, consulta) {
  const rodape = `<p class="nota">O KMP fez
    <b>${numero(dados.comparacoes)}</b> comparações de caractere para varrer o corpus
    inteiro. Compare com a busca por palavra: lá o índice já sabia a resposta.</p>`;

  if (!dados.resultados.length) {
    return `<p class="vazio">A sequência <b>${escapar(consulta)}</b> não aparece em
      nenhum documento.</p>` + rodape;
  }

  const blocos = dados.resultados.map((item) => `
    <article class="trecho">
      <div class="trecho-cabeca">
        <b>${escapar(item.documento)}</b>
        <span>${numero(item.ocorrencias)} ${plural(item.ocorrencias, 'ocorrência', 'ocorrências')}</span>
      </div>
      ${item.contextos.map((contexto) => `<p>${realcar(contexto, consulta)}</p>`).join('')}
    </article>`).join('');

  return `<p class="subtitulo">${numero(dados.total_ocorrencias)}
    ${plural(dados.total_ocorrencias, 'ocorrência', 'ocorrências')} em
    ${numero(dados.resultados.length)} ${plural(dados.resultados.length, 'arquivo', 'arquivos')}</p>` +
    blocos + rodape;
}

/* ========================================================================
   MÉTRICAS
   ======================================================================== */

function quadro(titulo, linhas) {
  const itens = linhas.map(([rotulo, valor]) =>
    `<div><dt>${escapar(rotulo)}</dt><dd>${escapar(valor)}</dd></div>`).join('');
  return `<section><p class="subtitulo">${escapar(titulo)}</p><dl class="quadro">${itens}</dl></section>`;
}

const porcentagem = (fracao) => `${(fracao * 100).toFixed(1)}%`;

// O servidor devolve as chaves sem acento, como o terminal as imprime. Aqui
// elas ganham a grafia que se lê melhor em tela.
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

// O terminal escreve "us" para não depender da codificação do console; na web
// cabe o símbolo de micro.
const micro = (texto) => String(texto).replace(/ us$/, ' µs');

async function carregarMetricas() {
  const saida = $('#saida-metricas');
  saida.innerHTML = '<p class="vazio">Lendo as estruturas…</p>';

  let dados;
  try {
    dados = await pedir('/api/estatisticas');
  } catch (falha) {
    saida.innerHTML = `<p class="aviso falha">${escapar(mensagemDeFalha(falha))}</p>`;
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
    quadro('Tempos de construção', Object.entries(dados.construcao).map(([fase, valor]) =>
      [nomear(fase), micro(valor)])),
    quadro('Tabela hash do índice', Object.entries(dados.hash).map(([chave, valor]) =>
      [nomear(chave), numero(valor)])),
    quadro('Pré-processamento', Object.entries(dados.preprocessamento).map(([chave, valor]) =>
      [nomear(chave), valor])),
  ].join('');

  const porTipo = Object.entries(dados.consultas.por_tipo);
  const consultas = porTipo.length
    ? `<p class="subtitulo">Consultas desta sessão (${numero(dados.consultas.total)})</p>
       <div class="rolagem"><table class="tabela">
         <thead><tr><th>modalidade</th><th>consultas</th><th>tempo total</th><th>tempo médio</th></tr></thead>
         <tbody>${porTipo.map(([tipo, valores]) => `<tr>
           <td>${escapar(tipo)}</td><td>${numero(valores.quantidade)}</td>
           <td>${escapar(micro(valores.total))}</td><td>${escapar(micro(valores.media))}</td></tr>`).join('')}
         </tbody>
       </table></div>
       <p class="subtitulo">Últimas consultas</p>
       <div class="rolagem"><table class="tabela">
         <thead><tr><th>modalidade</th><th>texto</th><th>resultados</th><th>tempo</th></tr></thead>
         <tbody>${dados.consultas.ultimas.slice().reverse().map((linha) => `<tr>
           <td>${escapar(linha.tipo)}</td><td>${escapar(linha.texto)}</td>
           <td>${numero(linha.resultados)}</td><td>${escapar(micro(linha.tempo))}</td></tr>`).join('')}
         </tbody>
       </table></div>`
    : '<p class="vazio">Nenhuma consulta feita ainda nesta sessão do servidor.</p>';

  let documentos = '';
  try {
    const lista = await pedir('/api/parte2/documentos');
    documentos = `<p class="subtitulo">Documentos indexados (${numero(lista.documentos.length)})</p>
      <div class="rolagem"><table class="tabela">
        <thead><tr><th>arquivo</th><th>KB</th><th>tokens</th></tr></thead>
        <tbody>${lista.documentos.map((documento) => `<tr>
          <td>${escapar(documento.documento)}</td>
          <td>${(documento.bytes / 1024).toFixed(1)}</td>
          <td>${numero(documento.tokens)}</td></tr>`).join('')}
        </tbody>
      </table></div>`;
  } catch (falha) {
    documentos = '';
  }

  saida.innerHTML = `<div class="grade">${quadros}</div>${consultas}${documentos}`;
}

/* ========================================================================
   INICIALIZAÇÃO
   ======================================================================== */

function mensagemDeFalha(falha) {
  if (falha instanceof TypeError) {
    return 'O servidor não respondeu. Confira se `python servidor.py` ainda está rodando.';
  }
  return falha.message || 'Não foi possível completar a consulta.';
}

async function carregarEstado() {
  try {
    const estado = await pedir('/api/estado');
    $('[data-campo="documentos"]').textContent = numero(estado.parte2.documentos);
    $('[data-campo="palavras"]').textContent = numero(estado.parte2.palavras);
    $('[data-campo="termos"]').textContent = numero(estado.parte2.termos);
    $('[data-campo="lexico"]').textContent = numero(estado.parte1.palavras);

    if (!estado.parte2.documentos) {
      avisar('parte2', `Nenhum .txt em ${estado.parte2.pasta}. ` +
        'Rode `python preparar_corpus.py` para baixar a base de exemplo.', true);
    }
  } catch (falha) {
    avisar('parte1', mensagemDeFalha(falha), true);
  }
}

const painelJaAberto = { parte1: true, parte2: false, metricas: false };

function abrirPainel(nome) {
  $$('.aba').forEach((aba) => {
    const ativa = aba.dataset.painel === nome;
    aba.classList.toggle('ativa', ativa);
    if (ativa) aba.setAttribute('aria-current', 'true');
    else aba.removeAttribute('aria-current');
  });

  $$('.painel').forEach((painel) => {
    const ativo = painel.id === nome;
    painel.classList.toggle('ativo', ativo);
    painel.hidden = !ativo;
  });

  // A primeira abertura já mostra um exemplo pronto, para que a aba nunca
  // apareça vazia esperando que alguém adivinhe o que digitar.
  if (!painelJaAberto[nome]) {
    painelJaAberto[nome] = true;
    if (nome === 'parte2') {
      $('#entrada-parte2').value = MODOS[modoAtual].exemplo;
      consultarDocumentos();
    }
    if (nome === 'metricas') carregarMetricas();
  }
}

function ligar() {
  $$('.aba').forEach((aba) => {
    aba.addEventListener('click', () => abrirPainel(aba.dataset.painel));
  });

  // --- Parte I ---
  const digitou = esperar(consultarPrefixo, ESPERA_DIGITACAO);
  $('#entrada-parte1').addEventListener('input', digitou);
  $('#forma-parte1').addEventListener('submit', (evento) => {
    evento.preventDefault();
    consultarPrefixo();
  });
  $('[data-acao="verificar"]').addEventListener('click', verificarPalavra);
  $('[data-acao="inserir"]').addEventListener('click', inserirPalavra);

  // --- Parte II ---
  $$('.modo').forEach((botao) => {
    botao.addEventListener('click', () => trocarModo(botao.dataset.modo));
  });
  $('#forma-parte2').addEventListener('submit', (evento) => {
    evento.preventDefault();
    consultarDocumentos();
  });

  // Só as modalidades indexadas consultam a cada tecla. O KMP varre o corpus
  // inteiro; dispará-lo a cada caractere mediria a digitação, não o algoritmo.
  const digitouParte2 = esperar(() => {
    if (MODOS[modoAtual].aoVivo) consultarDocumentos();
  }, ESPERA_DIGITACAO + 90);
  $('#entrada-parte2').addEventListener('input', digitouParte2);

  $('#recarregar-metricas').addEventListener('click', carregarMetricas);

  // --- primeira tela ---
  $('#nota-parte2').innerHTML = MODOS.palavra.nota;
  carregarEstado();
  $('#entrada-parte1').value = 'comp';
  consultarPrefixo();
}

document.addEventListener('DOMContentLoaded', ligar);
