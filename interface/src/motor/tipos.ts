/*
 * O formato das respostas. As chaves com sublinhado (`total_disponivel`,
 * `por_termo`) são as mesmas das rotas JSON do `servidor.py`: é isso que deixa
 * a interface trocar de motor, Python ou JavaScript, sem adaptação no meio.
 */

/** [palavra, distância de edição, peso] */
export type Aproximada = [string, number, number];

export interface Medida {
  tempo: number;
  repeticoes?: number;
}

export interface EstadoSistema {
  parte1: {
    lexico: string;
    palavras: number;
    nos: number;
    altura: number;
    tempo_construcao: number;
  };
  parte2: {
    pasta: string;
    documentos: number;
    palavras: number;
    palavras_brutas: number;
    termos: number;
    radicais: number;
    postagens: number;
    stemming: boolean;
    tempo_construcao: number;
  };
}

export interface RespostaAutocomplete extends Medida {
  prefixo: string;
  palavras: string[];
  total: number;
  truncado: boolean;
}

export interface RespostaLexico extends Medida {
  palavra: string;
  existe: boolean;
  formas: string[];
  continuacoes: number;
  aproximadas: Aproximada[];
  tempo_aproximacao: number;
}

export interface RespostaInsercao extends Medida {
  palavra: string;
  nova: boolean;
  palavras: number;
  nos: number;
}

export interface DetalheDoTermo {
  termo: string;
  radical: string;
  documentos: number;
  exatos: number;
}

export interface RespostaPalavra extends Medida {
  consulta: string;
  termo: string;
  radical: string | null;
  termos: DetalheDoTermo[];
  ignorados: string[];
  documentos: [string, number][];
  frequencias: Record<string, number>;
  cobertura: Record<string, number>;
  todos: string[];
  aproximadas: Record<string, Aproximada[]>;
  correcao: string | null;
  tempo_aproximacao: number;
}

export interface RespostaPrefixo extends Medida {
  prefixo: string;
  termos: string[];
  sugestoes: [string, number][];
  total_disponivel: number;
  truncado: boolean;
  por_termo: Record<string, string[]>;
  documentos: string[];
  ranking: [string, number][];
}

export interface OcorrenciasNoDocumento {
  documento: string;
  ocorrencias: number;
  posicoes: number[];
  contextos: string[];
}

export interface RespostaSequencia extends Medida {
  sequencia: string;
  resultados: OcorrenciasNoDocumento[];
  total_ocorrencias: number;
  comparacoes: number;
}

export interface RespostaEstatisticas {
  corpus: {
    documentos: number;
    palavras: number;
    palavras_brutas: number;
    reducao_stopwords: number;
    termos: number;
    palavras_na_trie: number;
    radicais: number;
    postagens: number;
  };
  memoria: {
    nos_trie: number;
    nos_trie_comprimida: number;
    economia: number;
  };
  construcao: Record<'leitura' | 'preprocessamento' | 'trie' | 'indice' | 'total', string>;
  preprocessamento: Record<string, string>;
  consultas: {
    total: number;
    por_tipo: Record<string, { quantidade: number; total: string; media: string }>;
    ultimas: { tipo: string; texto: string; resultados: number; tempo: string }[];
  };
  hash: Record<string, number>;
}

/** O que a interface precisa de quem executa os algoritmos. */
export interface Motor {
  readonly nome: 'JavaScript' | 'Python';
  estado(): Promise<EstadoSistema>;
  autocompletar(prefixo: string, limite?: number): Promise<RespostaAutocomplete>;
  buscarNoLexico(palavra: string): Promise<RespostaLexico>;
  inserirNoLexico(palavra: string): Promise<RespostaInsercao>;
  buscarPalavra(consulta: string): Promise<RespostaPalavra>;
  buscarPrefixo(prefixo: string, limite?: number): Promise<RespostaPrefixo>;
  buscarSequencia(sequencia: string): Promise<RespostaSequencia>;
  estatisticas(): Promise<RespostaEstatisticas>;
}
