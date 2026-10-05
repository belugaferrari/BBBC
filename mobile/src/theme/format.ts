/** Formatacao pt-BR de moeda, percentual e data. */

const currency = new Intl.NumberFormat('pt-BR', {
  style: 'currency',
  currency: 'BRL',
});

const compact = new Intl.NumberFormat('pt-BR', {
  notation: 'compact',
  maximumFractionDigits: 1,
});

export function money(value: number | string | null | undefined): string {
  if (value === null || value === undefined) return '—';
  return currency.format(Number(value));
}

/** Versao curta para caber em rotulo de grafico: R$ 28,4 mil. */
export function moneyShort(value: number | string): string {
  return `R$ ${compact.format(Number(value))}`;
}

export function percent(value: number | string, digits = 1): string {
  return `${(Number(value) * 100).toFixed(digits).replace('.', ',')}%`;
}

export function monthLabel(iso: string): string {
  const date = new Date(`${iso.slice(0, 10)}T12:00:00`);
  return date.toLocaleDateString('pt-BR', { month: 'long', year: 'numeric' });
}

/** "outubro" — o mês sem o ano, para frases curtas dentro de uma linha. */
export function mesLabel(iso: string): string {
  const date = new Date(`${iso.slice(0, 10)}T12:00:00`);
  return date.toLocaleDateString('pt-BR', { month: 'long' });
}

export function dayLabel(iso: string): string {
  const date = new Date(`${iso.slice(0, 10)}T12:00:00`);
  return date.toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' });
}

/**
 * "hoje às 14:12", "ontem às 21:40", "28 de set. às 09:05".
 *
 * Serve para datar o número que veio da cópia local do aparelho. Hora sozinha
 * mentiria no dia seguinte ("às 14:12" de qual dia?), e data sozinha esconderia
 * que o número é de dez minutos atrás — nos dois casos quem lê decide errado.
 */
export function quandoLabel(ts: number): string {
  const quando = new Date(ts);
  const hora = quando.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
  const dia = new Date(quando.getFullYear(), quando.getMonth(), quando.getDate());
  const hoje = new Date();
  const diasDeDiferenca = Math.round(
    (new Date(hoje.getFullYear(), hoje.getMonth(), hoje.getDate()).getTime() - dia.getTime()) /
      86_400_000,
  );
  if (diasDeDiferenca === 0) return `hoje às ${hora}`;
  if (diasDeDiferenca === 1) return `ontem às ${hora}`;
  return `${dayLabel(quando.toISOString())} às ${hora}`;
}
