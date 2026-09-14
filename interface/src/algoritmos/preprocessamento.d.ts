// Tipos de preprocessamento.js, para a interface em TypeScript.

import type { RSLP } from './stemmer-rslp.js';

export function paraMinusculas(texto: string): string;
export function removerPontuacao(texto: string): string;
export function tokenizar(texto: string): string[];
export function removerStopwords(tokens: string[], stopwords: Set<string>, tamanhoMinimo?: number): string[];

export class Preprocessador {
  constructor(opcoes?: { stopwords?: Iterable<string> | null; usarStemming?: boolean; tamanhoMinimo?: number });
  stopwords: Set<string>;
  usarStemming: boolean;
  tamanhoMinimo: number;
  stemmer: RSLP;
  processar(texto: string): string[];
  processarDetalhado(texto: string): [string[], string[]];
  radicalizar(token: string): string;
  processarConsulta(texto: string): string[];
  termosDaConsulta(texto: string): [string[], string[]];
  descrever(): Record<string, string | number>;
}
