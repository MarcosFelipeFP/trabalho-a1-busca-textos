/*
 * varreduras.ts
 * -------------
 * As buscas por força bruta que as estruturas do trabalho substituem.
 *
 * Existem para a interface responder à MESMA pergunta sem a estrutura e mostrar
 * os dois custos na tela, medidos, em vez de citados. Rodam sempre no motor
 * JavaScript local, mesmo quando as consultas estão sendo respondidas pelo
 * Python: são termo de comparação, e não a resposta.
 *
 * O `medir` é o mesmo do restante da interface: repete as operações rápidas em
 * lote, porque o relógio do navegador é arredondado (em `file://`, para cerca
 * de 100 µs) e uma varredura de 2 ms mediria 0 ou 100 µs.
 */
import { medir } from '../algoritmos/estatisticas.js';
import { buscarIngenuo, contextoDaOcorrencia } from '../algoritmos/kmp.js';
import type { Aplicacao } from '../algoritmos/mecanismo';
import { normalizar, ordemDeTexto } from '../algoritmos/trie.js';
import type { Medida, OcorrenciasNoDocumento, RespostaSequencia } from './tipos';

/**
 * Acha as palavras do prefixo percorrendo o vocabulário inteiro, uma a uma --
 * o trabalho que a Trie evita ao descer o prefixo e visitar apenas a subárvore
 * alcançada. A resposta é a mesma; o que muda é o custo: O(V·m) contra O(m + p).
 */
export function varrerVocabulario(aplicacao: Aplicacao, prefixo: string): Medida {
  const chave = normalizar(prefixo);
  const palavras = [...aplicacao.mecanismo.vocabulario];

  const medida = medir(() => {
    const encontradas: string[] = [];
    for (const palavra of palavras) {
      if (normalizar(palavra).startsWith(chave)) encontradas.push(palavra);
    }
    return encontradas.sort(ordemDeTexto);
  });
  return { tempo: medida.tempo, repeticoes: medida.repeticoes };
}

/**
 * Procura a sequência com a busca ingênua: ao falhar, ela recomeça uma posição
 * adiante e descarta o que já havia casado -- o oposto do KMP, que aproveita.
 * Devolve a mesma resposta de `buscarSequencia`, para a tela não precisar saber
 * qual dos dois respondeu.
 */
export function buscaIngenuaNoCorpus(
  aplicacao: Aplicacao,
  sequencia: string,
  maxContextos = 3,
): RespostaSequencia {
  const mecanismo = aplicacao.mecanismo;
  const padrao = sequencia.toLowerCase();

  const medida = medir(() => {
    const resultados: OcorrenciasNoDocumento[] = [];
    let totalOcorrencias = 0;
    let totalComparacoes = 0;

    for (const documento of [...mecanismo.conteudo.keys()].sort(ordemDeTexto)) {
      const achado = buscarIngenuo(mecanismo.conteudoMinusculo.get(documento)!, padrao);
      totalComparacoes += achado.comparacoes;
      if (!achado.ocorrencias.length) continue;

      totalOcorrencias += achado.ocorrencias.length;
      const texto = mecanismo.conteudo.get(documento)!;
      resultados.push({
        documento,
        ocorrencias: achado.ocorrencias.length,
        posicoes: achado.ocorrencias,
        contextos: achado.ocorrencias
          .slice(0, maxContextos)
          .map((posicao) => contextoDaOcorrencia(texto, posicao, padrao.length)),
      });
    }

    resultados.sort((a, b) => (b.ocorrencias - a.ocorrencias) ||
      ordemDeTexto(a.documento, b.documento));
    return { resultados, totalOcorrencias, totalComparacoes };
  }, { alvoMs: 0 });   // varre o corpus inteiro: uma execução basta

  return {
    sequencia,
    resultados: medida.resultado.resultados,
    total_ocorrencias: medida.resultado.totalOcorrencias,
    comparacoes: medida.resultado.totalComparacoes,
    tempo: medida.tempo,
    repeticoes: medida.repeticoes,
  };
}
