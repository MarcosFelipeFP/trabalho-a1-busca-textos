/*
 * Trechos e realces.
 *
 * O que acende no texto depende de como a busca encontrou o documento:
 *   palavra    toda palavra cujo radical é o de um termo da consulta
 *              ("rede" acende "redes", porque o índice as uniu);
 *   prefixo    toda palavra que começa com o prefixo;
 *   sequência  a sequência exata, sem diferenciar maiúsculas.
 */
import { Fragment } from 'react';

import { normalizar } from '../algoritmos/trie.js';

export type Criterio =
  | { tipo: 'radicais'; radicais: Set<string>; radicalizar: (palavra: string) => string }
  | { tipo: 'prefixo'; chave: string }
  | { tipo: 'sequencia'; trecho: string };

export interface Segmento {
  texto: string;
  realce: boolean;
}

const PALAVRA = /\p{L}+/gu;

function acende(criterio: Criterio, palavra: string): boolean {
  if (palavra.length < 2) return false;
  if (criterio.tipo === 'radicais') return criterio.radicais.has(criterio.radicalizar(palavra.toLowerCase()));
  if (criterio.tipo === 'prefixo') return normalizar(palavra).startsWith(criterio.chave);
  return false;
}

/** Posições [início, fim) de tudo o que acende em `texto`. */
function faixas(texto: string, criterio: Criterio, primeiraApenas = false): [number, number][] {
  const achadas: [number, number][] = [];
  if (criterio.tipo === 'sequencia') {
    const alvo = criterio.trecho.toLowerCase();
    const minusculo = texto.toLowerCase();
    if (!alvo || minusculo.length !== texto.length) return achadas;
    for (let i = minusculo.indexOf(alvo); i !== -1; i = minusculo.indexOf(alvo, i + alvo.length)) {
      achadas.push([i, i + alvo.length]);
      if (primeiraApenas) break;
    }
    return achadas;
  }
  for (const achado of texto.matchAll(PALAVRA)) {
    if (!acende(criterio, achado[0])) continue;
    const inicio = achado.index ?? 0;
    achadas.push([inicio, inicio + achado[0].length]);
    if (primeiraApenas) break;
  }
  return achadas;
}

function segmentar(texto: string, marcas: [number, number][], deslocamento = 0): Segmento[] {
  const saida: Segmento[] = [];
  let cursor = 0;
  for (const [inicio, fim] of marcas) {
    const a = inicio - deslocamento;
    const b = fim - deslocamento;
    if (b <= 0 || a >= texto.length) continue;
    if (a > cursor) saida.push({ texto: texto.slice(cursor, a), realce: false });
    saida.push({ texto: texto.slice(Math.max(a, 0), b), realce: true });
    cursor = b;
  }
  if (cursor < texto.length) saida.push({ texto: texto.slice(cursor), realce: false });
  return saida;
}

/** O texto inteiro, com as marcas: é o que o leitor desenha. */
export function marcarTexto(texto: string, criterio: Criterio): { segmentos: Segmento[]; total: number } {
  const marcas = faixas(texto, criterio);
  return { segmentos: segmentar(texto, marcas), total: marcas.length };
}

/**
 * Um trecho de cerca de `tamanho` caracteres em torno da primeira ocorrência,
 * cortado em fronteira de palavra, com as marcas que caírem dentro dele.
 */
export function extrairTrecho(texto: string, criterio: Criterio, tamanho = 230): Segmento[] | null {
  const [primeira] = faixas(texto, criterio, true);
  if (!primeira) return null;

  let inicio = Math.max(0, primeira[0] - 80);
  if (inicio > 0) inicio = texto.indexOf(' ', inicio) + 1 || inicio;
  let fim = Math.min(texto.length, inicio + tamanho);
  if (fim < texto.length) fim = texto.lastIndexOf(' ', fim) > primeira[1] ? texto.lastIndexOf(' ', fim) : fim;

  const pedaco = texto.slice(inicio, fim).replace(/\s/g, ' ');
  // Cada quebra de linha vira UM espaço, sem juntar vários: o tamanho não muda
  // e as posições das marcas continuam valendo dentro do pedaço.
  const marcas = faixas(texto.slice(inicio, fim), criterio);
  const segmentos = segmentar(pedaco, marcas);
  if (inicio > 0) segmentos.unshift({ texto: '… ', realce: false });
  if (fim < texto.length) segmentos.push({ texto: ' …', realce: false });
  return segmentos;
}

export function Segmentos({ segmentos }: { segmentos: Segmento[] }) {
  return (
    <>
      {segmentos.map((segmento, indice) =>
        segmento.realce ? <mark key={indice}>{segmento.texto}</mark> : <Fragment key={indice}>{segmento.texto}</Fragment>,
      )}
    </>
  );
}
