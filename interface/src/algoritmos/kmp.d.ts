// Tipos de kmp.js, para a interface em TypeScript.

export interface Achado {
  ocorrencias: number[];
  comparacoes: number;
}

export type EventoKmp = 'compara' | 'casa-completo' | 'desliza' | 'avanca';

export interface PassoKmp {
  i: number;
  j: number;
  casou: boolean;
  deslocamento: number;
  evento: EventoKmp;
  de?: number;
  para?: number;
}

export function tabelaFalha(padrao: string): number[];
export function buscarKmp(texto: string, padrao: string, primeiraApenas?: boolean): Achado;
export function buscarIngenuo(texto: string, padrao: string, primeiraApenas?: boolean): Achado;
export function tracarKmp(
  texto: string,
  padrao: string,
  limitePassos?: number,
): { passos: PassoKmp[]; ocorrencias: number[]; falha: number[] };
export function contextoDaOcorrencia(
  texto: string,
  posicao: number,
  tamanhoPadrao: number,
  margem?: number,
): string;
