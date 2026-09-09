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

export function dayLabel(iso: string): string {
  const date = new Date(`${iso.slice(0, 10)}T12:00:00`);
  return date.toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' });
}
