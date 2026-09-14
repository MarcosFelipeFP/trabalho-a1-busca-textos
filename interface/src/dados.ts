/*
 * Corpus, léxico e stopwords, gerados por `python gerar_dados_web.py` e
 * embutidos no arquivo final pelo Vite. É o que permite abrir a página sem
 * servidor: nada é buscado do disco depois que ela carrega.
 */
import corpus from './dados/corpus.json';
import lexico from './dados/lexico.json';
import stopwords from './dados/stopwords.json';

export interface DocumentoBruto {
  nome: string;
  titulo: string;
  bytes: number;
  texto: string;
}

export const DADOS = {
  corpus: corpus as DocumentoBruto[],
  lexico: lexico as string[],
  stopwords: stopwords as string[],
};

const TITULOS = new Map(DADOS.corpus.map((documento) => [documento.nome, documento.titulo]));

/** "computacao_quantica.txt" vira "Computação quântica". */
export function tituloDe(nome: string): string {
  return TITULOS.get(nome) ?? nome.replace(/\.txt$/i, '').replace(/_/g, ' ');
}
