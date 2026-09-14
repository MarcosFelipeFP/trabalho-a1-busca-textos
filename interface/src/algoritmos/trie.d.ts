// Tipos de trie.js, para a interface em TypeScript.

export function normalizar(texto: string): string;
export function ordemDeTexto(a: string, b: string): number;
export function distanciaEdicao(a: string, b: string): number;

export class NoTrie {
  filhos: Map<string, NoTrie>;
  fimDePalavra: boolean;
  formas: Set<string> | null;
  peso: number;
  palavrasAbaixo: number;
  melhorPeso: number;
}

export class Trie {
  constructor(palavras?: Iterable<string>);
  raiz: NoTrie;
  comparacoes: number;
  nosVisitados: number;
  readonly tamanho: number;
  inserir(palavra: string, peso?: number): boolean;
  descer(texto: string): NoTrie | null;
  buscar(palavra: string): boolean;
  formasDe(palavra: string): string[];
  buscarPrefixo(prefixo: string, limite?: number | null): string[];
  contarPrefixo(prefixo: string): number;
  sugerir(prefixo: string, limite?: number): [string, number][];
  buscarAproximado(
    palavra: string,
    distanciaMaxima?: number | null,
    limite?: number | null,
  ): [string, number, number][];
  totalNos(): number;
  altura(): number;
}

export class NoTrieComprimida {
  rotulo: string;
  filhos: Map<string, NoTrieComprimida>;
  fimDePalavra: boolean;
  formas: Set<string> | null;
  palavrasAbaixo: number;
}

export class TrieComprimida {
  constructor(palavras?: Iterable<string>);
  raiz: NoTrieComprimida;
  readonly tamanho: number;
  inserir(palavra: string, peso?: number): boolean;
  buscar(palavra: string): boolean;
  buscarPrefixo(prefixo: string, limite?: number | null): string[];
  contarPrefixo(prefixo: string): number;
  totalNos(): number;
}
