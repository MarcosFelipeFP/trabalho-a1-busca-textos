/*
 * Quem responde às consultas.
 *
 *   MotorLocal     os algoritmos de src/algoritmos/, rodando no navegador.
 *                  Funciona sem servidor, com a página aberta de um pendrive.
 *   MotorServidor  as rotas JSON de servidor.py: quem executa é o Python.
 *
 * As duas respostas têm o mesmo formato, e `verificar_web.py` garante que o
 * conteúdo também é o mesmo. Trocar de motor na apresentação mostra as duas
 * implementações respondendo igual.
 */
import type { Aplicacao } from '../algoritmos/mecanismo.js';
import type {
  EstadoSistema,
  Motor,
  RespostaAutocomplete,
  RespostaEstatisticas,
  RespostaInsercao,
  RespostaLexico,
  RespostaPalavra,
  RespostaPrefixo,
  RespostaSequencia,
} from './tipos';

export const LIMITE_AUTOCOMPLETE = 60;
export const LIMITE_PREFIXO = 50;

export class MotorLocal implements Motor {
  readonly nome = 'JavaScript' as const;

  constructor(readonly aplicacao: Aplicacao) {}

  async estado(): Promise<EstadoSistema> {
    return this.aplicacao.estado();
  }

  async autocompletar(prefixo: string, limite = LIMITE_AUTOCOMPLETE): Promise<RespostaAutocomplete> {
    return this.aplicacao.autocompletar(prefixo, limite);
  }

  async buscarNoLexico(palavra: string): Promise<RespostaLexico> {
    return this.aplicacao.buscarNoLexico(palavra);
  }

  async inserirNoLexico(palavra: string): Promise<RespostaInsercao> {
    return this.aplicacao.inserirNoLexico(palavra);
  }

  async buscarPalavra(consulta: string): Promise<RespostaPalavra> {
    return this.aplicacao.mecanismo.buscarPalavra(consulta);
  }

  async buscarPrefixo(prefixo: string, limite = LIMITE_PREFIXO): Promise<RespostaPrefixo> {
    return this.aplicacao.mecanismo.buscarPrefixo(prefixo, limite);
  }

  async buscarSequencia(sequencia: string): Promise<RespostaSequencia> {
    return this.aplicacao.mecanismo.buscarSequencia(sequencia, true, 4);
  }

  async estatisticas(): Promise<RespostaEstatisticas> {
    return this.aplicacao.resumirEstatisticas();
  }
}

export class MotorServidor implements Motor {
  readonly nome = 'Python' as const;

  private async pedir<T>(rota: string, parametros: Record<string, string | number> = {}): Promise<T> {
    const endereco = new URL(rota, window.location.origin);
    for (const [chave, valor] of Object.entries(parametros)) {
      endereco.searchParams.set(chave, String(valor));
    }
    const resposta = await fetch(endereco, { headers: { Accept: 'application/json' } });
    const dados = await resposta.json();
    if (!resposta.ok) throw new Error(dados.erro || `o servidor respondeu ${resposta.status}`);
    return dados as T;
  }

  estado() {
    return this.pedir<EstadoSistema>('/api/estado');
  }

  autocompletar(prefixo: string, limite = LIMITE_AUTOCOMPLETE) {
    return this.pedir<RespostaAutocomplete>('/api/parte1/prefixo', { q: prefixo, limite });
  }

  buscarNoLexico(palavra: string) {
    return this.pedir<RespostaLexico>('/api/parte1/palavra', { q: palavra });
  }

  async inserirNoLexico(palavra: string): Promise<RespostaInsercao> {
    const resposta = await fetch('/api/parte1/inserir', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ palavra }),
    });
    const dados = await resposta.json();
    if (!resposta.ok) throw new Error(dados.erro || `o servidor respondeu ${resposta.status}`);
    return dados as RespostaInsercao;
  }

  buscarPalavra(consulta: string) {
    return this.pedir<RespostaPalavra>('/api/parte2/palavra', { q: consulta });
  }

  buscarPrefixo(prefixo: string, limite = LIMITE_PREFIXO) {
    return this.pedir<RespostaPrefixo>('/api/parte2/prefixo', { q: prefixo, limite });
  }

  buscarSequencia(sequencia: string) {
    return this.pedir<RespostaSequencia>('/api/parte2/sequencia', { q: sequencia });
  }

  estatisticas() {
    return this.pedir<RespostaEstatisticas>('/api/estatisticas');
  }
}

/**
 * O servidor Python está no ar?
 *
 * Aberta de um pendrive, a página roda em file:// e nem tenta: não há origem
 * para onde pedir.
 */
export async function servidorDisponivel(): Promise<boolean> {
  if (window.location.protocol === 'file:') return false;
  try {
    const controle = new AbortController();
    const relogio = setTimeout(() => controle.abort(), 1200);
    const resposta = await fetch('/api/estado', { signal: controle.signal });
    clearTimeout(relogio);
    return resposta.ok;
  } catch {
    return false;
  }
}
