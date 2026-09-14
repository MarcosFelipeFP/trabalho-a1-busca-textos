/*
 * Uma página, uma busca.
 *
 * Antes da primeira consulta, só o nome e a caixa, no centro. Enquanto se
 * digita, a Trie sugere as palavras mais frequentes dos documentos (Parte I).
 * No Enter, a caixa sobe e os resultados aparecem embaixo (Parte II), com o
 * que foi encontrado realçado no trecho de cada documento.
 */
import { LayoutGroup, motion } from 'motion/react';
import { Search, X } from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import type { Aplicacao } from './algoritmos/mecanismo.js';
import { normalizar } from './algoritmos/trie.js';
import { Leitor, Resultados, type Abertura, type Resultado } from './busca/Resultados';
import { DADOS } from './dados';
import { construirAplicacao, ProvedorDoMotor, useMotor } from './motor/contexto';
import { numero, tempo } from './util/formato';

type Modo = 'palavra' | 'prefixo' | 'sequencia';

const MODOS: { valor: Modo; titulo: string; ajuda: string; exemplos: string[] }[] = [
  { valor: 'palavra', titulo: 'Palavra', ajuda: 'pelo índice invertido', exemplos: ['algoritmo', 'rede neural', 'algortimo'] },
  { valor: 'prefixo', titulo: 'Prefixo', ajuda: 'pela Trie', exemplos: ['comp', 'cripto'] },
  { valor: 'sequencia', titulo: 'Sequência', ajuda: 'com KMP no texto', exemplos: ['chave pública', 'O(n log n)'] },
];

type Pronta = { aplicacao: Aplicacao; segundos: number };
let construcao: Promise<Pronta> | null = null;

export function App() {
  const [pronta, setPronta] = useState<Pronta | null>(null);
  const [lidos, setLidos] = useState(0);

  useEffect(() => {
    let ativo = true;
    construcao ??= construirAplicacao((etapa) => {
      if (ativo && etapa.fase === 'leitura') setLidos(etapa.posicao);
    });
    construcao.then((resultado) => ativo && setPronta(resultado));
    return () => {
      ativo = false;
    };
  }, []);

  if (!pronta) {
    return (
      <Inicial
        caixa={<CaixaDeBusca valor="" aoMudar={() => undefined} aoBuscar={() => undefined} sugestoes={[]} desabilitada />}
        abas={null}
        rodape={`Preparando o índice · ${lidos} de ${DADOS.corpus.length} documentos`}
      />
    );
  }

  return (
    <ProvedorDoMotor aplicacao={pronta.aplicacao}>
      <Pagina segundos={pronta.segundos} />
    </ProvedorDoMotor>
  );
}

function Pagina({ segundos }: { segundos: number }) {
  const { aplicacao, motor, servidorNoAr, trocarMotor } = useMotor();
  const [consulta, setConsulta] = useState('');
  const [modo, setModo] = useState<Modo>('palavra');
  const [resultado, setResultado] = useState<Resultado | null>(null);
  const [abertura, setAbertura] = useState<Abertura | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  const buscar = useCallback(
    async (texto: string, qual: Modo = modo) => {
      const limpo = texto.trim();
      setConsulta(texto);
      if (!limpo) return;
      setErro(null);
      try {
        if (qual === 'palavra') setResultado({ modo: 'palavra', resposta: await motor.buscarPalavra(limpo) });
        else if (qual === 'prefixo') setResultado({ modo: 'prefixo', resposta: await motor.buscarPrefixo(limpo) });
        else setResultado({ modo: 'sequencia', resposta: await motor.buscarSequencia(limpo) });
      } catch (falha) {
        setErro(falha instanceof Error ? falha.message : String(falha));
      }
      window.scrollTo({ top: 0 });
    },
    [modo, motor],
  );

  // Sugestões da Trie para a última palavra digitada, das mais frequentes nos
  // documentos para as menos: é o autocomplete da Parte I.
  const sugestoes = useMemo(() => {
    if (modo !== 'palavra') return [];
    const partes = consulta.match(/^(.*?)(\S*)$/s);
    const antes = partes?.[1] ?? '';
    const ultima = partes?.[2] ?? '';
    if (!ultima) return [];
    const chave = normalizar(ultima);
    return aplicacao.mecanismo.trie
      .sugerir(ultima, 7)
      .map(([palavra]) => palavra)
      .filter((palavra) => normalizar(palavra) !== chave)
      .map((palavra) => antes + palavra);
  }, [consulta, modo, aplicacao]);

  function trocarModo(proximo: Modo) {
    setModo(proximo);
    if (resultado && consulta.trim()) void buscar(consulta, proximo);
  }

  const abas = (
    <div className="flex flex-wrap items-center gap-x-1 gap-y-2">
      {MODOS.map((opcao) => (
        <button
          key={opcao.valor}
          type="button"
          onClick={() => trocarModo(opcao.valor)}
          aria-pressed={modo === opcao.valor}
          className={`rounded-full px-3.5 py-1.5 text-[0.88rem] transition-colors ${
            modo === opcao.valor ? 'bg-tinta font-medium text-fundo' : 'text-grafite hover:bg-nevoa hover:text-tinta'
          }`}
        >
          {opcao.titulo}
        </button>
      ))}
      <span className="ml-2 text-[0.82rem] text-cinza">{MODOS.find((opcao) => opcao.valor === modo)?.ajuda}</span>
    </div>
  );

  const caixa = (
    <CaixaDeBusca
      valor={consulta}
      aoMudar={setConsulta}
      aoBuscar={(texto) => buscar(texto)}
      sugestoes={sugestoes}
      placeholder={modo === 'sequencia' ? 'Procure uma sequência exata no texto' : `Pesquise nos ${DADOS.corpus.length} documentos`}
    />
  );

  const seletorDeMotor = servidorNoAr && (
    <span className="inline-flex items-center gap-1 text-[0.8rem] text-cinza">
      Respondendo:
      {(['JavaScript', 'Python'] as const).map((nome) => (
        <button
          key={nome}
          type="button"
          onClick={() => trocarMotor(nome)}
          className={`rounded-full px-2 py-0.5 ${motor.nome === nome ? 'bg-nevoa font-medium text-tinta' : 'hover:text-tinta'}`}
        >
          {nome}
        </button>
      ))}
    </span>
  );

  return (
    <LayoutGroup>
      {!resultado ? (
        <Inicial
          caixa={caixa}
          abas={
            <>
              {abas}
              <p className="mt-6 text-[0.88rem] text-cinza">
                Experimente{' '}
                {MODOS.find((opcao) => opcao.valor === modo)!.exemplos.map((exemplo, indice) => (
                  <span key={exemplo}>
                    {indice > 0 && <span aria-hidden> · </span>}
                    <button type="button" onClick={() => buscar(exemplo)} className="text-grafite underline decoration-linha decoration-2 underline-offset-4 hover:text-tinta hover:decoration-tinta">
                      {exemplo}
                    </button>
                  </span>
                ))}
              </p>
            </>
          }
          rodape={
            <>
              {numero(DADOS.corpus.length)} documentos e {numero(aplicacao.mecanismo.vocabulario.size)} termos indexados em {tempo(segundos)}
              {seletorDeMotor && <span className="ml-3">{seletorDeMotor}</span>}
            </>
          }
        />
      ) : (
        <div className="min-h-dvh">
          <header className="sticky top-0 z-30 border-b border-linha bg-fundo/95 backdrop-blur">
            <div className="mx-auto flex max-w-[1080px] flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center sm:gap-8 sm:px-8">
              <button type="button" onClick={() => { setResultado(null); setConsulta(''); }} className="shrink-0 text-left">
                <Logo pequeno />
              </button>
              <div className="w-full max-w-[680px]">{caixa}</div>
            </div>
            <div className="mx-auto max-w-[1080px] px-5 pb-3 sm:px-8 sm:pl-[calc(2rem+9.6rem)]">
              <div className="flex flex-wrap items-center justify-between gap-2">
                {abas}
                {seletorDeMotor}
              </div>
            </div>
          </header>
          <main className="mx-auto max-w-[1080px] px-5 pb-24 pt-6 sm:px-8 sm:pl-[calc(2rem+9.6rem)]">
            <div className="max-w-[680px]">
              {erro ? <p className="text-[1rem] text-grafite">A busca falhou: {erro}</p> : <Resultados resultado={resultado} aoAbrir={setAbertura} aoBuscar={(texto) => buscar(texto)} />}
            </div>
          </main>
        </div>
      )}
      <Leitor abertura={abertura} aoFechar={() => setAbertura(null)} />
    </LayoutGroup>
  );
}

function Inicial({ caixa, abas, rodape }: { caixa: React.ReactNode; abas: React.ReactNode; rodape: React.ReactNode }) {
  return (
    <div className="flex min-h-dvh flex-col">
      <main className="flex flex-1 flex-col items-center justify-center px-5 pb-[12vh]">
        <motion.h1 layoutId="logo" className="mb-9">
          <Logo />
        </motion.h1>
        <div className="w-full max-w-[640px]">
          {caixa}
          <div className="mt-4 flex flex-col items-center">{abas}</div>
        </div>
      </main>
      <footer className="px-5 pb-6 text-center text-[0.8rem] leading-relaxed text-cinza">
        <p className="numeros">{rodape}</p>
        <p className="mt-1">
          Trabalho Prático A1 · Análise e Otimização de Sistemas · Universidade Veiga de Almeida
        </p>
        <p>Giovanni Cardoso Avallone Belo · Luana Cristina de Azevedo Celestino · Marcos Felipe Ferreira Pires · Pedro Henrique Graciliano Taka</p>
      </footer>
    </div>
  );
}

/** O nome, com um traço de marca-texto em "textos". */
function Logo({ pequeno = false }: { pequeno?: boolean }) {
  return (
    <span className={`whitespace-nowrap font-semibold tracking-[-0.035em] text-tinta ${pequeno ? 'text-[1.2rem]' : 'text-[clamp(2.3rem,6vw,3.3rem)]'}`}>
      Busca em{' '}
      <span className="relative inline-block">
        <span aria-hidden className="absolute inset-x-[-0.14em] bottom-[0.1em] h-[0.42em] -rotate-1 rounded-[0.12em] bg-marca" />
        <span className="relative">textos</span>
      </span>
    </span>
  );
}

function CaixaDeBusca({
  valor,
  aoMudar,
  aoBuscar,
  sugestoes,
  desabilitada = false,
  placeholder = 'Preparando o índice…',
}: {
  valor: string;
  aoMudar: (valor: string) => void;
  aoBuscar: (valor: string) => void;
  sugestoes: string[];
  desabilitada?: boolean;
  placeholder?: string;
}) {
  const [aberta, setAberta] = useState(false);
  const [ativa, setAtiva] = useState(-1);
  const campo = useRef<HTMLInputElement>(null);
  const mostrar = aberta && sugestoes.length > 0;

  useEffect(() => setAtiva(-1), [valor]);
  useEffect(() => {
    if (!desabilitada) campo.current?.focus();
  }, [desabilitada]);

  function escolher(texto: string) {
    setAberta(false);
    aoBuscar(texto);
  }

  return (
    <motion.div layoutId="caixa" className="relative" transition={{ type: 'spring', stiffness: 380, damping: 36 }}>
      <form
        role="search"
        onSubmit={(evento) => {
          evento.preventDefault();
          escolher(ativa >= 0 && mostrar ? sugestoes[ativa] : valor);
        }}
        className={`flex h-14 items-center gap-3 border bg-fundo px-5 transition-shadow ${
          mostrar ? 'rounded-t-[1.6rem] border-linha border-b-transparent shadow-[0_10px_30px_-12px_rgb(22_24_29/0.22)]'
            : 'rounded-[1.6rem] border-linha shadow-[0_2px_10px_-4px_rgb(22_24_29/0.12)] focus-within:shadow-[0_10px_30px_-12px_rgb(22_24_29/0.22)]'
        }`}
      >
        <Search aria-hidden className="size-5 shrink-0 text-cinza" />
        <input
          ref={campo}
          type="text"
          value={valor}
          disabled={desabilitada}
          placeholder={placeholder}
          spellCheck={false}
          autoComplete="off"
          autoCapitalize="off"
          enterKeyHint="search"
          aria-label="Consulta"
          onChange={(evento) => {
            aoMudar(evento.target.value);
            setAberta(true);
          }}
          onBlur={() => setTimeout(() => setAberta(false), 120)}
          onKeyDown={(evento) => {
            if (evento.key === 'ArrowDown' && mostrar) {
              evento.preventDefault();
              setAtiva((atual) => (atual + 1) % sugestoes.length);
            } else if (evento.key === 'ArrowUp' && mostrar) {
              evento.preventDefault();
              setAtiva((atual) => (atual <= 0 ? sugestoes.length - 1 : atual - 1));
            } else if (evento.key === 'Escape') {
              setAberta(false);
            }
          }}
          className="h-full min-w-0 flex-1 bg-transparent text-[1.08rem] text-tinta outline-none placeholder:text-cinza disabled:cursor-wait"
        />
        {valor && (
          <button type="button" onClick={() => { aoMudar(''); campo.current?.focus(); }} className="grid size-8 place-items-center rounded-full text-cinza hover:bg-nevoa hover:text-tinta" aria-label="Limpar">
            <X className="size-4" />
          </button>
        )}
      </form>

      {mostrar && (
        <ul
          role="listbox"
          className="absolute inset-x-0 top-full z-40 overflow-hidden rounded-b-[1.6rem] border border-t-0 border-linha bg-fundo pb-2 shadow-[0_18px_30px_-16px_rgb(22_24_29/0.22)]"
        >
          <li aria-hidden className="mx-5 mb-1 border-t border-linha" />
          {sugestoes.map((sugestao, indice) => {
            const digitado = valor.length <= sugestao.length ? valor : '';
            return (
              <li key={sugestao} role="option" aria-selected={indice === ativa}>
                <button
                  type="button"
                  onMouseDown={(evento) => evento.preventDefault()}
                  onClick={() => escolher(sugestao)}
                  onMouseEnter={() => setAtiva(indice)}
                  className={`flex w-full items-center gap-3 px-5 py-2 text-left text-[1rem] ${indice === ativa ? 'bg-nevoa' : ''}`}
                >
                  <Search aria-hidden className="size-4 shrink-0 text-cinza" />
                  <span className="truncate text-grafite">
                    {digitado}
                    <b className="font-semibold text-tinta">{sugestao.slice(digitado.length)}</b>
                  </span>
                </button>
              </li>
            );
          })}
          <li className="px-5 pt-1 text-[0.72rem] text-cinza">sugestões da Trie, das mais frequentes nos documentos</li>
        </ul>
      )}
    </motion.div>
  );
}
