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
  textMuted: '#B4B4BD',
  textFaint: '#80808A',

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
  md: 14,
  lg: 20,
  xl: 28,
} as const;

export const radius = {
  sm: 8,
  md: 14,
  lg: 20,
  pill: 999,
} as const;

/**
 * Tamanhos de texto um degrau acima do que a moda do design mobile pede.
 *
 * O app e lido tambem no navegador de um monitor grande, de longe, e por gente
 * que nao vai apertar os olhos para conferir quanto sobrou no mes. Corpo em 17
 * e legenda em 14 e o minimo que se le sem esforco nas duas situacoes.
 */
export const typography = {
  display: { fontSize: 40, fontWeight: '700' as const, letterSpacing: -1 },
  title: { fontSize: 25, fontWeight: '700' as const, letterSpacing: -0.4 },
  section: { fontSize: 13, fontWeight: '700' as const, letterSpacing: 1.1 },
  body: { fontSize: 17, fontWeight: '500' as const },
  caption: { fontSize: 14, fontWeight: '500' as const },
} as const;

/**
 * Largura maxima da coluna de conteudo.
 *
 * No celular nao muda nada - a tela e mais estreita que isso. No navegador de
 * um monitor largo muda tudo: sem o limite, uma linha "Entrou ....... R$ 1.000"
 * joga o rotulo na borda esquerda e o valor na direita, a um palmo de distancia,
 * e ler o par vira trabalho. A coluna centralizada mantem o olho num lugar so.
 */
export const layout = {
  maxWidth: 720,
  /**
   * Aplicar no contentContainerStyle de ScrollView e no root de telas fixas.
   *
   * Centraliza por dois caminhos de proposito: `alignSelf` resolve quando o pai
   * e um container flex (o caso do navegador), e a margem automatica resolve
   * quando nao e - o conteudo de um ScrollView nativo nao e filho de flexbox, e
   * so com `alignSelf` ele ficaria colado na esquerda num tablet.
   */
  coluna: {
    width: '100%' as const,
    maxWidth: 720,
    alignSelf: 'center' as const,
    marginHorizontal: 'auto' as const,
  },
} as const;

/** Altura minima de area tocavel: dedo em celular, mouse em monitor. */
export const toque = 48;

export const severityColor = {
  INFO: colors.textMuted,
  ATENCAO: '#F5A524',
  CRITICO: colors.red,
} as const;
