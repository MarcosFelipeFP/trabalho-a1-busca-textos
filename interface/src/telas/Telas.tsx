/*
 * As telas que espelham os menus do enunciado, ao lado da busca:
 *
 *   Autocomplete (Parte I)  seções 2.3 e 2.4 -- buscar palavra, buscar por
 *                           prefixo e inserir palavra, sobre o léxico;
 *   Documentos              opção 4 do menu da seção 3.8;
 *   Estatísticas            opção 5 do menu: as estatísticas obrigatórias da
 *                           seção 3.9, com o tempo de cada consulta.
 *
 * Os dados vêm do mesmo motor que responde a busca, Python ou JavaScript.
 */
import { useEffect, useRef, useState } from 'react';

import { tituloDe } from '../dados';
import { useMotor } from '../motor/contexto';
import type {
  RespostaAutocomplete,
  RespostaEstatisticas,
  RespostaInsercao,
  RespostaLexico,
} from '../motor/tipos';
import { decimal, kilobytes, numero, tempo } from '../util/formato';

export type Tela = 'parte1' | 'busca' | 'documentos' | 'estatisticas';

// Na ordem do enunciado: a Parte I, a Parte II e as opções 4 e 5 do menu dela.
const TELAS: { valor: Tela; titulo: string }[] = [
  { valor: 'parte1', titulo: 'Autocomplete (Parte I)' },
  { valor: 'busca', titulo: 'Busca (Parte II)' },
  { valor: 'documentos', titulo: 'Documentos' },
  { valor: 'estatisticas', titulo: 'Estatísticas' },
];

/** Custo previsto de cada consulta, o mesmo que o terminal mostra (seção 3.9). */
const CUSTO: Record<string, string> = {
  palavra: 'O(1) por termo',
  prefixo: 'O(m + p)',
  sequencia: 'O(N)',
};
const NOME: Record<string, string> = { palavra: 'palavra', prefixo: 'prefixo', sequencia: 'sequência' };
const LEGENDA_DO_CUSTO = 'm = tamanho da palavra ou do prefixo; p = nós da Trie abaixo do prefixo; '
  + 'N = caracteres de todos os documentos.';

// A Parte I lista TODAS as palavras do prefixo (seção 2.3); a tela as mostra
// em páginas do mesmo tamanho que o terminal usa, sem cortar nenhuma.
const POR_PAGINA = 40;

const BOTAO = 'rounded-full border border-linha px-3.5 py-1.5 text-[0.88rem] text-grafite transition-colors hover:bg-nevoa hover:text-tinta';

export function Navegacao({ atual, aoTrocar }: { atual: Tela; aoTrocar: (tela: Tela) => void }) {
  return (
    <nav aria-label="Telas do trabalho" className="flex flex-wrap items-center gap-1 text-[0.82rem] text-cinza">
      {TELAS.map((tela) => (
        <button
          key={tela.valor}
          type="button"
          onClick={() => aoTrocar(tela.valor)}
          aria-current={atual === tela.valor ? 'page' : undefined}
          className={`rounded-full px-2.5 py-1 transition-colors ${
            atual === tela.valor ? 'bg-nevoa font-medium text-tinta' : 'hover:bg-nevoa hover:text-tinta'
          }`}
        >
          {tela.titulo}
        </button>
      ))}
    </nav>
  );
}

function Titulo({ children, subtitulo }: { children: React.ReactNode; subtitulo?: React.ReactNode }) {
  return (
    <div className="mb-6">
      <h2 className="text-[1.5rem] font-semibold tracking-tight text-tinta">{children}</h2>
      {subtitulo && <p className="numeros mt-1 text-[0.88rem] text-cinza">{subtitulo}</p>}
    </div>
  );
}

function TempoDaOperacao({ segundos, custo, rotulo = 'Tempo da consulta', unica = false }: {
  segundos: number;
  custo: string;
  rotulo?: string;
  /** Medida de uma execução só, sem as repetições que o relógio grosso pede. */
  unica?: boolean;
}) {
  // O relógio do navegador conta de 0,1 em 0,1 ms. A inserção não pode ser
  // repetida para medir -- a segunda já não insere nada --, e numa execução
  // só a leitura sai 0 ou 0,1 ms, nenhuma delas o tempo real.
  const abaixoDoRelogio = unica && segundos < 2e-4;
  return (
    <p className="numeros mt-4 text-[0.84rem] text-cinza">
      {rotulo}: {abaixoDoRelogio ? 'abaixo do que o relógio do navegador mede (0,1 ms)' : tempo(segundos)}
      {' · '}custo previsto {custo}
    </p>
  );
}

/* ------------------------------------------------------------- Parte I */

type Operacao = 'buscar' | 'prefixo' | 'inserir';

// As três opções do menu da seção 2.4, com as perguntas do terminal.
const OPERACOES: { valor: Operacao; titulo: string; pergunta: string }[] = [
  { valor: 'buscar', titulo: '1 · Buscar palavra', pergunta: 'Digite a palavra' },
  { valor: 'prefixo', titulo: '2 · Buscar por prefixo', pergunta: 'Digite o prefixo' },
  { valor: 'inserir', titulo: '3 · Inserir nova palavra', pergunta: 'Digite a nova palavra' },
];

type RespostaParteUm =
  | { tipo: 'buscar'; r: RespostaLexico; acentuadas: string[]; comecos: string[] }
  | { tipo: 'prefixo'; r: RespostaAutocomplete }
  | { tipo: 'inserir'; r: RespostaInsercao };

export function ParteUm() {
  const { motor } = useMotor();
  const [texto, setTexto] = useState('');
  // Como no terminal, a opção escolhida continua ativa: cada Enter a executa
  // com a palavra da caixa, até se escolher outra. Escolher não executa nada,
  // para a inserção nunca gravar uma palavra que ficou na caixa por acaso.
  const [operacao, setOperacao] = useState<Operacao>('prefixo');
  const [cadastradas, setCadastradas] = useState<number | null>(null);
  const [resposta, setResposta] = useState<RespostaParteUm | null>(null);
  const [mostradas, setMostradas] = useState(POR_PAGINA);
  const [erro, setErro] = useState<string | null>(null);
  const campo = useRef<HTMLInputElement>(null);

  useEffect(() => campo.current?.focus(), []);

  useEffect(() => {
    let ativo = true;
    motor.estado().then((estado) => ativo && setCadastradas(estado.parte1.palavras)).catch(() => undefined);
    return () => {
      ativo = false;
    };
  }, [motor]);

  function escolher(tipo: Operacao) {
    setOperacao(tipo);
    // O texto fica selecionado: digitar já o substitui, e o Enter o reaproveita.
    campo.current?.focus();
    campo.current?.select();
  }

  async function executar(tipo: Operacao) {
    const palavra = texto.trim();
    if (!palavra) return;
    setErro(null);
    try {
      if (tipo === 'buscar') {
        const r = await motor.buscarNoLexico(palavra);
        // Fora do tempo da busca exata, como no terminal: as palavras do mesmo
        // caminho, que só diferem no acento, e -- quando a digitada não existe
        // -- as que a continuam. As do caminho saem primeiro na Trie.
        const digitada = palavra.toLowerCase().normalize('NFC');
        const acentuadas = r.formas.filter((forma) => forma !== digitada);
        const comecos = r.existe
          ? []
          : (await motor.autocompletar(palavra, 5 + acentuadas.length)).palavras.slice(acentuadas.length);
        setResposta({ tipo, r, acentuadas, comecos });
      } else if (tipo === 'prefixo') {
        setMostradas(POR_PAGINA);
        setResposta({ tipo, r: await motor.autocompletar(palavra, null) });
      } else {
        const r = await motor.inserirNoLexico(palavra);
        setCadastradas(r.palavras);
        setResposta({ tipo, r });
      }
    } catch (falha) {
      setErro(falha instanceof Error ? falha.message : String(falha));
    }
  }

  const pergunta = OPERACOES.find((opcao) => opcao.valor === operacao)!.pergunta;

  return (
    <section className="max-w-[680px]">
      <Titulo subtitulo={cadastradas !== null && <>Palavras cadastradas: {numero(cadastradas)}</>}>
        Autocomplete com Trie
      </Titulo>

      <div className="flex flex-wrap gap-2">
        {OPERACOES.map((opcao) => (
          <button
            key={opcao.valor}
            type="button"
            onClick={() => escolher(opcao.valor)}
            aria-pressed={operacao === opcao.valor}
            className={operacao === opcao.valor
              ? 'rounded-full border border-tinta bg-tinta px-3.5 py-1.5 text-[0.88rem] font-medium text-fundo'
              : BOTAO}
          >
            {opcao.titulo}
          </button>
        ))}
      </div>

      <form
        className="mt-4"
        onSubmit={(evento) => {
          evento.preventDefault();
          void executar(operacao);
        }}
      >
        <input
          ref={campo}
          value={texto}
          onChange={(evento) => setTexto(evento.target.value)}
          placeholder={`${pergunta} e tecle Enter`}
          aria-label={pergunta}
          spellCheck={false}
          autoComplete="off"
          autoCapitalize="off"
          className="w-full rounded-full border border-linha bg-fundo px-5 py-3 text-[1rem] text-tinta outline-none placeholder:text-cinza focus:border-grafite"
        />
      </form>

      {erro && <p className="mt-5 text-grafite">A operação falhou: {erro}</p>}

      {resposta?.tipo === 'buscar' && (
        <div className="mt-6 space-y-1.5 text-[1rem] text-grafite">
          <p>
            A palavra “{resposta.r.palavra}”{' '}
            <b className="text-tinta">{resposta.r.existe ? 'existe' : 'não está'}</b> na Trie.
          </p>
          {resposta.acentuadas.length > 0 && <p>Com outra acentuação: {resposta.acentuadas.join(', ')}.</p>}
          {resposta.comecos.length > 0 && <p>Começam assim: {resposta.comecos.join(', ')}.</p>}
          {resposta.r.aproximadas.length > 0 && (
            <p>Você quis dizer: {resposta.r.aproximadas.map(([palavra]) => palavra).join(', ')}?</p>
          )}
          <TempoDaOperacao segundos={resposta.r.tempo} custo="O(m)" />
        </div>
      )}

      {resposta?.tipo === 'prefixo' && (
        <div className="mt-6">
          {resposta.r.palavras.length === 0 ? (
            <p className="text-grafite">Nenhuma palavra começa com “{resposta.r.prefixo}”.</p>
          ) : (
            <>
              <p className="numeros mb-2 text-[0.84rem] font-medium text-cinza">
                Palavras encontradas: {numero(resposta.r.palavras.length)}
              </p>
              <ul className="columns-2 gap-6 text-[0.95rem] text-grafite sm:columns-3">
                {resposta.r.palavras.slice(0, mostradas).map((palavra) => <li key={palavra}>{palavra}</li>)}
              </ul>
              {mostradas < resposta.r.palavras.length && (
                <button type="button" className={`${BOTAO} numeros mt-3`} onClick={() => setMostradas((n) => n + POR_PAGINA)}>
                  Mostrar mais · {numero(mostradas)} de {numero(resposta.r.palavras.length)} palavras
                </button>
              )}
            </>
          )}
          <TempoDaOperacao segundos={resposta.r.tempo} custo="O(m + p)" />
        </div>
      )}

      {resposta?.tipo === 'inserir' && (
        <div className="mt-6 text-[1rem] text-grafite">
          <p>
            {resposta.r.nova
              ? <>“{resposta.r.palavra}” inserida. Total agora: {numero(resposta.r.palavras)} palavras.</>
              : <>“{resposta.r.palavra}” já estava cadastrada.</>}
          </p>
          <TempoDaOperacao
            segundos={resposta.r.tempo}
            custo="O(m)"
            rotulo="Tempo da inserção"
            unica={resposta.r.repeticoes === 1}
          />
        </div>
      )}
    </section>
  );
}

/* ---------------------------------------------------------- Documentos */

export function Documentos({ aoAbrir }: { aoAbrir: (documento: string) => void }) {
  const { aplicacao } = useMotor();
  const linhas = aplicacao.mecanismo.resumoDocumentos();
  return (
    <section className="max-w-[760px]">
      <Titulo subtitulo={`${numero(linhas.length)} arquivos .txt, lidos da pasta documentos/ sem nenhum nome fixado no código`}>
        Documentos indexados
      </Titulo>
      <table className="numeros w-full text-left text-[0.9rem]">
        <thead className="text-[0.78rem] text-cinza">
          <tr className="border-b border-linha">
            <th className="py-2 font-medium">Documento</th>
            <th className="py-2 text-right font-medium">Tamanho</th>
            <th className="py-2 pl-4 text-right font-medium">Palavras indexadas</th>
          </tr>
        </thead>
        <tbody className="text-grafite">
          {linhas.map((linha) => (
            <tr key={linha.documento} className="border-b border-linha">
              <td className="py-2">
                <button
                  type="button"
                  onClick={() => aoAbrir(linha.documento)}
                  className="text-left text-tinta decoration-linha decoration-2 underline-offset-4 hover:underline"
                >
                  {tituloDe(linha.documento)}
                </button>
                <span className="block text-[0.78rem] text-cinza sm:ml-2 sm:inline">{linha.documento}</span>
              </td>
              <td className="py-2 text-right">{kilobytes(linha.bytes)}</td>
              <td className="py-2 pl-4 text-right">{numero(linha.tokens)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

/* -------------------------------------------------------- Estatísticas */

/** "380 vezes" ou "2,5 vezes": a razão entre dois tempos médios. */
function vezesOTempo(razao: number): string {
  return `${razao >= 10 ? numero(Math.round(razao)) : decimal(razao, 1)} vezes`;
}

export function Estatisticas() {
  const { motor } = useMotor();
  const [dados, setDados] = useState<RespostaEstatisticas | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    let ativo = true;
    motor.estatisticas()
      .then((resposta) => ativo && setDados(resposta))
      .catch((falha) => ativo && setErro(String(falha)));
    return () => {
      ativo = false;
    };
  }, [motor]);

  if (erro) return <p className="text-grafite">Não foi possível ler as estatísticas: {erro}</p>;
  if (!dados) return <p className="text-cinza">Carregando…</p>;

  const obrigatorias: [string, string][] = [
    ['Documentos processados', numero(dados.corpus.documentos)],
    ['Palavras após a tokenização', numero(dados.corpus.palavras_brutas)],
    ['Termos distintos', numero(dados.corpus.termos)],
    ['Palavras armazenadas na Trie', numero(dados.corpus.palavras_na_trie)],
    ['Tempo de construção da Trie', dados.construcao.trie],
    ['Tempo de construção do índice invertido', dados.construcao.indice],
  ];
  const consultas = dados.consultas.cada_consulta;

  // A medição confrontada com a análise, como no terminal: quantas vezes uma
  // varredura O(N) do texto custa uma consulta O(1) ao hash, nesta sessão.
  const { palavra, sequencia } = dados.consultas.por_tipo;
  const razao = palavra && sequencia && palavra.media_segundos > 0
    ? sequencia.media_segundos / palavra.media_segundos
    : null;

  return (
    <section className="numeros max-w-[760px]">
      <Titulo subtitulo={`As estatísticas obrigatórias da seção 3.9, medidas pelo motor ${motor.nome}`}>
        Estatísticas
      </Titulo>

      <dl className="grid grid-cols-[1fr_auto] gap-x-8 gap-y-2 text-[0.95rem]">
        {obrigatorias.map(([rotulo, valor]) => (
          <div key={rotulo} className="contents">
            <dt className="text-grafite">{rotulo}</dt>
            <dd className="text-right text-tinta">{valor}</dd>
          </div>
        ))}
      </dl>

      <h3 className="mb-3 mt-10 text-[1.05rem] font-semibold text-tinta">
        Consultas realizadas{consultas.length > 0 && ` (${numero(consultas.length)})`}
      </h3>
      {consultas.length === 0 ? (
        <p className="text-[0.95rem] text-cinza">Nenhuma consulta feita ainda nesta sessão. Use a Busca e volte aqui.</p>
      ) : (
        <>
          <table className="w-full text-left text-[0.88rem]">
            <thead className="text-[0.78rem] text-cinza">
              <tr className="border-b border-linha">
                <th className="py-2 font-medium">Tipo</th>
                <th className="py-2 text-right font-medium">Consultas</th>
                <th className="py-2 text-right font-medium">Tempo médio</th>
                <th className="py-2 pl-6 font-medium">Custo previsto</th>
              </tr>
            </thead>
            <tbody className="text-grafite">
              {Object.entries(dados.consultas.por_tipo).map(([tipo, resumo]) => (
                <tr key={tipo} className="border-b border-linha">
                  <td className="py-2">{NOME[tipo] ?? tipo}</td>
                  <td className="py-2 text-right">{numero(resumo.quantidade)}</td>
                  <td className="py-2 text-right">{resumo.media}</td>
                  <td className="py-2 pl-6">{CUSTO[tipo] ?? ''}</td>
                </tr>
              ))}
            </tbody>
          </table>

          {razao !== null && (
            <p className="mt-4 text-[0.92rem] text-grafite">
              Em média, a busca por sequência levou <b className="font-semibold text-tinta">{vezesOTempo(razao)}</b> o
              tempo da busca por palavra: O(N) contra O(1).
            </p>
          )}
          <p className="mt-2 text-[0.8rem] text-cinza">{LEGENDA_DO_CUSTO}</p>

          <h4 className="mb-2 mt-8 text-[0.84rem] font-medium text-cinza">Tempo de cada consulta, na ordem em que foram feitas</h4>
          <ol className="space-y-1 text-[0.88rem] text-grafite">
            {consultas.map((consulta, posicao) => (
              <li key={posicao} className="flex gap-3">
                <span className="w-8 shrink-0 text-right text-cinza">{posicao + 1}.</span>
                <span className="w-20 shrink-0 text-cinza">{NOME[consulta.tipo] ?? consulta.tipo}</span>
                <span className="min-w-0 flex-1 truncate">“{consulta.texto}” · {numero(consulta.resultados)} resultado(s)</span>
                <span className="shrink-0 text-tinta">{consulta.tempo}</span>
              </li>
            ))}
          </ol>
        </>
      )}
    </section>
  );
}
