// Tipos de stemmer-rslp.js, para a interface em TypeScript.

export interface EtapaRslp {
  passo: string;
  de: string;
  para: string;
}

export class RSLP {
  constructor(usarCache?: boolean);
  radicalizar(palavra: string): string;
  explicar(palavra: string): { palavra: string; radical: string; etapas: EtapaRslp[] };
}

export const radical: (palavra: string) => string;
