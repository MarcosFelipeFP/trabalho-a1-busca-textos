// Tipos de mecanismo.js, para a interface em TypeScript.

import type {
  EstadoSistema,
  RespostaAutocomplete,
  RespostaEstatisticas,
  RespostaInsercao,
  RespostaLexico,
  RespostaPalavra,
  RespostaPrefixo,
  RespostaSequencia,
} from '../motor/tipos';
import type { Estatisticas } from './estatisticas.js';
import type { IndiceInvertido } from './indice-invertido.js';
import type { Preprocessador } from './preprocessamento.js';
import type { Trie, TrieComprimida } from './trie.js';

export interface DocumentoDeEntrada {
  nome: string;
  bytes?: number;
  texto: string;
}

export interface EtapaDeConstrucao {
  fase: 'leitura' | 'trie' | 'trie-comprimida' | 'indice';
  nome?: string;
  posicao: number;
  total: number;
}

export class MecanismoBusca {
  constructor(opcoes?: { documentos?: DocumentoDeEntrada[]; stopwords?: string[]; usarStemming?: boolean });
  preprocessador: Preprocessador;
  indice: IndiceInvertido;
  trie: Trie;
  trieComprimida: TrieComprimida;
  estatisticas: Estatisticas;
  conteudo: Map<string, string>;
  conteudoMinusculo: Map<string, string>;
  tamanhos: Map<string, number>;
  vocabulario: Set<string>;
  frequencia: Map<string, number>;
  construirEmEtapas(): Generator<EtapaDeConstrucao, number, void>;
  construir(): number;
  buscarPalavra(consulta: string, ranquear?: boolean): RespostaPalavra;
  sugerirCorrecao(termo: string, limite?: number): [string, number, number][];
  buscarPrefixo(prefixo: string, limite?: number | null): RespostaPrefixo;
  buscarSequencia(sequencia: string, ignorarCaixa?: boolean, maxContextos?: number): RespostaSequencia;
  resumoDocumentos(): { documento: string; bytes: number; tokens: number }[];
}

export class Aplicacao {
  constructor(opcoes: { documentos: DocumentoDeEntrada[]; lexico: string[]; stopwords: string[]; usarStemming?: boolean });
  lexico: string[];
  trie: Trie;
  tempoTrie: number;
  mecanismo: MecanismoBusca;
  construirEmEtapas(): Generator<EtapaDeConstrucao, number, void>;
  estado(): EstadoSistema;
  autocompletar(prefixo: string, limite?: number): RespostaAutocomplete;
  buscarNoLexico(palavra: string): RespostaLexico;
  inserirNoLexico(palavra: string): RespostaInsercao;
  resumirEstatisticas(): RespostaEstatisticas;
}
