/* ===========================================================================
   motor.js
   Quem responde às consultas da página.

   Há duas implementações possíveis e uma interface só:

       MotorLocal      chama o JavaScript de `web/algoritmos/`, aqui no
                       navegador. Funciona sem servidor, inclusive com a
                       página aberta direto de um pendrive.

       MotorServidor   chama as rotas JSON de `servidor.py`, e quem executa a
                       Trie, o índice e o KMP é o Python.

   As duas devolvem exatamente o mesmo formato -- as chaves são as das rotas de
   `servidor.py` --, então a interface não sabe nem precisa saber qual das duas
   respondeu. Trocar de motor durante a apresentação mostra as duas
   implementações rodando lado a lado, e `verificar_web.py` já garantiu, antes,
   que elas concordam.
   =========================================================================== */

'use strict';

window.UI = window.UI || {};

(function (UI) {

  /* ------------------------------------------------------------------ local */

  class MotorLocal {
    constructor(aplicacao) {
      this.aplicacao = aplicacao;
      this.nome = 'JavaScript';
      this.onde = 'no navegador';
    }

    async estado() { return this.aplicacao.estado(); }
    async autocompletar(prefixo, limite) { return this.aplicacao.autocompletar(prefixo, limite); }
    async buscarNoLexico(palavra) { return this.aplicacao.buscarNoLexico(palavra); }
    async inserirNoLexico(palavra) { return this.aplicacao.inserirNoLexico(palavra); }
    async buscarPalavra(consulta) { return this.aplicacao.mecanismo.buscarPalavra(consulta); }
    async buscarPrefixo(consulta, limite) {
      return this.aplicacao.mecanismo.buscarPrefixo(consulta, limite);
    }
    async buscarSequencia(consulta) {
      return this.aplicacao.mecanismo.buscarSequencia(consulta, true, 4);
    }
    async estatisticas() { return this.aplicacao.resumirEstatisticas(); }
    async documentos() {
      return { documentos: this.aplicacao.mecanismo.resumoDocumentos() };
    }
  }

  /* --------------------------------------------------------------- servidor */

  class MotorServidor {
    constructor() {
      this.nome = 'Python';
      this.onde = 'no servidor';
    }

    async _pedir(rota, parametros = {}) {
      const endereco = new URL(rota, window.location.origin);
      for (const [chave, valor] of Object.entries(parametros)) {
        if (valor !== undefined && valor !== null) endereco.searchParams.set(chave, valor);
      }
      const resposta = await fetch(endereco, { headers: { Accept: 'application/json' } });
      const dados = await resposta.json();
      if (!resposta.ok) throw new Error(dados.erro || `falha ${resposta.status}`);
      return dados;
    }

    async estado() { return this._pedir('/api/estado'); }
    async autocompletar(prefixo, limite) {
      return this._pedir('/api/parte1/prefixo', { q: prefixo, limite });
    }
    async buscarNoLexico(palavra) { return this._pedir('/api/parte1/palavra', { q: palavra }); }

    async inserirNoLexico(palavra) {
      const resposta = await fetch('/api/parte1/inserir', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ palavra }),
      });
      const dados = await resposta.json();
      if (!resposta.ok) throw new Error(dados.erro || `falha ${resposta.status}`);
      return dados;
    }

    async buscarPalavra(consulta) { return this._pedir('/api/parte2/palavra', { q: consulta }); }
    async buscarPrefixo(consulta, limite) {
      return this._pedir('/api/parte2/prefixo', { q: consulta, limite });
    }
    async buscarSequencia(consulta) {
      return this._pedir('/api/parte2/sequencia', { q: consulta });
    }
    async estatisticas() { return this._pedir('/api/estatisticas'); }
    async documentos() { return this._pedir('/api/parte2/documentos'); }
  }

  /**
   * O servidor está no ar?
   *
   * Aberta de um pendrive, a página roda em `file://` e nem tenta -- não há
   * origem para a qual pedir, e o navegador recusaria de qualquer forma.
   */
  async function servidorDisponivel() {
    if (window.location.protocol === 'file:') return false;
    try {
      const controle = new AbortController();
      const relogio = setTimeout(() => controle.abort(), 1200);
      const resposta = await fetch('/api/estado', { signal: controle.signal });
      clearTimeout(relogio);
      return resposta.ok;
    } catch (falha) {
      return false;
    }
  }

  UI.MotorLocal = MotorLocal;
  UI.MotorServidor = MotorServidor;
  UI.servidorDisponivel = servidorDisponivel;

})(window.UI);
