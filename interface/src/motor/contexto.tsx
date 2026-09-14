import { createContext, useContext, useEffect, useMemo, useState } from 'react';

import { Aplicacao, type EtapaDeConstrucao } from '../algoritmos/mecanismo.js';
import { DADOS } from '../dados';
import { MotorLocal, MotorServidor, servidorDisponivel } from './motores';
import type { Motor } from './tipos';

interface ValorDoMotor {
  /** Os algoritmos do navegador, sempre construídos: o texto dos documentos
   *  e as sugestões enquanto se digita saem deles. */
  aplicacao: Aplicacao;
  motor: Motor;
  servidorNoAr: boolean;
  trocarMotor(nome: Motor['nome']): void;
}

const Contexto = createContext<ValorDoMotor | null>(null);

export function ProvedorDoMotor({ aplicacao, children }: { aplicacao: Aplicacao; children: React.ReactNode }) {
  const local = useMemo(() => new MotorLocal(aplicacao), [aplicacao]);
  const [servidor, setServidor] = useState<MotorServidor | null>(null);
  const [nome, setNome] = useState<Motor['nome']>('JavaScript');

  useEffect(() => {
    let ativo = true;
    servidorDisponivel().then((noAr) => {
      if (ativo && noAr) setServidor(new MotorServidor());
    });
    return () => {
      ativo = false;
    };
  }, []);

  const valor = useMemo<ValorDoMotor>(
    () => ({
      aplicacao,
      motor: nome === 'Python' && servidor ? servidor : local,
      servidorNoAr: servidor !== null,
      trocarMotor: setNome,
    }),
    [aplicacao, local, servidor, nome],
  );

  return <Contexto.Provider value={valor}>{children}</Contexto.Provider>;
}

export function useMotor(): ValorDoMotor {
  const valor = useContext(Contexto);
  if (!valor) throw new Error('useMotor fora do ProvedorDoMotor');
  return valor;
}

/* ---------------------------------------------------------------- construção */

const ceder = () => new Promise<void>((resolver) => setTimeout(resolver, 0));

/**
 * Aquecimento do compilador JIT, fora de qualquer cronômetro.
 *
 * O JavaScript começa interpretando uma função e só a compila depois de vê-la
 * rodar algumas vezes. Sem aquecer, a PRIMEIRA consulta mediria o compilador
 * trabalhando: 70 µs onde as seguintes dão 5 µs. O histórico que o aquecimento
 * deixa no mecanismo é apagado em seguida.
 */
function aquecer(aplicacao: Aplicacao): void {
  const palavras = ['algoritmo', 'rede neural', 'algortimo', 'computação'];
  const prefixos = ['c', 'comp', 'pro'];
  for (let volta = 0; volta < 2; volta += 1) {
    for (const palavra of palavras) aplicacao.mecanismo.buscarPalavra(palavra);
    for (const prefixo of prefixos) {
      aplicacao.mecanismo.buscarPrefixo(prefixo, 50);
      aplicacao.mecanismo.trie.sugerir(prefixo, 7);
    }
  }
  aplicacao.mecanismo.buscarSequencia('chave pública', true, 4);
  aplicacao.mecanismo.estatisticas.consultas.length = 0;
}

/**
 * Monta as estruturas, devolvendo o controle ao navegador entre as etapas para
 * a página poder mostrar o andamento. Devolve o tempo de construção medido
 * pelos cronômetros internos do mecanismo, que não contam as pausas.
 */
export async function construirAplicacao(
  aoProgredir: (etapa: EtapaDeConstrucao) => void,
): Promise<{ aplicacao: Aplicacao; segundos: number }> {
  await ceder();
  const aplicacao = new Aplicacao({ documentos: DADOS.corpus, lexico: DADOS.lexico, stopwords: DADOS.stopwords });

  const etapas = aplicacao.construirEmEtapas();
  let passo = etapas.next();
  while (!passo.done) {
    aoProgredir(passo.value);
    await ceder();
    passo = etapas.next();
  }

  aquecer(aplicacao);
  return { aplicacao, segundos: aplicacao.tempoTrie + aplicacao.mecanismo.estatisticas.tempoTotalConstrucao() };
}
