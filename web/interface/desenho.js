/* ===========================================================================
   desenho.js
   As peças visuais que várias telas reaproveitam: a régua de custo, o feixe de
   palavras, as barras de ranqueamento, os gráficos do laboratório e o desenho
   da Trie.

   Tudo em SVG escrito à mão. Não é purismo: a página precisa abrir de um
   pendrive, sem rede, e qualquer biblioteca de gráficos viria de um CDN que
   ali não existe.
   =========================================================================== */

'use strict';

window.UI = window.UI || {};

(function (UI) {

  const $ = (seletor, raiz = document) => raiz.querySelector(seletor);

  /* ---------------------------------------------------------- utilidades */

  function escapar(texto) {
    return String(texto)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  const numero = (valor) => Number(valor).toLocaleString('pt-BR');
  const plural = (n, um, varios) => (n === 1 ? um : varios);
  const porcentagem = (fracao, casas = 1) => `${(fracao * 100).toFixed(casas)}%`;

  /** O terminal escreve "us"; na tela cabe o símbolo de micro. */
  const micro = (texto) => String(texto).replace(/ us$/, ' µs');

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

  /**
   * Devolve o controle ao navegador para ele desenhar antes de continuar.
   *
   * `setTimeout` e não `requestAnimationFrame`: em aba oculta o navegador para
   * de chamar o rAF por completo, e uma construção em andamento ficaria
   * congelada até alguém voltar à aba. Com temporizador o pior caso é uma
   * pausa maior entre as etapas, nunca uma parada definitiva -- e em aba
   * visível ele ainda é mais rápido, porque não espera o próximo quadro.
   */
  const respirar = () => new Promise((seguir) => setTimeout(seguir, 0));

  /* =========================================================================
     RÉGUA DE CUSTO
     =========================================================================
     O instrumento central da página: uma escala logarítmica de 1 µs a 1 s em
     que toda consulta desta sessão deixa uma marca.

     Escala logarítmica porque a distância entre o que se quer comparar é de
     três ordens de grandeza. Em escala linear, as consultas indexadas ficariam
     todas empilhadas contra o zero e a demonstração se perderia; em escala
     logarítmica, cada casa decimal ocupa a mesma largura e o salto do índice
     para o KMP vira distância visível.

     As marcas antigas não somem, só esmaecem. Ao fim de uma demonstração, a
     régua mostra dois aglomerados -- âmbar e ciano à esquerda, brasa à direita
     -- e essa imagem é o resultado do trabalho.
     ========================================================================= */

  const DECADAS = [
    [1e-6, '1 µs'], [1e-5, '10 µs'], [1e-4, '100 µs'],
    [1e-3, '1 ms'], [1e-2, '10 ms'], [1e-1, '100 ms'], [1, '1 s'],
  ];

  const Regua = {
    marcas: [],
    limite: 26,

    montar() {
      const escala = $('#regua-escala');
      if (!escala) return;
      escala.innerHTML = DECADAS.map(([segundos, rotulo]) =>
        `<span class="regua-tique" style="left:${(this.posicao(segundos) * 100).toFixed(2)}%">
           ${escapar(rotulo)}</span>`).join('');

      const limpar = $('#limpar-regua');
      if (limpar) limpar.addEventListener('click', () => this.limpar());
    },

    /** Fração de 0 a 1 na escala logarítmica de seis décadas. */
    posicao(segundos) {
      const micros = Math.max(segundos * 1e6, 1);
      return Math.min(1, Math.max(0, Math.log10(micros) / 6));
    },

    /**
     * Registra uma medição.
     *
     * `via` escolhe a cor, e cada cor quer dizer uma coisa só: âmbar para o
     * índice invertido, ciano para a Trie, brasa para a varredura linear.
     */
    marcar({ segundos, rotulo, via = 'indice', repeticoes = 1 }) {
      this.marcas.push({ segundos, rotulo, via, repeticoes });
      if (this.marcas.length > this.limite) this.marcas.shift();
      this.desenhar();
    },

    limpar() {
      this.marcas = [];
      this.desenhar();
    },

    desenhar() {
      const alvo = $('#regua-marcas');
      if (!alvo) return;

      const ultima = this.marcas.length - 1;
      alvo.innerHTML = this.marcas.map((marca, indice) => {
        const posicao = (this.posicao(marca.segundos) * 100).toFixed(2);
        const tempo = window.A1.formatarDuracao(marca.segundos);
        const nota = marca.repeticoes > 1
          ? `${marca.rotulo} · ${tempo} · mediana de ${numero(marca.repeticoes)} execuções`
          : `${marca.rotulo} · ${tempo}`;
        return `<span class="regua-marca via-${marca.via}${indice === ultima ? ' nova' : ''}"
                      style="left:${posicao}%" title="${escapar(nota)}">
                  <span class="valor">${escapar(tempo)}</span>
                  <span class="haste"></span>
                  <span class="cabeca"></span>
                </span>`;
      }).join('');
    },
  };

  /* =========================================================================
     FEIXE DE PALAVRAS
     ========================================================================= */

  /**
   * Desenha a lista com o prefixo compartilhado escrito uma vez só, como a
   * Trie o armazena: tinta cheia na primeira linha, eco nas seguintes, e o
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

  /* =========================================================================
     BARRAS DE RANQUEAMENTO
     ========================================================================= */

  function barras(ranking, frequencias, { clicavel = false, cor = '' } = {}) {
    const maior = Math.max(...ranking.map(([, nota]) => nota), 1e-9);

    return `<ul class="postagens">${ranking.map(([documento, nota]) => {
      const largura = Math.max(2, (nota / maior) * 100);
      const vezes = frequencias && frequencias[documento];
      const nome = clicavel
        ? `<button type="button" class="arquivo" data-documento="${escapar(documento)}">${escapar(documento)}</button>`
        : `<span class="arquivo">${escapar(documento)}</span>`;
      return `<li class="postagem">
        ${nome}
        <span class="barra-nota ${cor}" title="BM25 ${nota.toFixed(3)}"><i style="width:${largura.toFixed(1)}%"></i></span>
        <span class="numero">${nota.toFixed(3)}</span>
        <span class="vezes">${vezes ? `${numero(vezes)}×` : ''}</span>
      </li>`;
    }).join('')}</ul>`;
  }

  /* =========================================================================
     GRÁFICOS
     ========================================================================= */

  const CORES = ['a', 'b', 'c'];

  /**
   * Gráfico de linhas com eixos rotulados, opcionalmente logarítmico em y.
   *
   * `series` é uma lista de { nome, pontos: [[x, y], ...] }. A ordem define a
   * cor: âmbar, ciano, brasa -- as mesmas três da régua, pelos mesmos motivos.
   */
  function graficoLinhas({ series, rotuloX = '', rotuloY = '', logaritmico = false,
                           largura = 620, altura = 240, formatarY = null }) {
    // O topo é generoso de propósito: é onde o rótulo do eixo y fica, e
    // encostá-lo na primeira linha de grade tornaria os dois ilegíveis.
    const margem = { esquerda: 58, direita: 16, topo: 26, baixo: 34 };
    const larguraUtil = largura - margem.esquerda - margem.direita;
    const alturaUtil = altura - margem.topo - margem.baixo;

    const todosX = series.flatMap((s) => s.pontos.map((p) => p[0]));
    const todosY = series.flatMap((s) => s.pontos.map((p) => p[1]));
    const minX = Math.min(...todosX);
    const maxX = Math.max(...todosX);
    const maxY = Math.max(...todosY);
    const minY = logaritmico ? Math.max(Math.min(...todosY), 1e-9) : 0;

    const escalaX = (x) => margem.esquerda +
      (maxX === minX ? larguraUtil / 2 : ((x - minX) / (maxX - minX)) * larguraUtil);

    const escalaY = (y) => {
      if (!logaritmico) {
        return margem.topo + alturaUtil - (maxY ? (y / maxY) * alturaUtil : 0);
      }
      const valor = Math.max(y, minY);
      const faixa = Math.log10(maxY) - Math.log10(minY) || 1;
      return margem.topo + alturaUtil -
        ((Math.log10(valor) - Math.log10(minY)) / faixa) * alturaUtil;
    };

    const formatar = formatarY || ((v) => (v >= 1000 ? numero(Math.round(v)) : String(Number(v.toFixed(2)))));

    // Cinco linhas de grade: o suficiente para ler o valor, pouco o bastante
    // para não competir com os dados.
    const marcasY = [];
    for (let i = 0; i <= 4; i += 1) {
      const valor = logaritmico
        ? Math.pow(10, Math.log10(minY) + (i / 4) * (Math.log10(maxY) - Math.log10(minY)))
        : (i / 4) * maxY;
      marcasY.push(valor);
    }

    const grade = marcasY.map((valor) => {
      const y = escalaY(valor).toFixed(1);
      return `<line class="grade-linha" x1="${margem.esquerda}" x2="${largura - margem.direita}" y1="${y}" y2="${y}"/>
              <text x="${margem.esquerda - 7}" y="${y}" text-anchor="end" dominant-baseline="middle">${escapar(formatar(valor))}</text>`;
    }).join('');

    const marcasX = [minX, (minX + maxX) / 2, maxX].map((valor) => {
      const x = escalaX(valor).toFixed(1);
      return `<text x="${x}" y="${altura - margem.baixo + 16}" text-anchor="middle">${escapar(numero(Math.round(valor)))}</text>`;
    }).join('');

    const traços = series.map((serie, indice) => {
      const cor = CORES[indice % CORES.length];
      const caminho = serie.pontos.map((ponto, posicao) =>
        `${posicao ? 'L' : 'M'}${escalaX(ponto[0]).toFixed(1)},${escalaY(ponto[1]).toFixed(1)}`).join('');
      const pontos = serie.pontos.map((ponto) =>
        `<circle class="ponto-${cor}" cx="${escalaX(ponto[0]).toFixed(1)}" cy="${escalaY(ponto[1]).toFixed(1)}" r="2.6"/>`).join('');
      return `<path class="serie-${cor}" d="${caminho}"/>${pontos}`;
    }).join('');

    return `<div class="grafico">
      ${legenda(series)}
      <svg viewBox="0 0 ${largura} ${altura}" width="${largura}" height="${altura}" role="img"
           aria-label="${escapar(rotuloY)} por ${escapar(rotuloX)}">
        ${grade}
        <line class="eixo" x1="${margem.esquerda}" x2="${margem.esquerda}" y1="${margem.topo}" y2="${altura - margem.baixo}"/>
        <line class="eixo" x1="${margem.esquerda}" x2="${largura - margem.direita}" y1="${altura - margem.baixo}" y2="${altura - margem.baixo}"/>
        ${traços}
        ${marcasX}
        <text x="${largura - margem.direita}" y="${altura - 4}" text-anchor="end">${escapar(rotuloX)}</text>
        <text x="2" y="11">${escapar(rotuloY)}</text>
      </svg>
    </div>`;
  }

  /** Barras horizontais rotuladas -- para comparações de poucos itens. */
  function graficoBarras({ itens, formatar = (v) => numero(Math.round(v)), largura = 620 }) {
    const alturaBarra = 26;
    const altura = itens.length * alturaBarra + 12;
    const rotuloLargura = 168;
    const maior = Math.max(...itens.map((item) => item.valor), 1e-9);

    const corpo = itens.map((item, indice) => {
      const y = indice * alturaBarra + 6;
      const cor = item.cor || CORES[indice % CORES.length];
      const comprimento = Math.max(2, (item.valor / maior) * (largura - rotuloLargura - 90));
      return `
        <text x="${rotuloLargura - 10}" y="${y + alturaBarra / 2}" text-anchor="end" dominant-baseline="middle">${escapar(item.nome)}</text>
        <rect class="barra-${cor}" x="${rotuloLargura}" y="${y + 5}" width="${comprimento.toFixed(1)}" height="${alturaBarra - 14}" rx="1"/>
        <text x="${rotuloLargura + comprimento + 8}" y="${y + alturaBarra / 2}" dominant-baseline="middle">${escapar(formatar(item.valor))}</text>`;
    }).join('');

    return `<div class="grafico">
      <svg viewBox="0 0 ${largura} ${altura}" width="${largura}" height="${altura}" role="img">
        ${corpo}
      </svg>
    </div>`;
  }

  function legenda(series) {
    if (series.length < 2) return '';
    const cores = { a: 'var(--ambar)', b: 'var(--ciano)', c: 'var(--brasa)' };
    return `<p class="chaves">${series.map((serie, indice) =>
      `<span><i style="background:${cores[CORES[indice % CORES.length]]}"></i>${escapar(serie.nome)}</span>`).join('')}</p>`;
  }
  /* =========================================================================
     A TRIE DESENHADA
     =========================================================================
     Mostrar a estrutura é mais honesto do que descrevê-la. O prefixo digitado
     aparece como UM caminho -- é assim que a Trie o guarda, uma vez só para
     todas as palavras que o compartilham --, e o que se ramifica dali é o `p`
     do O(m + p): o que a consulta ainda precisa varrer depois de descer.

     ---------------------------------------------------------------------------
     O que entra no desenho
     ---------------------------------------------------------------------------
     Não a subárvore inteira: "co" alcança milhares de nós, e desenhar todos
     produziria uma mancha. Desenha-se a Trie INDUZIDA pelas primeiras palavras
     da resposta -- os caminhos exatos que elas percorrem, com as bifurcações
     onde elas se separam.

     Essa escolha preserva o que o diagrama tem de dizer (caminhos
     compartilhados, pontos de ramificação, nós que terminam palavra) e mantém
     a altura igual ao número de palavras mostradas, não ao tamanho do léxico.
     Onde a árvore real continua além do desenho, um ramo pontilhado diz quantas
     palavras ficaram de fora -- esconder sem avisar seria mentir sobre o
     tamanho da estrutura.
     ========================================================================= */

  const PALAVRAS_DESENHADAS = 8;

  /** Quantas palavras terminam na subárvore de um nó. */
  function palavrasAbaixo(raiz) {
    let total = 0;
    const pilha = [raiz];
    while (pilha.length) {
      const atual = pilha.pop();
      if (atual.fimDePalavra) total += 1;
      for (const filho of atual.filhos.values()) pilha.push(filho);
    }
    return total;
  }

  /**
   * Monta os nós do desenho seguindo, uma a uma, as chaves informadas.
   *
   * Cada nó visitado entra uma única vez, indexado pelo caminho relativo ao
   * prefixo -- é justamente isso que faz duas palavras com começo igual
   * compartilharem o mesmo traço na tela, como compartilham na memória.
   */
  function colherCaminhos(raizNo, chaves) {
    const nos = [];
    const porCaminho = new Map();

    const criar = (no, pai, caractere, profundidade) => {
      const registro = {
        no, pai, caractere, profundidade,
        filhos: [], indice: nos.length, corte: false, abaixo: 0,
      };
      nos.push(registro);
      if (pai !== null) nos[pai].filhos.push(registro.indice);
      return registro;
    };

    const raiz = criar(raizNo, null, '', 0);
    porCaminho.set('', raiz);

    for (const chave of chaves) {
      let atual = raiz;
      let caminho = '';
      for (const caractere of chave) {
        const proximo = atual.no.filhos.get(caractere);
        if (proximo === undefined) break;
        caminho += caractere;

        let registro = porCaminho.get(caminho);
        if (registro === undefined) {
          registro = criar(proximo, atual.indice, caractere, caminho.length);
          porCaminho.set(caminho, registro);
        }
        atual = registro;
      }
    }

    // Onde a árvore real segue além do desenho, um ramo de corte com a conta.
    let escondidas = 0;
    for (const registro of [...nos]) {
      const desenhados = new Set(registro.filhos.map((indice) => nos[indice].caractere));
      let fora = 0;
      for (const [caractere, filho] of registro.no.filhos) {
        if (!desenhados.has(caractere)) fora += palavrasAbaixo(filho);
      }
      if (!fora) continue;

      escondidas += fora;
      const corte = {
        no: null, pai: registro.indice, caractere: '',
        profundidade: registro.profundidade + 1,
        filhos: [], indice: nos.length, corte: true, abaixo: fora,
      };
      nos.push(corte);
      registro.filhos.push(corte.indice);
    }

    return { nos, escondidas };
  }

  /**
   * Desenha o tronco do prefixo e os caminhos que saem dele.
   *
   * O layout é o clássico de árvore: a profundidade vira coluna, as folhas
   * ocupam linhas consecutivas na ordem em que aparecem, e cada nó interno se
   * alinha ao meio dos seus filhos -- o que garante que nenhuma aresta cruze
   * outra.
   */
  function desenharArvore(trie, prefixo, { largura = 520 } = {}) {
    const chave = window.A1.normalizar(prefixo);

    if (!chave) {
      return '<p class="vazio">Digite um prefixo para ver o caminho que ele percorre.</p>';
    }

    const raizNo = trie.descer(chave);
    if (raizNo === null) {
      return `<p class="vazio">Nenhum caminho na Trie começa com
        <b>${escapar(prefixo)}</b> — a descida para antes do fim do prefixo.</p>`;
    }

    const palavras = trie.buscarPrefixo(prefixo, PALAVRAS_DESENHADAS);
    const chaves = palavras.map((palavra) =>
      window.A1.normalizar(palavra).slice(chave.length));
    const { nos, escondidas } = colherCaminhos(raizNo, chaves);

    // --- posiciona: x pela profundidade, y pela ordem das folhas ---
    const passoY = 24;
    const passoX = 22;
    let proximaLinha = 0;

    const posicionar = (indice) => {
      const registro = nos[indice];
      if (!registro.filhos.length) {
        registro.y = proximaLinha * passoY;
        proximaLinha += 1;
        return registro.y;
      }
      const alturas = registro.filhos.map(posicionar);
      registro.y = (Math.min(...alturas) + Math.max(...alturas)) / 2;
      return registro.y;
    };
    posicionar(0);

    // O tronco: até oito letras viram nós individuais; mais que isso, um
    // segmento só rotulado com o prefixo inteiro -- porque o ponto é que ele é
    // UM caminho, não oito.
    const troncoDetalhado = chave.length <= 8;
    const larguraTronco = troncoDetalhado ? chave.length * passoX : 96;
    const esquerda = 14;
    const inicioSubarvore = esquerda + larguraTronco;
    const deslocamentoY = 20;
    const alturaRaiz = nos[0].y + deslocamentoY;

    const partes = [];

    // --- tronco ---
    if (troncoDetalhado) {
      for (let i = 0; i < chave.length; i += 1) {
        const x0 = esquerda + i * passoX;
        partes.push(`<line class="aresta aresta-tronco" x1="${x0}" y1="${alturaRaiz}" x2="${x0 + passoX}" y2="${alturaRaiz}"/>`);
        partes.push(`<text class="rotulo rotulo-tronco" x="${x0 + passoX / 2}" y="${alturaRaiz - 7}" text-anchor="middle">${escapar(chave[i])}</text>`);
        partes.push(`<circle class="no no-tronco" cx="${x0}" cy="${alturaRaiz}" r="3"/>`);
      }
    } else {
      partes.push(`<line class="aresta aresta-tronco" x1="${esquerda}" y1="${alturaRaiz}" x2="${inicioSubarvore}" y2="${alturaRaiz}"/>`);
      partes.push(`<text class="rotulo rotulo-tronco" x="${esquerda + larguraTronco / 2}" y="${alturaRaiz - 7}" text-anchor="middle">${escapar(chave)}</text>`);
      partes.push(`<circle class="no no-tronco" cx="${esquerda}" cy="${alturaRaiz}" r="3"/>`);
    }

    // --- caminhos ---
    // As etiquetas saem em uma passada separada, no fim. O SVG pinta na ordem
    // do documento, e a aresta de um nó mais fundo passaria por cima do nome
    // escrito num nó anterior; desenhadas por último, e com auréola da cor da
    // placa, elas abrem espaço no traço em vez de brigar com ele.
    const etiquetas = [];
    let maiorX = inicioSubarvore;
    for (const registro of nos) {
      const x = inicioSubarvore + registro.profundidade * passoX;
      const y = registro.y + deslocamentoY;
      maiorX = Math.max(maiorX, x);

      if (registro.pai !== null) {
        const pai = nos[registro.pai];
        const xPai = inicioSubarvore + pai.profundidade * passoX;
        const yPai = pai.y + deslocamentoY;
        // Cotovelo em vez de diagonal: a leitura fica mais próxima de um
        // diagrama de estrutura de dados e menos de um gráfico de linhas.
        partes.push(`<path class="aresta" d="M${xPai},${yPai} H${xPai + passoX / 2} V${y} H${x}"/>`);
        if (registro.caractere) {
          partes.push(`<text class="rotulo" x="${x - passoX / 2 + 1}" y="${y - 5}" text-anchor="middle">${escapar(registro.caractere)}</text>`);
        }
      }

      if (registro.corte) {
        etiquetas.push(`<text class="corte" x="${x - passoX / 2}" y="${y + 3.5}">⋯ mais ${numero(registro.abaixo)} ${plural(registro.abaixo, 'palavra', 'palavras')}</text>`);
        continue;
      }

      const ehPalavra = registro.no.fimDePalavra;
      const classe = ['no'];
      if (registro.profundidade === 0) classe.push('no-tronco');
      if (ehPalavra) classe.push('no-palavra');
      partes.push(`<circle class="${classe.join(' ')}" cx="${x}" cy="${y}" r="${ehPalavra ? 4.2 : 3}"/>`);

      if (ehPalavra) {
        const forma = Array.from(registro.no.formas).sort(window.A1.ordemDeTexto)[0];
        // Um nó pode terminar uma palavra E continuar em outras ("computacional"
        // segue para "computacionais"). Nesse caso a etiqueta sobe, para não
        // cair em cima da aresta que sai dali.
        const continua = registro.filhos.length > 0;
        etiquetas.push(`<text class="folha" x="${x + (continua ? 6 : 9)}"
          y="${(continua ? y - 8 : y + 3.5).toFixed(1)}">${escapar(forma)}</text>`);
      }
    }

    partes.push(...etiquetas);

    const alturaTotal = proximaLinha * passoY + deslocamentoY + 14;
    if (escondidas) {
      partes.push(`<text class="corte" x="${esquerda}" y="${alturaTotal - 2}">
        o desenho mostra ${numero(palavras.length)} ${plural(palavras.length, 'palavra', 'palavras')};
        outras ${numero(escondidas)} continuam na árvore</text>`);
    }

    const larguraTotal = Math.max(largura, maiorX + 190);

    return `<svg viewBox="0 0 ${larguraTotal} ${alturaTotal + 6}"
                 width="${larguraTotal}" height="${alturaTotal + 6}">
      ${partes.join('\n      ')}
    </svg>`;
  }

  UI.$ = $;
  UI.escapar = escapar;
  UI.numero = numero;
  UI.plural = plural;
  UI.porcentagem = porcentagem;
  UI.micro = micro;
  UI.realcar = realcar;
  UI.esperar = esperar;
  UI.respirar = respirar;
  UI.Regua = Regua;
  UI.feixe = feixe;
  UI.barras = barras;
  UI.graficoLinhas = graficoLinhas;
  UI.graficoBarras = graficoBarras;
  UI.desenharArvore = desenharArvore;

})(window.UI);
