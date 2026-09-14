/*
 * A lista de resultados e o leitor que abre por cima dela.
 */
import { AnimatePresence, motion } from 'motion/react';
import { X } from 'lucide-react';
import { useEffect, useMemo, useRef } from 'react';

import { normalizar } from '../algoritmos/trie.js';
import { tituloDe } from '../dados';
import { useMotor } from '../motor/contexto';
import type { RespostaPalavra, RespostaPrefixo, RespostaSequencia } from '../motor/tipos';
import { decimal, numero, plural, tempo } from '../util/formato';
import { extrairTrecho, marcarTexto, Segmentos, type Criterio } from './trechos';

export type Resultado =
  | { modo: 'palavra'; resposta: RespostaPalavra }
  | { modo: 'prefixo'; resposta: RespostaPrefixo }
  | { modo: 'sequencia'; resposta: RespostaSequencia };

export interface Abertura {
  documento: string;
  criterio: Criterio;
}

interface Item {
  documento: string;
  detalhe: string;
}

export function Resultados({
  resultado,
  aoAbrir,
  aoBuscar,
}: {
  resultado: Resultado;
  aoAbrir: (abertura: Abertura) => void;
  aoBuscar: (texto: string) => void;
}) {
  const { aplicacao, motor } = useMotor();
  const preprocessador = aplicacao.mecanismo.preprocessador;

  const { criterio, itens, resumo } = useMemo(() => {
    if (resultado.modo === 'palavra') {
      const r = resultado.resposta;
      const varios = r.termos.length > 1;
      return {
        criterio: {
          tipo: 'radicais',
          radicais: new Set(r.termos.map((termo) => termo.radical)),
          radicalizar: (palavra: string) => preprocessador.radicalizar(palavra),
        } as Criterio,
        itens: r.documentos.map(([documento, nota]): Item => ({
          documento,
          detalhe: [
            plural(r.frequencias[documento] ?? 0, 'ocorrência', 'ocorrências'),
            varios ? `${r.cobertura[documento]} de ${r.termos.length} termos` : null,
            `BM25 ${decimal(nota, 2)}`,
          ].filter(Boolean).join(' · '),
        })),
        resumo: r.documentos.length
          ? `${plural(r.documentos.length, 'documento', 'documentos')}${varios ? ` · ${numero(r.todos.length)} com todos os termos` : ''} · ${tempo(r.tempo)} pelo índice invertido`
          : `Nenhum documento · ${tempo(r.tempo)} pelo índice invertido`,
      };
    }
    if (resultado.modo === 'prefixo') {
      const r = resultado.resposta;
      return {
        criterio: { tipo: 'prefixo', chave: normalizar(r.prefixo) } as Criterio,
        itens: r.ranking.map(([documento, nota]): Item => ({
          documento,
          detalhe: `${plural(r.termos.filter((termo) => r.por_termo[termo]?.includes(documento)).length, 'termo', 'termos')} do prefixo · BM25 ${decimal(nota, 2)}`,
        })),
        resumo: `${plural(r.total_disponivel, 'palavra começa', 'palavras começam')} com “${r.prefixo}” · ${plural(r.documentos.length, 'documento', 'documentos')} · ${tempo(r.tempo)} pela Trie`,
      };
    }
    const r = resultado.resposta;
    return {
      criterio: { tipo: 'sequencia', trecho: r.sequencia } as Criterio,
      itens: r.resultados.map((item): Item => ({
        documento: item.documento,
        detalhe: plural(item.ocorrencias, 'ocorrência', 'ocorrências'),
      })),
      resumo: `${plural(r.total_ocorrencias, 'ocorrência', 'ocorrências')} em ${plural(r.resultados.length, 'documento', 'documentos')} · ${tempo(r.tempo)} lendo o texto com KMP`,
    };
  }, [resultado, preprocessador]);

  return (
    <div>
      <p className="numeros text-[0.84rem] text-cinza">
        {resumo}
        {motor.nome === 'Python' && ' · Python'}
      </p>

      {resultado.modo === 'palavra' && resultado.resposta.correcao && (
        <p className="mt-4 text-[1.02rem] text-grafite">
          Você quis dizer{' '}
          <button
            type="button"
            onClick={() => aoBuscar(resultado.resposta.correcao!)}
            className="font-semibold text-tinta underline decoration-marca decoration-[3px] underline-offset-4 hover:decoration-tinta"
          >
            {resultado.resposta.correcao}
          </button>
          ?
        </p>
      )}

      {resultado.modo === 'palavra' && resultado.resposta.termos.length === 0 && resultado.resposta.ignorados.length > 0 && (
        <p className="mt-4 text-[1rem] text-grafite">
          “{resultado.resposta.ignorados.join(' ')}” só tem palavras que o índice descarta (stopwords). Tente outro termo.
        </p>
      )}

      {resultado.modo === 'prefixo' && resultado.resposta.termos.length > 0 && (
        <div className="mt-5">
          <p className="mb-2 text-[0.8rem] font-medium text-cinza">Palavras encontradas na Trie</p>
          <ul className="flex flex-wrap gap-1.5">
            {resultado.resposta.termos.slice(0, 28).map((termo) => (
              <li key={termo}>
                <button
                  type="button"
                  onClick={() => aoBuscar(termo)}
                  className="rounded-full bg-nevoa px-3 py-1 text-[0.88rem] text-grafite transition-colors hover:bg-linha hover:text-tinta"
                >
                  <b className="font-semibold text-tinta">{Array.from(termo).slice(0, Array.from(resultado.resposta.prefixo).length).join('')}</b>
                  {Array.from(termo).slice(Array.from(resultado.resposta.prefixo).length).join('')}
                </button>
              </li>
            ))}
            {resultado.resposta.total_disponivel > 28 && (
              <li className="px-2 py-1 text-[0.85rem] text-cinza">+{numero(resultado.resposta.total_disponivel - 28)}</li>
            )}
          </ul>
        </div>
      )}

      {itens.length > 0 ? (
        <ol className="mt-7 space-y-7">
          {itens.map((item, posicao) => (
            <motion.li
              key={item.documento}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.22, delay: Math.min(posicao, 8) * 0.03 }}
            >
              <ItemDeResultado item={item} criterio={criterio} aoAbrir={aoAbrir} />
            </motion.li>
          ))}
        </ol>
      ) : (
        !(resultado.modo === 'palavra' && resultado.resposta.correcao) && (
          <p className="mt-6 text-[1rem] text-grafite">Nenhum documento encontrado.</p>
        )
      )}
    </div>
  );
}

function ItemDeResultado({ item, criterio, aoAbrir }: { item: Item; criterio: Criterio; aoAbrir: (abertura: Abertura) => void }) {
  const { aplicacao } = useMotor();
  const trecho = useMemo(
    () => extrairTrecho(aplicacao.mecanismo.conteudo.get(item.documento) ?? '', criterio),
    [aplicacao, item.documento, criterio],
  );

  return (
    <article>
      <button type="button" onClick={() => aoAbrir({ documento: item.documento, criterio })} className="group block text-left">
        <h2 className="text-[1.2rem] font-semibold leading-snug tracking-[-0.01em] text-tinta decoration-linha decoration-2 underline-offset-4 group-hover:underline">
          {tituloDe(item.documento)}
        </h2>
      </button>
      <p className="mt-0.5 text-[0.8rem] text-cinza">
        {item.documento} · {item.detalhe}
      </p>
      {trecho && (
        <p className="mt-2 line-clamp-3 font-serif text-[0.98rem] leading-[1.7] text-grafite">
          <Segmentos segmentos={trecho} />
        </p>
      )}
    </article>
  );
}

/* ------------------------------------------------------------------- leitor */

export function Leitor({ abertura, aoFechar }: { abertura: Abertura | null; aoFechar: () => void }) {
  const { aplicacao } = useMotor();
  const corpo = useRef<HTMLDivElement>(null);

  const marcado = useMemo(() => {
    if (!abertura) return null;
    return marcarTexto(aplicacao.mecanismo.conteudo.get(abertura.documento) ?? '', abertura.criterio);
  }, [abertura, aplicacao]);

  useEffect(() => {
    if (!abertura) return undefined;
    const aoTeclar = (evento: KeyboardEvent) => evento.key === 'Escape' && aoFechar();
    window.addEventListener('keydown', aoTeclar);
    // Leva a primeira palavra realçada para o meio da tela.
    const relogio = setTimeout(() => corpo.current?.querySelector('mark')?.scrollIntoView({ block: 'center' }), 60);
    return () => {
      window.removeEventListener('keydown', aoTeclar);
      clearTimeout(relogio);
    };
  }, [abertura, aoFechar]);

  return (
    <AnimatePresence>
      {abertura && marcado && (
        <motion.div
          className="fixed inset-0 z-50 flex items-center justify-center bg-tinta/25 p-4 backdrop-blur-[2px] sm:p-8"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={aoFechar}
        >
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-label={tituloDe(abertura.documento)}
            className="flex max-h-full w-full max-w-[760px] flex-col overflow-hidden rounded-2xl bg-fundo shadow-[0_24px_80px_-24px_rgb(22_24_29/0.45)]"
            initial={{ y: 12, scale: 0.99 }}
            animate={{ y: 0, scale: 1 }}
            exit={{ y: 12, opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={(evento) => evento.stopPropagation()}
          >
            <header className="flex items-start justify-between gap-4 border-b border-linha px-7 py-5">
              <div>
                <h2 className="text-[1.35rem] font-semibold tracking-[-0.01em]">{tituloDe(abertura.documento)}</h2>
                <p className="mt-0.5 text-[0.82rem] text-cinza">
                  {abertura.documento} · {plural(marcado.total, 'trecho realçado', 'trechos realçados')}
                </p>
              </div>
              <button
                type="button"
                onClick={aoFechar}
                className="grid size-9 shrink-0 place-items-center rounded-full text-cinza hover:bg-nevoa hover:text-tinta"
                aria-label="Fechar"
              >
                <X className="size-5" />
              </button>
            </header>
            <div ref={corpo} className="overflow-y-auto px-7 py-6">
              <article className="whitespace-pre-line font-serif text-[1.05rem] leading-[1.8] text-tinta">
                <Segmentos segmentos={marcado.segmentos} />
              </article>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
