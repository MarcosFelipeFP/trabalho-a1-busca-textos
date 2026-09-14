/* ===========================================================================
   estatisticas.js
   Porte de `estatisticas.py`: cronometragem e as métricas exigidas na seção
   3.9 do enunciado.

   ---------------------------------------------------------------------------
   Qual relógio usar -- e por que aqui a medição precisa repetir
   ---------------------------------------------------------------------------
   No Python, `time.perf_counter()` é monotônico e tem resolução de
   nanossegundos: uma consulta de 45 µs é medida direto, de uma vez.

   No navegador não dá. Desde as mitigações de Spectre (2018), `performance.now`
   é arredondado de propósito -- na maioria dos navegadores para 100 µs, em
   alguns para 1 ms. Medir uma vez uma consulta de 45 µs devolveria "0" ou
   "100 µs", nunca o valor real, e a comparação entre o índice e o KMP, que é o
   ponto do trabalho, apareceria distorcida.

   A saída é a mesma que `benchmark.py` já adota por razões metodológicas:
   repetir a operação até acumular tempo suficiente para o relógio enxergar, e
   dividir. A interface sempre mostra quantas repetições entraram na conta, de
   modo que o número exibido não pretenda ser algo que não é.

   O efeito colateral é bom: a mediana de centenas de execuções é bem menos
   sensível a um pico do escalonador do que uma execução única.
   =========================================================================== */

import { ordemDeTexto } from './trie.js';

const agora = () => performance.now() / 1000;   // segundos, como no Python

/**
 * Cronômetro de bloco.
 *
 *     const relogio = Cronometro.iniciar();
 *     construirIndice();
 *     relogio.parar();       // relogio.decorrido, em segundos
 */
class Cronometro {
  constructor() {
    this.inicio = agora();
    this.decorrido = 0;
  }

  static iniciar() {
    return new Cronometro();
  }

  parar() {
    this.decorrido = agora() - this.inicio;
    return this.decorrido;
  }

  get ms() {
    return this.decorrido * 1000;
  }
}

/**
 * Executa `funcao` repetidas vezes e devolve o custo POR EXECUÇÃO.
 *
 * A primeira chamada guarda o resultado que a interface vai desenhar e diz se
 * a operação é cara. Operações caras (o KMP varrendo o corpus inteiro) passam
 * de `alvoMs` na primeira execução e não repetem; as baratas (uma consulta ao
 * índice) repetem em lotes crescentes até o tempo acumulado passar do alvo --
 * tempo suficiente para o relógio grosso do navegador resolver. `tetoMs`
 * impede que a página congele.
 *
 * Devolve { resultado, tempo, repeticoes, total, estimado }.
 */
function medir(funcao, { alvoMs = 8, tetoMs = 60 } = {}) {
  const inicioSonda = agora();
  const resultado = funcao();
  const sonda = agora() - inicioSonda;

  const alvo = alvoMs / 1000;
  if (sonda >= alvo) {
    return { resultado, tempo: sonda, repeticoes: 1, total: sonda, estimado: false };
  }

  // A sonda não serve para prever quantas repetições faltam: com o relógio
  // arredondado para 100 µs, uma consulta de 20 µs mede 0 ou 100 µs. Quem
  // decide é o próprio relógio -- lotes que dobram de tamanho até o tempo
  // acumulado passar do alvo. Consultar o relógio só entre lotes evita que a
  // chamada a `performance.now` pese mais que a operação medida.
  const limite = tetoMs / 1000;
  const inicio = agora();
  let feitas = 0;
  let lote = 1;
  let total = 0;
  while (total < alvo) {
    for (let volta = 0; volta < lote; volta += 1) funcao();
    feitas += lote;
    total = agora() - inicio;
    if (total > limite) break;
    lote = Math.min(lote * 2, 65536);
  }

  return {
    resultado,
    tempo: total / feitas,
    repeticoes: feitas,
    total,
    estimado: true,
  };
}

/**
 * Formata uma duração escolhendo a unidade legível.
 *
 * Um índice leva centenas de milissegundos para ser construído; uma consulta
 * leva microssegundos. Exibir tudo na mesma unidade produziria ou "0.000 s"
 * ou "812000.000 µs" -- nenhum dos dois ajuda a ler o resultado.
 */
function formatarDuracao(segundos) {
  if (segundos >= 1) return `${segundos.toFixed(3)} s`;
  if (segundos >= 1e-3) return `${(segundos * 1e3).toFixed(3)} ms`;
  return `${(segundos * 1e6).toFixed(1)} µs`;
}

/**
 * Reúne as sete métricas obrigatórias da seção 3.9 do enunciado.
 *
 *     1. documentos processados
 *     2. total de palavras após a tokenização
 *     3. termos distintos
 *     4. palavras armazenadas na Trie
 *     5. tempo de construção da Trie
 *     6. tempo de construção do índice invertido
 *     7. tempo de cada consulta realizada
 *
 * O item 7 é acumulado em `consultas`, histórico que também alimenta o
 * resumo por tipo exibido na tela de métricas.
 */
class Estatisticas {
  constructor() {
    this.documentos = 0;
    this.totalPalavras = 0;         // tokens após a tokenização
    this.totalPalavrasBrutas = 0;   // tokens antes da remoção de stopwords
    this.termosDistintos = 0;
    this.palavrasNaTrie = 0;
    this.nosNaTrie = 0;
    this.nosNaTrieComprimida = 0;
    this.postagens = 0;

    this.tempoLeitura = 0;
    this.tempoPreprocessamento = 0;
    this.tempoTrie = 0;
    this.tempoIndice = 0;

    this.consultas = [];   // {tipo, texto, resultados, segundos}
  }

  /** Guarda o custo de uma consulta -- item 7 da seção 3.9. */
  registrarConsulta(tipo, texto, resultados, segundos) {
    this.consultas.push({ tipo, texto, resultados, segundos });
  }

  ultimaConsulta() {
    return this.consultas.length ? this.consultas[this.consultas.length - 1] : null;
  }

  /**
   * Agrega o histórico por tipo de consulta.
   *
   * Serve para mostrar, com números do próprio uso, que a busca exata (uma
   * consulta de hash) custa consistentemente menos que a busca por prefixo
   * (que ainda precisa varrer a subárvore da Trie).
   */
  resumoPorTipo() {
    const agregado = new Map();
    for (const { tipo, segundos } of this.consultas) {
      const atual = agregado.get(tipo) || { quantidade: 0, total: 0 };
      atual.quantidade += 1;
      atual.total += segundos;
      agregado.set(tipo, atual);
    }
    return Array.from(agregado.entries())
      .sort((a, b) => ordemDeTexto(a[0], b[0]))
      .map(([tipo, { quantidade, total }]) => ({
        tipo, quantidade, total, media: total / quantidade,
      }));
  }

  /** Soma das quatro fases de construção do sistema. */
  tempoTotalConstrucao() {
    return this.tempoLeitura + this.tempoPreprocessamento +
      this.tempoTrie + this.tempoIndice;
  }

  /** Fração de tokens eliminada pela remoção de stopwords. */
  taxaReducaoStopwords() {
    if (!this.totalPalavrasBrutas) return 0;
    return (this.totalPalavrasBrutas - this.totalPalavras) / this.totalPalavrasBrutas;
  }

  /** Fração de nós economizada pela Trie comprimida. */
  economiaTrieComprimida() {
    if (!this.nosNaTrie) return 0;
    return 1 - (this.nosNaTrieComprimida / this.nosNaTrie);
  }
}

export { agora, Cronometro, medir, formatarDuracao, Estatisticas };
