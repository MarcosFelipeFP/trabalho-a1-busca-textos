// Tipos de indice-invertido.js, para a interface em TypeScript.

import type { Preprocessador } from './preprocessamento.js';

export interface EstatisticasHash {
  chaves: number;
  capacidade: number;
  'fator de carga': number;
  'baldes ocupados': number;
  colisoes: number;
  'maior cadeia': number;
  'cadeia media': number;
}

export class TabelaHash {
  constructor(capacidade?: number);
  capacidade: number;
  n: number;
  colisoes: number;
  inserir(chave: string, valor: unknown): boolean;
  buscar(chave: string, padrao?: unknown): unknown;
  estatisticas(): EstatisticasHash;
  distribuicaoDeCadeias(): { tamanho: number; baldes: number }[];
  _redimensionar(): void;
}

export class IndiceInvertido {
  porTermo: Map<string, Map<string, number>>;
  porRadical: Map<string, Map<string, number>>;
  documentos: string[];
  tamanhoDocumento: Map<string, number>;
  totalTokens: number;
  indexar(documento: string, tokens: string[], preprocessador: Preprocessador): void;
  buscar(termo: string, usarRadical?: boolean): Record<string, number>;
  frequenciaDocumental(termo: string, usarRadical?: boolean): number;
  ranquearBm25(termos: string[], usarRadical?: boolean): [string, number][];
  ranquearTfidf(termos: string[], usarRadical?: boolean): [string, number][];
  totalTermos(usarRadical?: boolean): number;
  totalPostagens(usarRadical?: boolean): number;
  tamanhoMedio(): number;
  espelharEmTabelaHash(usarRadical?: boolean): TabelaHash;
  termosMaisFrequentes(
    quantos?: number,
    usarRadical?: boolean,
  ): { termo: string; documentos: number; ocorrencias: number }[];
}
