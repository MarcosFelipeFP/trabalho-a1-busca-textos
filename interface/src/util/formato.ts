/*
 * Números no formato brasileiro. O projetor da sala não perdoa "1,234.5":
 * separador de milhar é ponto, decimal é vírgula, e unidade não se separa do
 * número na quebra de linha.
 */

const INTEIRO = new Intl.NumberFormat('pt-BR');
export const NBSP = ' ';

export function numero(valor: number): string {
  return INTEIRO.format(valor);
}

export function decimal(valor: number, casas = 1): string {
  return valor.toLocaleString('pt-BR', {
    minimumFractionDigits: casas,
    maximumFractionDigits: casas,
  });
}

export function porcentagem(fracao: number, casas = 1): string {
  return `${decimal(fracao * 100, casas)}${NBSP}%`;
}

/** Valor e unidade de uma duração, escolhendo a unidade que se lê melhor. */
export function partesDoTempo(segundos: number): [string, string] {
  if (!Number.isFinite(segundos) || segundos <= 0) return ['0', 'µs'];
  if (segundos < 1e-6) return [decimal(segundos * 1e9, 0), 'ns'];
  if (segundos < 1e-3) {
    const micro = segundos * 1e6;
    return [decimal(micro, micro < 100 ? 1 : 0), 'µs'];
  }
  if (segundos < 1) {
    const mili = segundos * 1e3;
    return [decimal(mili, mili < 100 ? 1 : 0), 'ms'];
  }
  return [decimal(segundos, 2), 's'];
}

export function tempo(segundos: number): string {
  const [valor, unidade] = partesDoTempo(segundos);
  return `${valor}${NBSP}${unidade}`;
}

/** "2.300×" ou "6,7×": razões grandes dispensam casa decimal. */
export function vezes(razao: number): string {
  if (!Number.isFinite(razao) || razao <= 0) return '—';
  return `${razao >= 100 ? numero(Math.round(razao)) : decimal(razao, 1)}×`;
}

export function plural(quantidade: number, singular: string, varios: string): string {
  return `${numero(quantidade)}${NBSP}${quantidade === 1 ? singular : varios}`;
}

export function kilobytes(bytes: number): string {
  return `${decimal(bytes / 1024, 1)}${NBSP}KB`;
}

/** Nome de arquivo legível: "banco_dados.txt" vira "banco dados". */
export function tituloDoDocumento(nome: string): string {
  return nome.replace(/\.txt$/i, '').replace(/_/g, ' ');
}
