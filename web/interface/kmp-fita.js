/* ===========================================================================
   kmp-fita.js
   O KMP passo a passo, sobre uma fita de células de caractere.

   ---------------------------------------------------------------------------
   Por que vale desenhar
   ---------------------------------------------------------------------------
   O ponto do KMP é uma afirmação que a prosa não consegue tornar evidente: o
   ponteiro do texto NUNCA volta atrás. Quem lê o pseudocódigo tem de confiar;
   quem vê a fita percebe que o cursor do texto só anda para a direita, e que
   quando o casamento falha é o PADRÃO que escorrega por baixo dele.

   A função de falha aparece embaixo, e a célula consultada acende no momento
   exato em que o deslize a usa -- que é onde a tabela deixa de ser um vetor de
   números e vira o motivo pelo qual não é preciso voltar.

   O traçado vem de `A1.tracarKmp`, que é o mesmo algoritmo de `A1.buscarKmp`
   com um registro de cada comparação. A busca de verdade, sobre o corpus
   inteiro, continua rodando pelo caminho sem instrumentação.
   =========================================================================== */

'use strict';

window.UI = window.UI || {};

(function (UI) {

  const TRECHO_MAXIMO = 120;     // caracteres da fita
  const INTERVALO = 420;         // ms entre passos na reprodução automática

  class FitaKMP {
    constructor(elemento) {
      this.elemento = elemento;
      this.passo = 0;
      this.tocando = false;
      this.relogio = null;
    }

    /**
     * Escolhe o trecho, traça o algoritmo e desenha.
     *
     * O trecho começa um pouco antes da primeira ocorrência, para que a
     * reprodução mostre falhas antes de chegar ao casamento -- é nas falhas
     * que o algoritmo faz o que tem de interessante.
     */
    montar(texto, padrao, { rotulo = '' } = {}) {
      this.padrao = padrao;
      this.rotulo = rotulo;

      const posicao = texto.toLowerCase().indexOf(padrao.toLowerCase());
      const inicio = posicao >= 0
        ? Math.max(0, posicao - Math.floor(TRECHO_MAXIMO * 0.45))
        : 0;

      this.trecho = texto.slice(inicio, inicio + TRECHO_MAXIMO)
        .replace(/[\r\n\t]/g, ' ');
      this.deslocamentoOriginal = inicio;

      const traco = window.A1.tracarKmp(this.trecho.toLowerCase(), padrao.toLowerCase());
      this.passos = traco.passos;
      this.falha = traco.falha;
      this.ocorrencias = traco.ocorrencias;
      this.passo = 0;
      this.parar();

      this.elemento.innerHTML = this.esqueleto();
      this.ligar();
      this.desenhar();
    }

    esqueleto() {
      const { escapar } = UI;
      return `
        <div class="fita-controles">
          <button type="button" class="botao" data-acao="reiniciar" title="Volta ao início">⏮</button>
          <button type="button" class="botao" data-acao="voltar" title="Um passo atrás">◀</button>
          <button type="button" class="botao primario" data-acao="tocar">Reproduzir</button>
          <button type="button" class="botao" data-acao="avancar" title="Um passo à frente">▶</button>
          <span class="fita-leitura">
            comparação <b data-campo="passo">0</b> de ${UI.numero(this.passos.length)}
            · padrão <b>${escapar(this.padrao)}</b>
          </span>
        </div>
        <div class="fita-pista" data-pista>
          <div class="fita-regua" data-regua></div>
          <div class="fita-linha texto" data-texto></div>
          <div class="fita-linha padrao" data-padrao></div>
        </div>
        <div class="falha-tabela" data-falha></div>
        <p class="fita-nota" data-nota></p>`;
    }

    ligar() {
      const acoes = {
        reiniciar: () => { this.parar(); this.irPara(0); },
        voltar: () => { this.parar(); this.irPara(this.passo - 1); },
        avancar: () => { this.parar(); this.irPara(this.passo + 1); },
        tocar: () => (this.tocando ? this.parar() : this.tocar()),
      };

      for (const botao of this.elemento.querySelectorAll('[data-acao]')) {
        botao.addEventListener('click', () => acoes[botao.dataset.acao]());
      }
    }

    /* ------------------------------------------------------------ controle */

    tocar() {
      if (this.passo >= this.passos.length - 1) this.passo = 0;
      this.tocando = true;
      this.elemento.querySelector('[data-acao="tocar"]').textContent = 'Pausar';
      this.relogio = setInterval(() => {
        if (this.passo >= this.passos.length - 1) return this.parar();
        this.irPara(this.passo + 1);
      }, INTERVALO);
    }

    parar() {
      this.tocando = false;
      if (this.relogio) clearInterval(this.relogio);
      this.relogio = null;
      const botao = this.elemento.querySelector('[data-acao="tocar"]');
      if (botao) botao.textContent = 'Reproduzir';
    }

    irPara(passo) {
      this.passo = Math.max(0, Math.min(this.passos.length - 1, passo));
      this.desenhar();
    }

    /* ------------------------------------------------------------- desenho */

    desenhar() {
      if (!this.passos.length) {
        this.elemento.querySelector('[data-nota]').textContent =
          'O padrão é maior que o trecho: não há o que comparar.';
        return;
      }

      const atual = this.passos[this.passo];
      const { escapar } = UI;
      const celula = (conteudo, classes) =>
        `<span class="celula ${classes.join(' ')}">${escapar(conteudo === ' ' ? '·' : conteudo)}</span>`;

      // Posições já confirmadas como ocorrência até este ponto da reprodução.
      const achadas = new Set();
      for (let k = 0; k <= this.passo; k += 1) {
        if (this.passos[k].evento === 'casa-completo') {
          const inicio = this.passos[k].deslocamento;
          for (let d = 0; d < this.padrao.length; d += 1) achadas.add(inicio + d);
        }
      }

      // --- régua de posições: marca a dezena, para dar noção de deslocamento ---
      const regua = Array.from(this.trecho, (_, indice) =>
        `<span class="celula">${indice % 10 === 0 ? String((indice / 10) % 10) : '·'}</span>`).join('');

      // --- linha do texto ---
      const linhaTexto = Array.from(this.trecho, (caractere, indice) => {
        const classes = [];
        if (indice === atual.i) classes.push('cursor');
        else if (achadas.has(indice)) classes.push('achado');
        else if (indice < atual.i) classes.push('lida');
        return celula(caractere, classes);
      }).join('');

      // --- linha do padrão, alinhada ao deslocamento atual ---
      const deslocamento = Math.max(0, atual.i - atual.j);
      const vazias = '<span class="celula"> </span>'.repeat(deslocamento);
      const linhaPadrao = vazias + Array.from(this.padrao, (caractere, indice) => {
        const classes = [];
        if (indice < atual.j) classes.push('casado');
        else if (indice === atual.j) classes.push(atual.casou ? 'cursor' : 'falhou');
        return celula(caractere, classes);
      }).join('');

      // --- tabela de falha, com a célula consultada acesa ---
      const consultada = atual.evento === 'desliza' ? atual.de - 1 : -1;
      const tabela = this.falha.map((valor, indice) =>
        `<div class="${indice === consultada ? 'atual' : ''}">
           <b>${escapar(this.padrao[indice])}</b>${valor}</div>`).join('');

      const alvo = (seletor) => this.elemento.querySelector(seletor);
      alvo('[data-regua]').innerHTML = regua;
      alvo('[data-texto]').innerHTML = linhaTexto;
      alvo('[data-padrao]').innerHTML = linhaPadrao;
      alvo('[data-falha]').innerHTML = tabela;
      alvo('[data-campo="passo"]').textContent = UI.numero(this.passo + 1);
      alvo('[data-nota]').innerHTML = this.narrar(atual);

      this.acompanhar(deslocamento);
    }

    /** Mantém o cursor visível quando a fita é mais larga que a tela. */
    acompanhar(deslocamento) {
      const pista = this.elemento.querySelector('[data-pista]');
      const celula = pista.querySelector('.celula');
      if (!pista || !celula) return;
      const largura = celula.getBoundingClientRect().width || 8;
      const alvo = deslocamento * largura - pista.clientWidth / 2;
      pista.scrollLeft = Math.max(0, alvo);
    }

    /** Uma frase por passo, dizendo o que o algoritmo acabou de decidir. */
    narrar(atual) {
      const { escapar } = UI;
      const letra = (valor) => `<b>${escapar(valor === ' ' ? 'espaço' : valor)}</b>`;
      const doTexto = this.trecho[atual.i];
      const doPadrao = this.padrao[atual.j];

      if (atual.evento === 'casa-completo') {
        return `Ocorrência completa na posição
          <b>${UI.numero(this.deslocamentoOriginal + atual.deslocamento)}</b> do documento.
          O padrão não recomeça do zero: continua de <b>falha[${this.padrao.length - 1}]
          = ${this.falha[this.padrao.length - 1]}</b>, porque ocorrências podem se sobrepor.`;
      }

      if (atual.evento === 'desliza') {
        return `<span class="desliza">Desliza.</span> Os ${atual.de} caracteres já casados
          são conhecidos — são os ${atual.de} primeiros do padrão. <b>falha[${atual.de - 1}]
          = ${atual.para}</b> diz que os ${atual.para} primeiros ainda servem, então
          <b>j vai de ${atual.de} para ${atual.para}</b> e <b>i não se move</b>.`;
      }

      if (atual.evento === 'avanca') {
        return `Falhou já no primeiro caractere do padrão, com <b>j = 0</b>: não há
          nada aproveitado para deslizar. O texto anda uma posição.`;
      }

      if (atual.casou) {
        return `${letra(doTexto)} do texto casa com ${letra(doPadrao)} do padrão.
          <b>i</b> e <b>j</b> avançam juntos — ${UI.numero(atual.j + 1)} de
          ${UI.numero(this.padrao.length)} caracteres casados.`;
      }

      return `<span class="falha">Falha.</span> ${letra(doTexto)} do texto (posição
        ${UI.numero(atual.i)}) não casa com ${letra(doPadrao)} do padrão (posição
        ${atual.j}). O próximo passo consulta a função de falha.`;
    }
  }

  UI.FitaKMP = FitaKMP;

})(window.UI);
