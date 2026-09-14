/* ===========================================================================
   stemmer-rslp.js
   Porte de `stemmer_rslp.py`: o RSLP (Removedor de Sufixos da Língua
   Portuguesa), algoritmo de stemming projetado para o português.

   Referência principal:
       Orengo, V. M.; Huyck, C. "A Stemming Algorithm for the Portuguese
       Language". In: Proceedings of the 8th International Symposium on String
       Processing and Information Retrieval (SPIRE 2001), Laguna de San Rafael,
       Chile, pp. 186-193, IEEE Computer Society, 2001.

   ---------------------------------------------------------------------------
   Por que stemming importa neste trabalho
   ---------------------------------------------------------------------------
   O enunciado, no exemplo da seção 3.7.1, digita "algoritmo" no singular e
   espera encontrá-la em três arquivos -- só que o texto dos documentos traz
   "algoritmos" no plural. Sem normalização morfológica a consulta falharia. O
   stemmer reduz as duas formas ao mesmo radical, de modo que variantes
   flexionais caiam na mesma entrada do índice invertido.

   ---------------------------------------------------------------------------
   Como o algoritmo funciona
   ---------------------------------------------------------------------------
   Oito passos aplicados em ordem. Cada regra é uma quádrupla

       [sufixo, tamanhoMinimoDoRadical, substituicao, excecoes]

   e dentro de um passo as regras são testadas na ordem em que aparecem -- do
   sufixo mais longo para o mais curto --, valendo apenas a PRIMEIRA que casar.
   Uma regra só se aplica se, retirado o sufixo, sobrar um radical com pelo
   menos `tamanhoMinimo` caracteres; palavras da lista de exceções voltam
   intactas. O fluxo de controle é o do artigo original:

       se termina em "s"  -> Passo 1: redução de plural
       se termina em "a"  -> Passo 2: redução de feminino
                             Passo 3: redução de advérbio
                             Passo 4: redução de aumentativo/diminutivo
                             Passo 5: redução de sufixo nominal
       se o passo 5 não mudou a palavra:
                             Passo 6: redução de sufixo verbal
           se o passo 6 também não mudou:
                             Passo 7: remoção da vogal temática final
                             Passo 8: remoção de acentos

   ---------------------------------------------------------------------------
   Observação honesta sobre a implementação
   ---------------------------------------------------------------------------
   As tabelas reproduzem a estrutura e as regras publicadas do RSLP, mas as
   listas de exceções foram reduzidas às palavras mais frequentes -- as tabelas
   completas somam algumas centenas de exceções levantadas manualmente pelos
   autores. O efeito prático é um pouco mais de over-stemming em casos raros.

   As tabelas abaixo são as MESMAS de `stemmer_rslp.py`, e `verificar_web.py`
   confere radical por radical que as duas implementações concordam sobre todo
   o vocabulário do corpus.
   =========================================================================== */

const DIACRITICOS = /\p{M}/gu;

/* =======================================================================
   PASSO 1 - REDUÇÃO DE PLURAL   (só se a palavra termina em "s")
   ======================================================================= */
const REGRAS_PLURAL = [
  ["ns", 1, "m", []],
  ["ões", 3, "ão", []],
  ["ães", 1, "ão", ["mães", "alemães"]],
  ["ais", 1, "al", ["cais", "mais", "pais"]],
  ["éis", 2, "el", []],
  ["eis", 2, "el", []],
  ["óis", 2, "ol", []],
  ["is", 2, "il", [
    "lápis", "cais", "mais", "crúcis", "biquínis", "pois", "depois", "dois",
    "leis", "seis"
  ]],
  ["les", 3, "l", []],
  ["res", 3, "r", ["árvores"]],
  ["s", 2, "", [
    "aliás", "pires", "lápis", "cais", "mais", "mas", "menos", "férias",
    "fezes", "pêsames", "crúcis", "gás", "atrás", "moisés", "através",
    "convés", "ês", "país", "após", "ambas", "ambos", "messias", "depois",
    "mês", "três"
  ]],
];

/* =======================================================================
   PASSO 2 - REDUÇÃO DE FEMININO  (só se a palavra termina em "a")
   ======================================================================= */
const REGRAS_FEMININO = [
  ["ona", 3, "ão", [
    "abandona", "lona", "iona", "cortisona", "monótona", "maratona",
    "acetona", "detona", "carona", "persona"
  ]],
  ["ora", 3, "or", []],
  ["na", 4, "no", [
    "carona", "abandona", "lona", "iona", "cortisona", "monótona",
    "maratona", "acetona", "detona", "guiana", "campana", "grana",
    "caravana", "banana", "paisana", "máquina", "página", "pessoana"
  ]],
  ["inha", 3, "inho", ["rainha", "linha", "minha", "campinha"]],
  ["esa", 3, "ês", [
    "mesa", "obesa", "princesa", "turquesa", "ilesa", "pesa", "presa",
    "empresa", "defesa", "surpresa"
  ]],
  ["osa", 3, "oso", ["mucosa", "prosa"]],
  ["íaca", 3, "íaco", []],
  ["ica", 3, "ico", [
    "dica", "música", "física", "lógica", "prática", "técnica", "política",
    "pública", "básica"
  ]],
  ["ada", 3, "ado", ["pitada", "entrada", "estrada", "chamada", "rodada"]],
  ["ida", 3, "ido", ["vida", "dúvida", "medida", "saída", "guarida"]],
  ["ída", 3, "ido", ["recaída", "saída", "dúvida"]],
  ["ima", 3, "imo", ["vítima", "estima"]],
  ["iva", 3, "ivo", ["saliva", "oliva", "deriva"]],
  ["eira", 3, "eiro", [
    "beira", "cadeira", "frigideira", "bandeira", "feira", "capoeira",
    "barreira", "fronteira", "besteira", "poeira", "maneira", "carteira",
    "madeira"
  ]],
  ["ã", 2, "ão", ["amanhã", "arapuã", "fã", "divã"]],
];

/* =======================================================================
   PASSO 3 - REDUÇÃO DE ADVÉRBIO
   ======================================================================= */
const REGRAS_ADVERBIO = [
  ["mente", 4, "", ["experimente", "regimente", "elemente"]],
];

/* =======================================================================
   PASSO 4 - AUMENTATIVO, DIMINUTIVO E SUPERLATIVO
   ======================================================================= */
const REGRAS_AUMENTATIVO = [
  ["díssimo", 5, "", []],
  ["abilíssimo", 5, "", []],
  ["íssimo", 3, "", []],
  ["ésimo", 3, "", []],
  ["érrimo", 4, "", []],
  ["zinho", 2, "", []],
  ["quinho", 4, "c", []],
  ["uinho", 4, "", []],
  ["adinho", 3, "", []],
  ["inho", 3, "", ["caminho", "cominho", "vizinho", "moinho"]],
  ["alhão", 4, "", []],
  ["uça", 4, "", []],
  ["aço", 4, "", ["antebraço"]],
  ["aça", 4, "", []],
  ["adão", 4, "", []],
  ["idão", 4, "", []],
  ["ázio", 3, "", ["topázio"]],
  ["arraz", 4, "", []],
  ["zarrão", 3, "", []],
  ["arrão", 4, "", []],
  ["arra", 3, "", []],
  ["zão", 2, "", ["coração"]],
  ["ão", 3, "", [
    "camarão", "chimarrão", "canção", "coração", "embrião", "grotão",
    "glutão", "ficção", "fogão", "feijão", "divisão", "profissão", "vazão",
    "cão", "razão", "limão", "leão", "mamão", "sabão", "verão", "balão",
    "salão", "sertão", "irmão", "cristão", "alemão", "capitão", "pão",
    "chão", "mão", "não", "então", "bilhão", "milhão", "questão", "padrão",
    "versão", "tensão", "extensão", "dimensão", "precisão", "decisão",
    "conclusão", "inclusão", "exclusão", "difusão", "confusão", "revisão",
    "televisão", "visão", "missão", "comissão", "permissão", "transmissão",
    "admissão", "emissão", "pressão", "sessão", "expressão", "impressão",
    "compressão", "progressão", "agressão", "regressão", "depressão",
    "concessão", "sucessão"
  ]],
];

/* =======================================================================
   PASSO 5 - SUFIXO NOMINAL
   ======================================================================= */
const REGRAS_NOMINAL = [
  ["encialista", 4, "", []],
  ["alista", 5, "", []],
  ["agem", 3, "", [
    "coragem", "chantagem", "vantagem", "carruagem", "imagem", "viagem",
    "linguagem", "mensagem"
  ]],
  ["iamento", 4, "", []],
  ["amento", 3, "", ["firmamento", "fundamento", "departamento"]],
  ["imento", 3, "", []],
  ["mento", 6, "", [
    "firmamento", "elemento", "complemento", "instrumento", "departamento",
    "documento", "argumento", "movimento", "momento"
  ]],
  ["alizado", 4, "", []],
  ["atizado", 4, "", []],
  ["tizado", 4, "", ["alfabetizado"]],
  ["izado", 5, "", ["organizado", "pulverizado"]],
  ["ativo", 4, "", ["pejorativo", "relativo"]],
  ["tivo", 4, "", ["relativo"]],
  ["ivo", 4, "", [
    "passivo", "possessivo", "pejorativo", "positivo", "motivo", "objetivo",
    "arquivo"
  ]],
  ["ado", 2, "", [
    "grado", "estado", "lado", "dado", "mercado", "resultado",
    "significado", "empregado"
  ]],
  ["ido", 3, "", [
    "cândido", "consolido", "rápido", "decido", "líquido", "sólido",
    "válido", "conteúdo", "sentido", "partido", "pedido"
  ]],
  ["ador", 3, "", []],
  ["edor", 3, "", []],
  ["idor", 4, "", ["ouvidor"]],
  ["dor", 4, "", ["ouvidor"]],
  ["sor", 4, "", ["assessor"]],
  ["atória", 5, "", []],
  ["tor", 3, "", [
    "benfeitor", "leitor", "editor", "pastor", "produtor", "promotor",
    "consultor", "vetor", "setor", "fator", "motor"
  ]],
  ["or", 2, "", [
    "motor", "melhor", "redor", "rigor", "sensor", "tambor", "tumor",
    "assessor", "benfeitor", "pastor", "favor", "autor", "valor", "calor",
    "amor", "cor", "dor", "flor", "maior", "menor", "pior", "senhor",
    "setor", "vetor", "fator"
  ]],
  ["abilidade", 5, "", []],
  ["icionista", 4, "", []],
  ["cionista", 5, "", []],
  ["ionista", 5, "", []],
  ["ista", 4, "", ["batista", "vista", "lista", "revista", "conquista", "analista"]],
  ["aria", 3, "", ["maria", "varia"]],
  ["eiro", 3, "", [
    "desespero", "primeiro", "ligeiro", "barbeiro", "brasileiro",
    "cargueiro", "fronteiro", "dinheiro", "inteiro", "janeiro", "roteiro"
  ]],
  ["uoso", 3, "", []],
  ["oso", 3, "", ["precioso", "gostoso"]],
  ["aticidade", 4, "", []],
  ["icidade", 4, "", []],
  ["idade", 4, "", ["autoridade", "comunidade"]],
  ["dade", 4, "", [
    "autoridade", "comunidade", "oportunidade", "contabilidade",
    "reciprocidade"
  ]],
  ["ivel", 4, "", ["possível"]],
  ["ível", 4, "", ["possível"]],
  ["ável", 2, "", ["afável", "razoável", "potável", "vulnerável"]],
  ["ência", 3, "", []],
  ["ância", 4, "", ["ambulância"]],
  ["ncia", 3, "", []],
  ["edouro", 3, "", []],
  ["queiro", 3, "c", []],
  ["adeiro", 4, "", ["desfiladeiro"]],
  ["ário", 3, "", [
    "voluntário", "salário", "aniversário", "diário", "armário",
    "necessário", "usuário", "binário"
  ]],
  ["oira", 3, "o", []],
  ["ério", 6, "", []],
  ["ês", 4, "", []],
  ["eza", 3, "", []],
  ["ez", 4, "", []],
  ["esco", 4, "", []],
  ["ante", 2, "", [
    "gigante", "elefante", "adiante", "possante", "instante", "restaurante",
    "importante", "constante", "durante", "diante"
  ]],
  ["ástico", 4, "", ["eclesiástico"]],
  ["ático", 3, "", []],
  ["ico", 4, "", [
    "público", "básico", "físico", "clássico", "prático", "técnico",
    "único", "típico"
  ]],
  ["ividade", 5, "", []],
  ["ismo", 3, "", ["cinismo", "organismo", "mecanismo"]],
  ["ente", 4, "", [
    "acidente", "alimente", "presente", "ambiente", "cliente", "diferente",
    "eficiente", "gerente", "paciente", "recente"
  ]],
  ["ense", 5, "", []],
  ["inal", 3, "", []],
  ["ano", 4, "", ["humano", "plano", "urbano", "oceano"]],
  ["ura", 4, "", [
    "imatura", "acupuntura", "costura", "estrutura", "cultura", "figura",
    "leitura", "natura"
  ]],
  ["ural", 4, "", []],
  ["ual", 3, "", [
    "bissexual", "virtual", "visual", "pontual", "atual", "manual", "anual",
    "casual"
  ]],
  ["ial", 3, "", [
    "social", "especial", "material", "essencial", "inicial", "oficial",
    "parcial"
  ]],
  ["al", 4, "", [
    "afinal", "animal", "estatal", "bissexual", "desleal", "fiscal",
    "formal", "pessoal", "liberal", "postal", "virtual", "visual",
    "pontual", "sideral", "sucursal", "digital", "total", "final", "local",
    "natural", "geral", "principal", "capital", "central", "global"
  ]],
];

/* =======================================================================
   PASSO 6 - SUFIXO VERBAL
   ======================================================================= */
const REGRAS_VERBAL = [
  ["aríamos", 3, "", []],
  ["eríamos", 3, "", []],
  ["iríamos", 3, "", []],
  ["ássemos", 3, "", []],
  ["êssemos", 3, "", []],
  ["íssemos", 3, "", []],
  ["aríeis", 3, "", []],
  ["eríeis", 3, "", []],
  ["iríeis", 3, "", []],
  ["ásseis", 3, "", []],
  ["ésseis", 3, "", []],
  ["ísseis", 3, "", []],
  ["áramos", 3, "", []],
  ["éramos", 3, "", []],
  ["íramos", 3, "", []],
  ["ávamos", 3, "", []],
  ["aremos", 3, "", []],
  ["eremos", 3, "", []],
  ["iremos", 3, "", []],
  ["ariam", 3, "", []],
  ["eriam", 3, "", []],
  ["iriam", 3, "", []],
  ["assem", 3, "", []],
  ["essem", 3, "", []],
  ["issem", 3, "", []],
  ["ando", 2, "", []],
  ["endo", 3, "", []],
  ["indo", 3, "", []],
  ["ondo", 3, "", []],
  ["aramos", 3, "", []],
  ["eramos", 3, "", []],
  ["iramos", 3, "", []],
  ["arias", 3, "", []],
  ["erias", 3, "", []],
  ["irias", 3, "", []],
  ["ardes", 3, "", []],
  ["erdes", 3, "", []],
  ["irdes", 3, "", []],
  ["asses", 3, "", []],
  ["esses", 3, "", []],
  ["isses", 3, "", []],
  ["astes", 3, "", []],
  ["estes", 3, "", []],
  ["istes", 3, "", []],
  ["áveis", 3, "", []],
  ["áreis", 3, "", []],
  ["éreis", 3, "", []],
  ["íreis", 3, "", []],
  ["araas", 3, "", []],
  ["arão", 3, "", []],
  ["erão", 3, "", []],
  ["irão", 3, "", []],
  ["arás", 3, "", []],
  ["erás", 3, "", []],
  ["irás", 3, "", []],
  ["aria", 3, "", []],
  ["eria", 3, "", []],
  ["iria", 3, "", []],
  ["asse", 3, "", []],
  ["esse", 3, "", []],
  ["isse", 3, "", []],
  ["aste", 3, "", []],
  ["este", 3, "", []],
  ["iste", 3, "", []],
  ["arei", 3, "", []],
  ["erei", 3, "", []],
  ["irei", 3, "", []],
  ["aram", 3, "", []],
  ["eram", 3, "", []],
  ["iram", 3, "", []],
  ["avam", 2, "", []],
  ["arem", 3, "", []],
  ["erem", 3, "", []],
  ["irem", 3, "", []],
  ["ares", 3, "", []],
  ["eres", 3, "", []],
  ["ires", 3, "", []],
  ["avas", 2, "", []],
  ["íeis", 3, "", []],
  ["ados", 3, "", []],
  ["idos", 3, "", []],
  ["ámos", 3, "", []],
  ["amos", 3, "", []],
  ["emos", 3, "", []],
  ["imos", 3, "", []],
  ["iras", 3, "", []],
  ["ada", 2, "", []],
  ["ida", 3, "", []],
  ["ará", 3, "", []],
  ["ara", 3, "", ["prepara"]],
  ["erá", 3, "", []],
  ["era", 3, "", ["espera", "considera"]],
  ["irá", 3, "", []],
  ["ava", 2, "", []],
  ["ado", 2, "", []],
  ["ido", 3, "", []],
  ["ide", 3, "", []],
  ["ode", 3, "", []],
  ["ade", 3, "", ["abade"]],
  ["ede", 3, "", []],
  ["ira", 3, "", ["fronteira", "sátira"]],
  ["eis", 3, "", []],
  ["ei", 3, "", []],
  ["eu", 3, "", ["chapeu"]],
  ["iu", 3, "", []],
  ["ou", 3, "", []],
  ["ar", 2, "", ["lugar", "bar", "par", "mar", "ar"]],
  ["er", 2, "", ["ter", "ser", "poder", "haver", "qualquer", "mulher"]],
  ["ir", 3, "", ["ir"]],
  ["am", 2, "", []],
  ["em", 2, "", [
    "tem", "bem", "quem", "além", "porém", "alguém", "ninguém", "vem",
    "item", "ordem"
  ]],
  ["ia", 2, "", [
    "estória", "fatia", "acia", "praia", "elogia", "mania", "lábia",
    "aprecia", "polícia", "arredia", "cheia", "ásia", "dia", "via",
    "família", "energia", "teoria", "memória", "história", "economia",
    "tecnologia"
  ]],
  ["i", 3, "", []],
];

/* =======================================================================
   PASSO 7 - VOGAL TEMÁTICA FINAL
   ======================================================================= */
const REGRAS_VOGAL = [
  ["a", 3, "", ["ásia"]],
  ["e", 3, "", []],
  ["o", 3, "", ["ão"]],
];

/* Os passos 3 e 4 não dependem da terminação da palavra: saem em sequência. */
const PASSOS_INTERMEDIARIOS = [REGRAS_ADVERBIO, REGRAS_AUMENTATIVO];

/**
 * Converte as listas de exceções em `Set`.
 *
 * O Python varre a tupla de exceções linearmente; aqui a consulta é O(1). O
 * resultado da regra não muda -- só o custo de descobrir que a palavra é
 * exceção --, e as tabelas continuam legíveis como literais acima.
 */
function compilar(regras) {
  return regras.map(([sufixo, minimo, substituicao, excecoes]) => ({
    sufixo,
    minimo,
    substituicao,
    excecoes: new Set(excecoes),
  }));
}

const COMPILADAS = new Map();
for (const tabela of [REGRAS_PLURAL, REGRAS_FEMININO, REGRAS_ADVERBIO,
                      REGRAS_AUMENTATIVO, REGRAS_NOMINAL, REGRAS_VERBAL,
                      REGRAS_VOGAL]) {
  COMPILADAS.set(tabela, compilar(tabela));
}

/* =========================================================================
   O STEMMER
   ========================================================================= */

class RSLP {
  constructor(usarCache = true) {
    this.cache = usarCache ? new Map() : null;
    this.chamadas = 0;
    this.acertosCache = 0;
  }

  /* ---------------------------------------------------------- utilidades */

  /** Passo 8: remove os sinais diacríticos, mantendo as letras-base. */
  static semAcento(palavra) {
    return palavra.normalize('NFD').replace(DIACRITICOS, '');
  }

  /**
   * Testa as regras de um passo na ordem e aplica a primeira que casar.
   *
   * Devolve [palavraResultante, houveMudanca]. Três condições precisam valer:
   *   1. a palavra termina com o sufixo da regra;
   *   2. o radical que sobra tem o tamanho mínimo exigido;
   *   3. a palavra não está na lista de exceções.
   *
   * Quando a palavra é exceção conhecida, o passo inteiro é abandonado e ela
   * volta intacta -- comportamento da implementação de referência.
   */
  static aplicar(palavra, regras) {
    for (const regra of COMPILADAS.get(regras)) {
      if (!palavra.endsWith(regra.sufixo)) continue;
      if (palavra.length - regra.sufixo.length < regra.minimo) continue;
      if (regra.excecoes.has(palavra)) return [palavra, false];
      return [
        palavra.slice(0, palavra.length - regra.sufixo.length) + regra.substituicao,
        true,
      ];
    }
    return [palavra, false];
  }

  /* ------------------------------------------------------------- radical */

  /**
   * Reduz a palavra ao seu radical, seguindo o fluxo de oito passos do RSLP.
   *
   * Palavras com menos de três letras voltam apenas sem acento: não há
   * radical a extrair e qualquer corte as destruiria.
   *
   * A memoização importa: o corpus tem cerca de cem mil tokens para menos de
   * quinze mil palavras distintas, então a maior parte das chamadas feitas
   * durante a indexação é repetição.
   */
  radicalizar(palavra) {
    this.chamadas += 1;
    const original = String(palavra).toLowerCase().trim();

    if (this.cache !== null) {
      const guardado = this.cache.get(original);
      if (guardado !== undefined) {
        this.acertosCache += 1;
        return guardado;
      }
    }

    const resultado = this.semCache(original);

    if (this.cache !== null) this.cache.set(original, resultado);
    return resultado;
  }

  semCache(palavra) {
    if (palavra.length < 3) return RSLP.semAcento(palavra);

    // Passo 1 - plural
    if (palavra.endsWith('s')) {
      [palavra] = RSLP.aplicar(palavra, REGRAS_PLURAL);
    }

    // Passo 2 - feminino
    if (palavra.endsWith('a')) {
      [palavra] = RSLP.aplicar(palavra, REGRAS_FEMININO);
    }

    // Passos 3 e 4 - advérbio, depois aumentativo / diminutivo / superlativo
    for (const passo of PASSOS_INTERMEDIARIOS) {
      [palavra] = RSLP.aplicar(palavra, passo);
    }

    // Passo 5 - sufixo nominal
    let mudou;
    [palavra, mudou] = RSLP.aplicar(palavra, REGRAS_NOMINAL);

    // Passo 6 - sufixo verbal, apenas se o passo 5 não alterou nada
    if (!mudou) {
      [palavra, mudou] = RSLP.aplicar(palavra, REGRAS_VERBAL);

      // Passo 7 - vogal temática, apenas se o passo 6 também não alterou
      if (!mudou) {
        [palavra] = RSLP.aplicar(palavra, REGRAS_VOGAL);
      }
    }

    // Passo 8 - remoção de acentos
    return RSLP.semAcento(palavra);
  }

  /**
   * Registro do caminho percorrido, passo a passo -- existe só para a
   * interface poder mostrar POR QUE "algoritmos" e "algorítmica" caem no
   * mesmo radical.
   *
   * Repete o fluxo de `semCache` anotando cada transformação; a indexação
   * não passa por aqui, ela usa o caminho rápido com cache.
   */
  explicar(palavra) {
    const original = String(palavra).toLowerCase().trim();
    const etapas = [];
    let atual = original;

    if (atual.length < 3) {
      const curto = RSLP.semAcento(atual);
      if (curto !== atual) etapas.push({ passo: 'acentos', de: atual, para: curto });
      return { palavra: original, radical: curto, etapas };
    }

    const registrar = (nome, regras, condicao) => {
      if (condicao === false) return false;
      const [depois, mudou] = RSLP.aplicar(atual, regras);
      if (mudou) etapas.push({ passo: nome, de: atual, para: depois });
      atual = depois;
      return mudou;
    };

    registrar('plural', REGRAS_PLURAL, atual.endsWith('s'));
    registrar('feminino', REGRAS_FEMININO, atual.endsWith('a'));
    registrar('advérbio', REGRAS_ADVERBIO);
    registrar('aumentativo', REGRAS_AUMENTATIVO);

    if (!registrar('nominal', REGRAS_NOMINAL)) {
      if (!registrar('verbal', REGRAS_VERBAL)) {
        registrar('vogal temática', REGRAS_VOGAL);
      }
    }

    const radical = RSLP.semAcento(atual);
    if (radical !== atual) {
      etapas.push({ passo: 'acentos', de: atual, para: radical });
    }
    return { palavra: original, radical, etapas };
  }

  /** [chamadas, acertos, taxa] do cache de memoização. */
  estatisticasCache() {
    if (!this.chamadas) return [0, 0, 0];
    return [this.chamadas, this.acertosCache, this.acertosCache / this.chamadas];
  }
}

// Instância compartilhada, como o `_PADRAO` do módulo Python.
const PADRAO = new RSLP();

export const radical = (palavra) => PADRAO.radicalizar(palavra);

export { RSLP };
