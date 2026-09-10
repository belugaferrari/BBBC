/** Evolutivo: saldo projetado em cima, saídas por origem embaixo. */

import React, { useMemo } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import Svg, { Circle, Line, Path, Rect, Text as SvgText } from 'react-native-svg';

import { colors, spacing, typography } from '@/theme';
import { moneyShort } from '@/theme/format';

import { KIND_ORDER, buildForecastGeometry, type FlowKind, type ForecastPoint } from './forecastLayout';

/** Cheio para compromisso assumido, translúcido para chute. */
const KIND_FILL: Record<FlowKind, string> = {
  FIXO: colors.red,
  ESPERADO: 'rgba(225, 29, 46, 0.62)',
  ESTIMADO: 'rgba(225, 29, 46, 0.28)',
};

const KIND_LABEL: Record<FlowKind, string> = {
  FIXO: 'Fixo',
  ESPERADO: 'Esperado',
  ESTIMADO: 'Estimado',
};

interface Props {
  points: ForecastPoint[];
  width: number;
  height?: number;
}

export function ForecastChart({ points, width, height = 200 }: Props): React.ReactElement {
  const geo = useMemo(
    () => buildForecastGeometry(points, width, height),
    [points, width, height],
  );

  if (points.length === 0) {
    return <Text style={styles.empty}>Sem dados para projetar ainda.</Text>;
  }

  return (
    <View>
      <Svg width={width} height={height}>
        {/* saldo projetado */}
        {geo.zeroLineY !== null && (
          <Line
            x1={0} x2={width} y1={geo.zeroLineY} y2={geo.zeroLineY}
            stroke={colors.red} strokeWidth={1} strokeDasharray="3 3"
          />
        )}
        <Path d={geo.balancePath} stroke={colors.white} strokeWidth={2} fill="none" />
        {geo.balanceDots.map((dot, i) => (
          <Circle
            key={`dot-${i}`}
            cx={dot.x} cy={dot.y} r={3.5}
            fill={dot.negative ? colors.red : colors.white}
          />
        ))}
        <SvgText
          x={geo.balanceDots[geo.balanceDots.length - 1].x}
          y={Math.max(11, geo.balanceDots[geo.balanceDots.length - 1].y - 9)}
          fill={colors.textMuted} fontSize={10} textAnchor="end"
        >
          {moneyShort(geo.balanceDots[geo.balanceDots.length - 1].value)}
        </SvgText>

        {/* saídas empilhadas por origem */}
        {geo.bars.map((bar, i) => (
          <Rect
            key={`bar-${i}`}
            x={bar.x} y={bar.y} width={bar.width} height={bar.height}
            fill={KIND_FILL[bar.kind]} rx={2}
          />
        ))}

        {geo.ticks.map((tick, i) => (
          <SvgText
            key={`tick-${i}`}
            x={tick.x} y={height - 3}
            fill={colors.textFaint} fontSize={10} textAnchor="middle"
          >
            {tick.label}
          </SvgText>
        ))}
      </Svg>

      <View style={styles.legend}>
        <View style={styles.item}>
          <View style={[styles.dash, { backgroundColor: colors.white }]} />
          <Text style={styles.text}>Saldo</Text>
        </View>
        {KIND_ORDER.map((kind) => (
          <View key={kind} style={styles.item}>
            <View style={[styles.box, { backgroundColor: KIND_FILL[kind] }]} />
            <Text style={styles.text}>{KIND_LABEL[kind]}</Text>
          </View>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  empty: { ...typography.caption, color: colors.textFaint, paddingVertical: spacing.lg },
  legend: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.md, marginTop: spacing.sm },
  item: { flexDirection: 'row', alignItems: 'center', gap: 5 },
  box: { width: 9, height: 9, borderRadius: 2 },
  dash: { width: 12, height: 2, borderRadius: 1 },
  text: { ...typography.caption, color: colors.textMuted },
});
