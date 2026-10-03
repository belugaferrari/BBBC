/**
 * Treze barras: o mês escolhido e os doze que o antecedem.
 *
 * A leitura que este gráfico tem de entregar num relance é "este mês é normal
 * ou não". Por isso duas coisas que não são enfeite: a barra do mês escolhido
 * fica vermelha (as outras cinzas), e uma linha pontilhada marca a média dos
 * doze. Barra acima da linha é mês fora da curva — e é só isso que se precisa
 * ver sem ler número nenhum.
 */

import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import Svg, { Line, Rect } from 'react-native-svg';

import type { MonthPoint } from '@/api/types';
import { colors, spacing, typography } from '@/theme';
import { moneyShort } from '@/theme/format';

const ALTURA = 120;

/** "2026-10-01" -> "out". Só a inicial do mês cabe em treze colunas. */
function mesCurto(iso: string): string {
  const data = new Date(`${iso.slice(0, 10)}T12:00:00`);
  return data.toLocaleDateString('pt-BR', { month: 'short' }).replace('.', '');
}

export function BarSeries({
  points,
  width,
  media,
}: {
  points: MonthPoint[];
  width: number;
  media?: number;
}): React.ReactElement {
  if (points.length === 0) {
    return <Text style={styles.vazio}>Sem histórico ainda.</Text>;
  }

  const valores = points.map((p) => Number(p.total));
  const teto = Math.max(...valores, media ?? 0, 1);
  const vao = width / points.length;
  const largura = Math.max(vao - 6, 3);

  return (
    <View>
      <Svg width={width} height={ALTURA}>
        {points.map((ponto, i) => {
          const altura = (Number(ponto.total) / teto) * (ALTURA - 8);
          const ultimo = i === points.length - 1;
          return (
            <Rect
              key={ponto.month}
              x={i * vao + 3}
              y={ALTURA - altura}
              width={largura}
              height={Math.max(altura, 1)}
              rx={3}
              fill={ultimo ? colors.red : colors.border}
            />
          );
        })}
        {media !== undefined && media > 0 ? (
          <Line
            x1={0}
            x2={width}
            y1={ALTURA - (media / teto) * (ALTURA - 8)}
            y2={ALTURA - (media / teto) * (ALTURA - 8)}
            stroke={colors.textFaint}
            strokeWidth={1}
            strokeDasharray="4 4"
          />
        ) : null}
      </Svg>

      <View style={[styles.rotulos, { width }]}>
        {points.map((ponto, i) => (
          <Text
            key={ponto.month}
            style={[
              styles.rotulo,
              { width: vao },
              i === points.length - 1 && styles.rotuloAtual,
            ]}
          >
            {/* o primeiro e o último sempre; os do meio alternam, para não virar borrão */}
            {i === 0 || i === points.length - 1 || i % 2 === 0 ? mesCurto(ponto.month) : ''}
          </Text>
        ))}
      </View>

      {media !== undefined && media > 0 ? (
        <Text style={styles.legenda}>
          A linha pontilhada é a média dos doze meses: {moneyShort(media)}
        </Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  vazio: { ...typography.caption, color: colors.textFaint },
  rotulos: { flexDirection: 'row', marginTop: spacing.xs },
  rotulo: { ...typography.caption, fontSize: 11, color: colors.textFaint, textAlign: 'center' },
  rotuloAtual: { color: colors.red, fontWeight: '700' },
  legenda: { ...typography.caption, color: colors.textFaint, marginTop: spacing.sm },
});
