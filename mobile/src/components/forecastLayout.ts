/**
 * Geometria do evolutivo, separada do componente para poder ser conferida sem
 * renderizar nada.
 *
 * São duas faixas empilhadas que dividem o mesmo eixo de meses:
 *   - em cima, a linha do saldo projetado, com escala própria;
 *   - embaixo, as barras de saída, empilhadas por origem (fixo, esperado,
 *     estimado), com escala própria.
 * Duas escalas num gráfico só fariam as duas leituras mentirem uma sobre a
 * outra; separadas, cada faixa é honesta dentro de si.
 */

export type FlowKind = 'FIXO' | 'ESPERADO' | 'ESTIMADO';

export const KIND_ORDER: FlowKind[] = ['FIXO', 'ESPERADO', 'ESTIMADO'];

export interface ForecastPoint {
  month: string;                            // '2026-10-01'
  closingBalance: number;
  outflowByKind: Partial<Record<FlowKind, number>>;
}

export interface StackSegment {
  kind: FlowKind;
  x: number;
  y: number;
  width: number;
  height: number;
  value: number;
}

export interface ForecastGeometry {
  width: number;
  height: number;
  bandTop: { y: number; height: number };
  bandBottom: { y: number; height: number };
  balancePath: string;
  balanceDots: { x: number; y: number; value: number; negative: boolean }[];
  zeroLineY: number | null;
  bars: StackSegment[];
  ticks: { x: number; label: string }[];
  maxOutflow: number;
  balanceRange: { min: number; max: number };
}

const MESES = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun',
               'jul', 'ago', 'set', 'out', 'nov', 'dez'];

export function monthLabel(iso: string): string {
  const [, mes] = iso.split('-');
  return MESES[Number(mes) - 1] ?? iso;
}

export function buildForecastGeometry(
  points: ForecastPoint[],
  width: number,
  height: number,
): ForecastGeometry {
  const GAP = 14;                     // respiro entre as duas faixas
  const AXIS = 16;                    // altura reservada aos rótulos de mês
  const alturaUtil = height - AXIS - GAP;
  const bandTop = { y: 0, height: Math.round(alturaUtil * 0.42) };
  const bandBottom = { y: bandTop.height + GAP, height: alturaUtil - bandTop.height };

  const vazio: ForecastGeometry = {
    width, height, bandTop, bandBottom,
    balancePath: '', balanceDots: [], zeroLineY: null, bars: [], ticks: [],
    maxOutflow: 0, balanceRange: { min: 0, max: 0 },
  };
  if (points.length === 0) return vazio;

  const passo = width / points.length;
  const larguraBarra = Math.min(26, passo * 0.52);

  // ── faixa de cima: saldo ────────────────────────────────────────────────
  const saldos = points.map((p) => p.closingBalance);
  // o zero entra na escala sempre que o saldo chega perto dele, para a linha
  // do zero ter onde ser desenhada
  const min = Math.min(0, ...saldos);
  const max = Math.max(0, ...saldos);
  const amplitude = max - min || 1;
  const yDoSaldo = (valor: number) =>
    bandTop.y + bandTop.height - ((valor - min) / amplitude) * bandTop.height;

  const balanceDots = points.map((p, i) => ({
    x: passo * i + passo / 2,
    y: yDoSaldo(p.closingBalance),
    value: p.closingBalance,
    negative: p.closingBalance < 0,
  }));
  const balancePath = balanceDots
    .map((d, i) => `${i === 0 ? 'M' : 'L'} ${d.x.toFixed(1)} ${d.y.toFixed(1)}`)
    .join(' ');

  // ── faixa de baixo: saídas empilhadas ───────────────────────────────────
  const totais = points.map((p) =>
    KIND_ORDER.reduce((soma, kind) => soma + (p.outflowByKind[kind] ?? 0), 0));
  const maxOutflow = Math.max(...totais, 1);

  const bars: StackSegment[] = [];
  points.forEach((p, i) => {
    let base = bandBottom.y + bandBottom.height;
    KIND_ORDER.forEach((kind) => {
      const valor = p.outflowByKind[kind] ?? 0;
      if (valor <= 0) return;
      const altura = (valor / maxOutflow) * bandBottom.height;
      base -= altura;
      bars.push({
        kind,
        x: passo * i + (passo - larguraBarra) / 2,
        y: base,
        width: larguraBarra,
        height: altura,
        value: valor,
      });
    });
  });

  return {
    width,
    height,
    bandTop,
    bandBottom,
    balancePath,
    balanceDots,
    zeroLineY: min < 0 ? yDoSaldo(0) : null,
    bars,
    ticks: points.map((p, i) => ({
      x: passo * i + passo / 2,
      label: monthLabel(p.month),
    })),
    maxOutflow,
    balanceRange: { min, max },
  };
}
