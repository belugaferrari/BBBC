/**
 * Grafico em cascata (Sankey) do dashboard.
 *
 * Nao existe biblioteca de Sankey pronta para React Native, entao o layout e
 * calculado aqui e desenhado com react-native-svg. Regras do desenho:
 *   - a espessura de cada fita e proporcional ao valor;
 *   - todos os estagios usam a MESMA escala, senao a comparacao visual mente;
 *   - entrada de dinheiro em branco, saida em vermelho (paleta do app).
 */

import React, { useMemo } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import Svg, { Defs, LinearGradient, Path, Rect, Stop, Text as SvgText } from 'react-native-svg';

import type { SankeyData } from '@/api/types';
import { colors, radius, spacing, typography } from '@/theme';
import { money, moneyShort } from '@/theme/format';

import { buildLayout, NODE_WIDTH } from './sankeyLayout';

/** Folga entre a barra do no e o seu rotulo. */
const LABEL_SPACE = 4;

interface Props {
  data: SankeyData;
  width: number;
  height?: number;
}

export function SankeyChart({ data, width, height = 260 }: Props): React.ReactElement {
  const chartWidth = width - spacing.md * 2;
  const { nodes, ribbons } = useMemo(
    () => buildLayout(data, chartWidth, height),
    [data, chartWidth, height],
  );

  if (nodes.length === 0) {
    return (
      <View style={styles.empty}>
        <Text style={styles.emptyText}>Sem lancamentos neste mes.</Text>
      </View>
    );
  }

  return (
    <View>
      <Svg width={chartWidth} height={height + 24}>
        <Defs>
          <LinearGradient id="inflow" x1="0" y1="0" x2="1" y2="0">
            <Stop offset="0" stopColor={colors.white} stopOpacity="0.9" />
            <Stop offset="1" stopColor={colors.white} stopOpacity="0.35" />
          </LinearGradient>
          <LinearGradient id="outflow" x1="0" y1="0" x2="1" y2="0">
            <Stop offset="0" stopColor={colors.red} stopOpacity="0.85" />
            <Stop offset="1" stopColor={colors.redDark} stopOpacity="0.55" />
          </LinearGradient>
        </Defs>

        {ribbons.map((ribbon) => (
          <Path
            key={ribbon.key}
            d={ribbon.path}
            fill={ribbon.fromStage === 0 ? 'url(#inflow)' : 'url(#outflow)'}
            opacity={ribbon.fromStage === 0 ? 0.28 : 0.36}
          />
        ))}

        {nodes.map((node) => {
          const isInflow = node.stage === 0;
          const anchorLeft = node.stage < 2;
          return (
            <React.Fragment key={node.id}>
              <Rect
                x={node.x}
                y={node.y}
                width={NODE_WIDTH}
                height={node.height}
                rx={3}
                fill={isInflow ? colors.white : colors.red}
                opacity={node.stage === 1 ? 1 : 0.9}
              />
              {node.height >= 14 && (
                <SvgText
                  x={anchorLeft ? node.x + NODE_WIDTH + LABEL_SPACE : node.x - LABEL_SPACE}
                  y={node.y + node.height / 2 + 4}
                  fill={colors.textMuted}
                  fontSize={10}
                  textAnchor={anchorLeft ? 'start' : 'end'}
                >
                  {`${node.label} · ${moneyShort(node.value)}`}
                </SvgText>
              )}
            </React.Fragment>
          );
        })}
      </Svg>

      <View style={styles.legend}>
        <Legend color={colors.white} label={`Entrou ${money(data.total_income)}`} />
        <Legend color={colors.red} label={`Saiu ${money(data.total_expense)}`} />
      </View>
    </View>
  );
}

function Legend({ color, label }: { color: string; label: string }): React.ReactElement {
  return (
    <View style={styles.legendItem}>
      <View style={[styles.legendDot, { backgroundColor: color }]} />
      <Text style={styles.legendText}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  empty: {
    height: 140,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.surfaceAlt,
    borderRadius: radius.md,
  },
  emptyText: { color: colors.textFaint, ...typography.body },
  legend: { flexDirection: 'row', gap: spacing.md, marginTop: spacing.sm },
  legendItem: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
  legendDot: { width: 8, height: 8, borderRadius: 4 },
  legendText: { color: colors.textMuted, ...typography.caption },
});
