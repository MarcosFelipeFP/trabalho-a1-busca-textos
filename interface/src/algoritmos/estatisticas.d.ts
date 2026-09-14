// Tipos de estatisticas.js, para a interface em TypeScript.

export function agora(): number;

export class Cronometro {
  static iniciar(): Cronometro;
  inicio: number;
  decorrido: number;
  parar(): number;
  readonly ms: number;
}

export interface Medicao<T> {
  resultado: T;
  tempo: number;
  repeticoes: number;
  total: number;
  estimado: boolean;
}

export function medir<T>(
  funcao: () => T,
  opcoes?: { alvoMs?: number; tetoMs?: number },
): Medicao<T>;

export function formatarDuracao(segundos: number): string;

export class Estatisticas {
  documentos: number;
  totalPalavras: number;
  totalPalavrasBrutas: number;
  termosDistintos: number;
  palavrasNaTrie: number;
  nosNaTrie: number;
  nosNaTrieComprimida: number;
  postagens: number;
  tempoLeitura: number;
  tempoPreprocessamento: number;
  tempoTrie: number;
  tempoIndice: number;
  consultas: { tipo: string; texto: string; resultados: number; segundos: number }[];
  tempoTotalConstrucao(): number;
  taxaReducaoStopwords(): number;
  economiaTrieComprimida(): number;
}
