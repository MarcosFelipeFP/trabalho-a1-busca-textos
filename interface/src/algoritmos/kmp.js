/* ===========================================================================
   kmp.js
   Porte de `kmp.py`: algoritmo de Knuth-Morris-Pratt para casamento exato de
   cadeias, usado na consulta da seção 3.7.3 do enunciado -- procurar uma
   sequência de caracteres diretamente no conteúdo original dos documentos.

   Referências:
       Morris, J. H.; Pratt, V. R. "A linear pattern-matching algorithm".
           Technical Report 40, University of California, Berkeley, 1970.
       Knuth, D. E.; Morris, J. H.; Pratt, V. R. "Fast Pattern Matching in
           Strings". SIAM Journal on Computing, 6(2):323-350, 1977.

   ---------------------------------------------------------------------------
   A ideia, em uma frase
   ---------------------------------------------------------------------------
   A busca ingênua, ao falhar na posição j do padrão, joga fora tudo o que já
   tinha descoberto e recomeça uma posição adiante no texto. O KMP observa que
   os j caracteres já casados SÃO CONHECIDOS -- são exatamente os j primeiros
   do padrão -- e portanto dá para calcular de antemão, olhando só o padrão,
   quanto é seguro deslocar sem perder ocorrência nenhuma.

       texto   a b a b a b ...
       padrão  a b a b c
                       ^ falha aqui, com "abab" já casado

   "abab" tem "ab" como maior prefixo que também é sufixo. Logo o algoritmo
   desliza o padrão para alinhar esse "ab" e retoma a comparação a partir do
   terceiro caractere do padrão -- sem NUNCA voltar atrás no texto.

   ---------------------------------------------------------------------------
   Complexidade
   ---------------------------------------------------------------------------
       função de falha    O(m)
       varredura do texto O(n)
       total              O(n + m), com O(m) de memória

   A prova de que a varredura é linear é um argumento de amortização: o
   ponteiro `i` do texto só avança (no máximo n incrementos) e `j` cresce no
   máximo 1 por incremento de `i`, enquanto cada retrocesso via função de falha
   o diminui em pelo menos 1. Como `j` nunca fica negativo, os retrocessos não
   podem exceder os incrementos, e o laço executa no máximo 2n vezes.

   A busca ingênua, em contraste, é O(n * m) no pior caso -- fácil de exibir
   com texto "aaaa...a" e padrão "aaa...ab", em que toda tentativa avança quase
   até o fim do padrão antes de falhar no último caractere.
   =========================================================================== */

/**
 * Constrói a função de falha (vetor de bordas) do padrão.
 *
 * `falha[j]` é o comprimento do maior prefixo PRÓPRIO de padrao[0..j] que
 * também é sufixo de padrao[0..j]. "Próprio" significa que não vale o
 * prefixo inteiro -- senão a resposta seria sempre j+1 e o algoritmo não
 * sairia do lugar. Para "ababc":
 *
 *     j   trecho   maior prefixo = sufixo   falha[j]
 *     0   a        (nenhum)                 0
 *     1   ab       (nenhum)                 0
 *     2   aba      "a"                      1
 *     3   abab     "ab"                     2
 *     4   ababc    (nenhum)                 0
 *
 * A construção é o próprio KMP aplicado ao padrão contra ele mesmo, e o
 * mesmo argumento de amortização garante custo O(m).
 */
function tabelaFalha(padrao) {
  const m = padrao.length;
  const falha = new Array(m).fill(0);
  let comprimento = 0;   // tamanho do prefixo-sufixo atual
  let i = 1;

  while (i < m) {
    if (padrao[i] === padrao[comprimento]) {
      comprimento += 1;
      falha[i] = comprimento;
      i += 1;
    } else if (comprimento > 0) {
      // Não avança i: apenas encurta o candidato e tenta de novo.
      comprimento = falha[comprimento - 1];
    } else {
      falha[i] = 0;
      i += 1;
    }
  }

  return falha;
}

/**
 * Todas as ocorrências de `padrao` em `texto` pelo algoritmo KMP.
 *
 * Devolve { ocorrencias, comparacoes } -- as posições iniciais e o número de
 * comparações de caractere efetuadas. A instrumentação existe para o
 * experimento do relatório, que confronta o custo real com o da busca
 * ingênua.
 *
 * Ocorrências sobrepostas são todas encontradas: procurar "aa" em "aaa"
 * devolve as posições 0 e 1. Após um casamento completo o algoritmo continua
 * de `falha[m-1]`, exatamente como faz numa falha comum.
 *
 * O(n + m) de tempo, O(m) de espaço.
 */
function buscarKmp(texto, padrao, primeiraApenas = false) {
  const n = texto.length;
  const m = padrao.length;
  if (m === 0 || m > n) return { ocorrencias: [], comparacoes: 0 };

  const falha = tabelaFalha(padrao);
  const ocorrencias = [];
  let comparacoes = 0;

  let i = 0;   // ponteiro do texto  -- só avança
  let j = 0;   // ponteiro do padrão -- pode retroceder pela função de falha

  while (i < n) {
    comparacoes += 1;
    if (texto[i] === padrao[j]) {
      i += 1;
      j += 1;
      if (j === m) {
        ocorrencias.push(i - m);
        if (primeiraApenas) break;
        j = falha[j - 1];
      }
    } else if (j > 0) {
      j = falha[j - 1];      // desliza o padrão sem mexer em i
    } else {
      i += 1;                // falhou no primeiro caractere: só anda
    }
  }

  return { ocorrencias, comparacoes };
}

/**
 * Busca por força bruta, implementada apenas como termo de comparação.
 *
 * Testa o padrão em cada uma das n - m + 1 posições possíveis, reiniciando
 * do zero a cada falha. O(n * m) no pior caso.
 */
function buscarIngenuo(texto, padrao, primeiraApenas = false) {
  const n = texto.length;
  const m = padrao.length;
  if (m === 0 || m > n) return { ocorrencias: [], comparacoes: 0 };

  const ocorrencias = [];
  let comparacoes = 0;

  for (let inicio = 0; inicio <= n - m; inicio += 1) {
    let j = 0;
    while (j < m) {
      comparacoes += 1;
      if (texto[inicio + j] !== padrao[j]) break;
      j += 1;
    }
    if (j === m) {
      ocorrencias.push(inicio);
      if (primeiraApenas) break;
    }
  }

  return { ocorrencias, comparacoes };
}

/**
 * O MESMO algoritmo, anotando cada comparação para a interface animar.
 *
 * Não substitui `buscarKmp`: registrar o traço custa memória proporcional ao
 * número de comparações, e a busca de verdade roda sobre centenas de
 * milhares de caracteres. Serve para um trecho curto, escolhido na tela, em
 * que dá para ver o ponteiro do texto nunca voltar atrás.
 *
 * Cada passo é { i, j, casou, deslocamento, evento }, com `evento` em
 * {'compara', 'casa-completo', 'desliza', 'avanca'}.
 */
function tracarKmp(texto, padrao, limitePassos = 4000) {
  const n = texto.length;
  const m = padrao.length;
  const passos = [];
  if (m === 0 || m > n) return { passos, ocorrencias: [], falha: [] };

  const falha = tabelaFalha(padrao);
  const ocorrencias = [];
  let i = 0;
  let j = 0;

  while (i < n && passos.length < limitePassos) {
    const casou = texto[i] === padrao[j];
    passos.push({ i, j, casou, deslocamento: i - j, evento: 'compara' });

    if (casou) {
      i += 1;
      j += 1;
      if (j === m) {
        ocorrencias.push(i - m);
        passos.push({
          i: i - 1, j: j - 1, casou: true,
          deslocamento: i - m, evento: 'casa-completo',
        });
        j = falha[j - 1];
      }
    } else if (j > 0) {
      const antes = j;
      j = falha[j - 1];
      passos.push({
        i, j, casou: false, deslocamento: i - j,
        evento: 'desliza', de: antes, para: j,
      });
    } else {
      i += 1;
      passos.push({ i, j, casou: false, deslocamento: i, evento: 'avanca' });
    }
  }

  return { passos, ocorrencias, falha };
}

/**
 * Recorta um trecho ao redor da ocorrência, para exibir na interface.
 *
 * Não faz parte do algoritmo; é apoio de apresentação. Quebras de linha
 * viram espaço para o trecho caber em uma linha.
 */
function contextoDaOcorrencia(texto, posicao, tamanhoPadrao, margem = 45) {
  const inicio = Math.max(0, posicao - margem);
  const fim = Math.min(texto.length, posicao + tamanhoPadrao + margem);

  let trecho = texto.slice(inicio, fim).replace(/[\r\n]/g, ' ');
  trecho = trecho.split(/\s+/).filter(Boolean).join(' ');

  if (inicio > 0) trecho = '...' + trecho;
  if (fim < texto.length) trecho = trecho + '...';
  return trecho;
}

export { tabelaFalha, buscarKmp, buscarIngenuo, tracarKmp, contextoDaOcorrencia };
