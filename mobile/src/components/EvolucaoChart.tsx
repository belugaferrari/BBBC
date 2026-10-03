/**
 * O gasto acumulado do mês, contra três referências.
 *
 * Substituiu o Sankey. O Sankey é bonito e responde "para onde foi o dinheiro" —
 * pergunta que a aba Categorias responde melhor, com números em vez de fitas. O
 * que ele não respondia é a pergunta que se faz no dia 12: **estou gastando
 * rápido demais?**
 *
 * Para responder isso não basta o total, precisa do ritmo — e ritmo só existe
 * comparado. Daí as três referências:
 *
 *   * a META do mês, reta, porque é um teto;
 *   * o MÊS PASSADO, que diz se mudou alguma coisa agora;
 *   * o MESMO MÊS DO ANO PASSADO, que separa mudança de sazonalidade.
 *
 * As duas últimas vêm como curva, e não como linha reta no total delas. A reta
 * diria só "no fim do mês passado deu R$ 4.200"; a curva diz "no dia 12 do mês
 * passado você estava em R$ 1.100, e hoje está em R$ 1.900" — que é a leitura
 * que faz alguém mudar de comportamento no meio do mês, enquanto ainda dá. O
 * total continua legível: é onde a curva termina.
 */

import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import Svg, { Circle, Line, Path, Text as SvgText } from 'react-native-svg';

import type { DiaAcumulado, Evolucao } from '@/api/types';
import { colors, spacing, typography } from '@/theme';
import { money, moneyShort } from '@/theme/format';

const ALTURA = 190;
const MARGEM_ESQUERDA = 4;
const MARGEM_TOPO = 10;
const MARGEM_BAIXO = 22;

/** Cinza para as referências, vermelho só para o mês que está correndo. */
const COR_PASSADO = '#6B6B73';
const COR_ANO_PASSADO = '#45454C';
const COR_META = '#F5A524';

function caminho(
  pontos: DiaAcumulado[],
  escalaX: (dia: number) => number,
  escalaY: (valor: number) => number,
): string {
  if (pontos.length === 0) return '';
  return pontos
    .map((p, i) => `${i === 0 ? 'M' : 'L'}${escalaX(p.day)},${escalaY(Number(p.total))}`)
    .join(' ');
}

export function EvolucaoChart({
  dados,
  width,
}: {
  dados: Evolucao;
  width: number;
}): React.ReactElement {
  const dias = dados.days_in_month;
  const larguraUtil = Math.max(width - MARGEM_ESQUERDA, 40);
  const alturaUtil = ALTURA - MARGEM_TOPO - MARGEM_BAIXO;

  const meta = dados.current.cap ? Number(dados.current.cap) : null;
  const totalAgora = Number(dados.current.total);
  const totalPassado = Number(dados.previous_month.total);
  const totalAnoPassado = Number(dados.same_month_last_year.total);

  // O teto do eixo precisa caber tudo, inclusive a meta: uma meta fora da área
  // desenhada viraria uma linha invisível, e é justamente a que importa.
  const teto = Math.max(totalAgora, totalPassado, totalAnoPassado, meta ?? 0, 1) * 1.08;

  const escalaX = (dia: number) =>
    MARGEM_ESQUERDA + ((dia - 1) / Math.max(dias - 1, 1)) * larguraUtil;
  const escalaY = (valor: number) =>
    MARGEM_TOPO + alturaUtil - (valor / teto) * alturaUtil;

  // No mês corrente a curva para em hoje. Desenhá-la reta até o dia 31 faria o
  // mês parecer estagnado, quando na verdade ele ainda não aconteceu.
  const ateHoje = dados.today
    ? dados.current.series.filter((p) => p.day <= dados.today!)
    : dados.current.series;
  const ultimo = ateHoje[ateHoje.length - 1];

  return (
    <View>
      <Svg width={width} height={ALTURA}>
        {/* a meta, reta, porque é um teto */}
        {meta !== null ? (
          <>
            <Line
              x1={MARGEM_ESQUERDA}
              x2={width}
              y1={escalaY(meta)}
              y2={escalaY(meta)}
              stroke={COR_META}
              strokeWidth={1.5}
              strokeDasharray="6 4"
            />
            <SvgText
              x={width}
              y={escalaY(meta) - 5}
              fill={COR_META}
              fontSize="11"
              textAnchor="end"
            >
              {`meta ${moneyShort(meta)}`}
            </SvgText>
          </>
        ) : null}

        <Path
          d={caminho(dados.same_month_last_year.series, escalaX, escalaY)}
          stroke={COR_ANO_PASSADO}
          strokeWidth={1.5}
          strokeDasharray="3 3"
          fill="none"
        />
        <Path
          d={caminho(dados.previous_month.series, escalaX, escalaY)}
          stroke={COR_PASSADO}
          strokeWidth={1.5}
          fill="none"
        />
        <Path
          d={caminho(ateHoje, escalaX, escalaY)}
          stroke={colors.red}
          strokeWidth={2.5}
          fill="none"
        />
        {ultimo ? (
          <Circle
            cx={escalaX(ultimo.day)}
            cy={escalaY(Number(ultimo.total))}
            r={4}
            fill={colors.red}
          />
        ) : null}

        {/* dias de referência no pé */}
        {[1, Math.round(dias / 2), dias].map((dia) => (
          <SvgText
            key={dia}
            x={escalaX(dia)}
            y={ALTURA - 6}
            fill={colors.textFaint}
            fontSize="11"
            textAnchor={dia === 1 ? 'start' : dia === dias ? 'end' : 'middle'}
          >
            {`dia ${dia}`}
          </SvgText>
        ))}
      </Svg>

      <View style={styles.legenda}>
        <Item cor={colors.red} rotulo="Este mês" valor={money(totalAgora)} forte />
        <Item cor={COR_PASSADO} rotulo="Mês passado" valor={money(totalPassado)} />
        <Item
          cor={COR_ANO_PASSADO}
          rotulo={`Mesmo mês de ${Number(dados.month.slice(0, 4)) - 1}`}
          valor={totalAnoPassado > 0 ? money(totalAnoPassado) : 'sem histórico'}
          tracejado
        />
        {meta !== null ? (
          <Item cor={COR_META} rotulo="Meta do mês" valor={money(meta)} tracejado />
        ) : (
          <Text style={styles.semMeta}>
            Sem meta neste mês. Defina em Categorias e a linha aparece aqui.
          </Text>
        )}
      </View>
    </View>
  );
}

function Item({
  cor,
  rotulo,
  valor,
  forte = false,
  tracejado = false,
}: {
  cor: string;
  rotulo: string;
  valor: string;
  forte?: boolean;
  tracejado?: boolean;
}): React.ReactElement {
  return (
    <View style={styles.item}>
      <View
        style={[
          styles.traco,
          { backgroundColor: cor },
          forte && styles.tracoForte,
          tracejado && styles.tracoFraco,
        ]}
      />
      <Text style={styles.itemRotulo}>{rotulo}</Text>
      <Text style={[styles.itemValor, forte && styles.itemValorForte]}>{valor}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  legenda: { marginTop: spacing.sm },
  item: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    paddingVertical: 3,
  },
  traco: { width: 16, height: 2, borderRadius: 1 },
  tracoForte: { height: 3 },
  tracoFraco: { opacity: 0.7 },
  itemRotulo: { ...typography.caption, color: colors.textMuted, flex: 1 },
  itemValor: { ...typography.caption, color: colors.text },
  itemValorForte: { ...typography.body, color: colors.text, fontWeight: '700' },
  semMeta: { ...typography.caption, color: colors.textFaint, marginTop: spacing.xs },
});
