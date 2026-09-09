/**
 * Paleta do app: preto, branco e vermelho.
 *
 * O vermelho e reservado para o que exige atencao (saida de dinheiro, teto
 * estourado, imposto a pagar). Usar vermelho em tudo tira o poder do alerta,
 * entao entradas e saldos positivos ficam em branco.
 */

export const colors = {
  background: '#0A0A0B',
  surface: '#141416',
  surfaceAlt: '#1C1C1F',
  border: '#2A2A2E',

  text: '#FFFFFF',
  textMuted: '#A1A1AA',
  textFaint: '#6B6B73',

  red: '#E11D2E',
  redDark: '#8F0F1C',
  redSoft: 'rgba(225, 29, 46, 0.14)',

  white: '#FFFFFF',
  whiteSoft: 'rgba(255, 255, 255, 0.08)',

  /** entrada de dinheiro */
  inflow: '#FFFFFF',
  /** saida de dinheiro */
  outflow: '#E11D2E',
} as const;

export const spacing = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
} as const;

export const radius = {
  sm: 8,
  md: 14,
  lg: 20,
  pill: 999,
} as const;

export const typography = {
  display: { fontSize: 34, fontWeight: '700' as const, letterSpacing: -0.8 },
  title: { fontSize: 22, fontWeight: '700' as const, letterSpacing: -0.4 },
  section: { fontSize: 13, fontWeight: '600' as const, letterSpacing: 1.1 },
  body: { fontSize: 15, fontWeight: '500' as const },
  caption: { fontSize: 12, fontWeight: '500' as const },
} as const;

export const severityColor = {
  INFO: colors.textMuted,
  ATENCAO: '#F5A524',
  CRITICO: colors.red,
} as const;
