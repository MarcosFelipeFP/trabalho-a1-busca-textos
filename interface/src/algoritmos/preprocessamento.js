/* ===========================================================================
   preprocessamento.js
   Porte de `preprocessamento.py`: as etapas de preparação do texto exigidas na
   seção 3.3 do enunciado, como funções separadas e encadeáveis.

       1. conversão para minúsculas
       2. remoção de pontuação
       3. tokenização
       4. remoção de stopwords
       5. (opcional) stemming com o algoritmo RSLP

   ---------------------------------------------------------------------------
   Por que o token guarda a forma acentuada
   ---------------------------------------------------------------------------
   A tokenização preserva os acentos ("computação" continua "computação"). Quem
   normaliza é a Trie, ao montar a chave, e o stemmer, no último passo. Manter
   a forma original até o fim é o que permite ao autocomplete devolver a
   palavra escrita corretamente, em vez de uma versão descaracterizada.

   ---------------------------------------------------------------------------
   As duas expressões regulares, traduzidas com cuidado
   ---------------------------------------------------------------------------
   O `re` do Python trabalha em Unicode por padrão: `\w` cobre letras
   acentuadas, e `[^\W\d_]` significa "caractere de palavra que não seja dígito
   nem sublinhado". O JavaScript é o contrário -- `\w` continua sendo
   `[A-Za-z0-9_]` mesmo com a flag `u` --, então a tradução precisa nomear as
   categorias Unicode explicitamente:

       Python  [^\W\d_]+          ->  JS  [\p{L}\p{Nl}\p{No}]+
       Python  [^\w\s]|_          ->  JS  [^\p{L}\p{N}_\s]|_

   `verificar_web.py` compara as duas tokenizações token a token sobre os 24
   documentos do corpus, que é a única forma honesta de afirmar que a tradução
   ficou fiel.
   =========================================================================== */

import { RSLP } from './stemmer-rslp.js';
import { normalizar } from './trie.js';

// Um "token" é uma sequência maximal de letras.
const PADRAO_TOKEN = /[\p{L}\p{Nl}\p{No}]+/gu;

// Pontuação e símbolos viram espaço -- espaço, e não string vazia, para que
// "banco-de-dados" produza três tokens em vez do amálgama "bancodedados".
const PADRAO_PONTUACAO = /[^\p{L}\p{N}_\s]|_/gu;

/** Etapa 1: caixa baixa. O(n) no tamanho do texto. */
function paraMinusculas(texto) {
  return texto.toLowerCase();
}

/**
 * Etapa 2: troca pontuação e símbolos por espaço. O(n).
 *
 * Aparece separada porque o enunciado a lista explicitamente; a tokenização
 * da etapa 3 já daria conta sozinha, mas manter as duas deixa o pipeline
 * rastreável passo a passo.
 */
function removerPontuacao(texto) {
  return texto.replace(PADRAO_PONTUACAO, ' ');
}

/**
 * Etapa 3: quebra o texto em palavras. O(n).
 *
 * Números e sequências alfanuméricas são descartados: o vocabulário é de
 * palavras, e "1998" ou "x86" não têm prefixo linguístico útil para o
 * autocomplete.
 */
function tokenizar(texto) {
  return texto.match(PADRAO_TOKEN) || [];
}

/**
 * Etapa 4: descarta palavras vazias e tokens curtos demais. O(t).
 *
 * A comparação é feita sobre a forma normalizada (minúscula e sem acento),
 * de modo que a lista de stopwords pode ser escrita sem acentuação. Cada
 * teste é uma consulta a conjunto hash, O(1) em média.
 */
function removerStopwords(tokens, stopwords, tamanhoMinimo = 2) {
  return tokens.filter((token) =>
    token.length >= tamanhoMinimo && !stopwords.has(normalizar(token)));
}

/**
 * Encapsula o pipeline completo e a configuração usada em todo o sistema.
 *
 * Manter uma única instância compartilhada garante que documentos e consultas
 * passem exatamente pelo mesmo tratamento -- se a indexação remover
 * stopwords e a consulta não, os dois lados deixam de se encontrar.
 */
class Preprocessador {
  constructor({ stopwords = null, usarStemming = true, tamanhoMinimo = 2 } = {}) {
    this.stopwords = stopwords instanceof Set
      ? stopwords
      : new Set((stopwords || []).map(normalizar));
    this.usarStemming = usarStemming;
    this.tamanhoMinimo = tamanhoMinimo;
    this.stemmer = new RSLP();
  }

  /** Etapas 1 a 4, preservando a acentuação original. O(n + t). */
  processar(texto) {
    return this.processarDetalhado(texto)[1];
  }

  /**
   * Como `processar`, mas devolve também os tokens ANTES da remoção de
   * stopwords, na forma [brutos, filtrados].
   *
   * Existe para evitar trabalho duplicado na indexação: as estatísticas da
   * seção 3.9 pedem tanto o total bruto quanto o total após a filtragem, e
   * obter os dois com duas chamadas separadas tokenizaria o documento duas
   * vezes.
   */
  processarDetalhado(texto) {
    let preparado = paraMinusculas(texto);
    preparado = removerPontuacao(preparado);
    const brutos = tokenizar(preparado);
    const filtrados = removerStopwords(brutos, this.stopwords, this.tamanhoMinimo);
    return [brutos, filtrados];
  }

  /**
   * Etapa 5: o radical do token quando o stemming está ligado; caso
   * contrário, apenas a forma normalizada.
   *
   * É este método que define a CHAVE do índice invertido, e ele precisa ser
   * o mesmo na indexação e na consulta.
   */
  radicalizar(token) {
    if (this.usarStemming) return this.stemmer.radicalizar(token);
    return normalizar(token);
  }

  /**
   * Passa o texto digitado pelo mesmo pipeline dos documentos.
   *
   * Diferença importante: aqui as stopwords NÃO são descartadas em silêncio;
   * se a consulta inteira for filtrada, devolve-se lista vazia e a interface
   * avisa quem digitou.
   */
  processarConsulta(texto) {
    return tokenizar(removerPontuacao(paraMinusculas(texto)));
  }

  /**
   * Separa a consulta em termos pesquisáveis e palavras ignoradas, devolvendo
   * [termos, ignorados].
   *
   * Uma consulta com várias palavras descarta as stopwords do mesmo jeito que
   * a indexação descartou: em "estrutura de dados", o "de" não está no índice,
   * e exigir que os documentos contenham TODOS os termos zeraria qualquer
   * resultado.
   */
  termosDaConsulta(texto) {
    const brutos = this.processarConsulta(texto);
    const termos = removerStopwords(brutos, this.stopwords, this.tamanhoMinimo);
    const mantidos = new Set(termos);
    const ignorados = brutos.filter((token) => !mantidos.has(token));
    return [termos, ignorados];
  }

  /** Resumo da configuração, exibido nas estatísticas do sistema. */
  descrever() {
    return {
      'stopwords carregadas': this.stopwords.size,
      stemming: this.usarStemming ? 'RSLP (Orengo & Huyck, 2001)' : 'desligado',
      'tamanho minimo do token': this.tamanhoMinimo,
    };
  }
}

export { paraMinusculas, removerPontuacao, tokenizar, removerStopwords, Preprocessador };
