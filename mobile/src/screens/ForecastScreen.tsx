/** Previsoes: metas de longo prazo e o simulador de aportes. */

import React, { useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  useWindowDimensions,
  View,
} from 'react-native';

import { useForecast, useGoals } from '@/api/queries';
import { api } from '@/api/client';
import type { Goal, GoalProjection } from '@/api/types';
import { Card, MoneyValue, ProgressBar, SectionTitle } from '@/components/ui';
import { ForecastChart } from '@/components/ForecastChart';
import { colors, radius, spacing, typography } from '@/theme';
import { money, monthLabel } from '@/theme/format';

export function ForecastScreen(): React.ReactElement {
  const { data: goals, isLoading, refetch } = useGoals();
  const [meses, setMeses] = useState(6);
  const { width } = useWindowDimensions();
  const previsao = useForecast(meses, 'familia');

  if (isLoading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={colors.red} />
      </View>
    );
  }

  const projecao = previsao.data?.projection ?? [];
  const resumo = previsao.data?.summary;
  const fontes = previsao.data?.sources;

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <SectionTitle>Próximos meses</SectionTitle>
      <Card>
        <View style={styles.horizons}>
          {[3, 6, 12].map((n) => (
            <Pressable
              key={n}
              onPress={() => setMeses(n)}
              style={[styles.horizon, meses === n && styles.horizonOn]}
            >
              <Text style={[styles.horizonText, meses === n && { color: colors.white }]}>
                {n} meses
              </Text>
            </Pressable>
          ))}
        </View>

        {previsao.isLoading ? (
          <ActivityIndicator color={colors.red} style={{ marginVertical: spacing.lg }} />
        ) : (
          <>
            <ForecastChart
              width={width - spacing.md * 4}
              points={projecao.map((m) => ({
                month: m.month,
                closingBalance: Number(m.closing_balance),
                outflowByKind: Object.fromEntries(
                  Object.entries(m.outflow_by_kind).map(([k, v]) => [k, Number(v)]),
                ),
              }))}
            />

            {resumo?.first_negative_month ? (
              <Text style={styles.alert}>
                No ritmo atual o saldo fica negativo em{' '}
                {monthLabel(resumo.first_negative_month)}.
              </Text>
            ) : (
              <Text style={styles.hint}>
                Saldo projetado para o fim do período:{' '}
                {money(resumo?.closing_balance ?? 0)}.
              </Text>
            )}

            <View style={styles.monthList}>
              {projecao.map((m) => (
                <View key={m.month} style={styles.monthRow}>
                  <Text style={styles.monthName}>{monthLabel(m.month)}</Text>
                  <View style={styles.monthNumbers}>
                    <Text style={styles.monthOut}>−{money(m.outflow)}</Text>
                    <Text
                      style={[
                        styles.monthBalance,
                        Number(m.closing_balance) < 0 && { color: colors.red },
                      ]}
                    >
                      {money(m.closing_balance)}
                    </Text>
                  </View>
                </View>
              ))}
            </View>

            {fontes ? (
              <Text style={styles.sources}>
                De onde vêm os números: {fontes.recurring_rules} gastos fixos
                cadastrados, {fontes.scheduled_transactions} lançamentos já
                agendados e {fontes.estimated_categories} categorias estimadas
                pela média dos últimos {fontes.history_months} meses. O que já
                está previsto como fixo não é somado de novo na média.
              </Text>
            ) : null}
          </>
        )}
      </Card>

      <SectionTitle>Metas da família</SectionTitle>
      {(goals ?? []).map((goal) => (
        <GoalCard key={goal.id} goal={goal} onSimulated={refetch} />
      ))}
      {(goals ?? []).length === 0 && (
        <Text style={styles.empty}>
          Nenhuma meta cadastrada. Comece pelo fundo da viagem para a Disney.
        </Text>
      )}
    </ScrollView>
  );
}

function GoalCard({
  goal,
  onSimulated,
}: {
  goal: Goal;
  onSimulated: () => void;
}): React.ReactElement {
  const [contribution, setContribution] = useState(String(Number(goal.monthly_contribution)));
  const [scenario, setScenario] = useState<GoalProjection | null>(null);
  const [busy, setBusy] = useState(false);

  const projection = scenario ?? goal.projection;
  const progress = Number(goal.current_amount) / Number(projection.adjusted_target || 1);

  async function simulate(): Promise<void> {
    setBusy(true);
    try {
      const result = await api.post<{ scenario: GoalProjection }>(`/goals/${goal.id}/simulate`, {
        monthly_contribution: Number(contribution.replace(',', '.')) || 0,
      });
      setScenario(result.scenario);
      onSimulated();
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <View style={styles.goalHeader}>
        <Text style={styles.goalName}>{goal.name}</Text>
        <Text style={[styles.badge, projection.on_track ? styles.badgeOk : styles.badgeLate]}>
          {projection.on_track ? 'no ritmo' : 'atrasada'}
        </Text>
      </View>

      <MoneyValue value={goal.current_amount} size="title" />
      <Text style={styles.goalSub}>
        de {money(projection.adjusted_target)} · faltam {projection.months_remaining} meses
      </Text>

      <View style={styles.progress}>
        <ProgressBar ratio={progress} severity={projection.on_track ? 'INFO' : 'ATENCAO'} />
      </View>

      <View style={styles.metrics}>
        <Metric label="Aporte atual" value={money(goal.monthly_contribution)} />
        <Metric
          label="Aporte necessario"
          value={money(projection.required_monthly)}
          highlight={!projection.on_track}
        />
      </View>

      {Number(projection.contribution_delta) > 0 && (
        <Text style={styles.warning}>
          Faltam {money(projection.contribution_delta)} por mes para chegar no prazo.
        </Text>
      )}

      <SectionTitle>Simular aporte</SectionTitle>
      <View style={styles.simulator}>
        <TextInput
          value={contribution}
          onChangeText={setContribution}
          keyboardType="decimal-pad"
          style={styles.input}
          placeholder="0,00"
          placeholderTextColor={colors.textFaint}
        />
        <Pressable style={styles.button} onPress={simulate} disabled={busy}>
          <Text style={styles.buttonText}>{busy ? '...' : 'Simular'}</Text>
        </Pressable>
      </View>
      {scenario && (
        <Text style={styles.simulationResult}>
          Com esse aporte voce chega a {money(scenario.projected_amount)}
          {scenario.on_track ? ' — meta atingida.' : ` — ainda faltam ${money(scenario.gap)}.`}
        </Text>
      )}
    </Card>
  );
}

function Metric({
  label,
  value,
  highlight,
}: {
  label: string;
  value: string;
  highlight?: boolean;
}): React.ReactElement {
  return (
    <View style={styles.metric}>
      <Text style={styles.metricLabel}>{label}</Text>
      <Text style={[styles.metricValue, highlight && { color: colors.red }]}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.md, paddingBottom: spacing.xl },
  center: { flex: 1, backgroundColor: colors.background, alignItems: 'center', justifyContent: 'center' },
  empty: { ...typography.body, color: colors.textFaint },
  horizons: { flexDirection: 'row', gap: spacing.sm, marginBottom: spacing.md },
  horizon: {
    paddingHorizontal: spacing.md,
    paddingVertical: 6,
    borderRadius: radius.pill,
    backgroundColor: colors.surfaceAlt,
  },
  horizonOn: { backgroundColor: colors.red },
  horizonText: { ...typography.caption, color: colors.textMuted },
  alert: { ...typography.caption, color: colors.red, marginTop: spacing.md },
  hint: { ...typography.caption, color: colors.textMuted, marginTop: spacing.md },
  monthList: { marginTop: spacing.md, borderTopWidth: 1, borderTopColor: colors.border },
  monthRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 9,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  monthName: { ...typography.body, color: colors.text, textTransform: 'capitalize' },
  monthNumbers: { flexDirection: 'row', gap: spacing.md, alignItems: 'baseline' },
  monthOut: { ...typography.caption, color: colors.red },
  monthBalance: { ...typography.body, color: colors.text },
  sources: {
    ...typography.caption,
    color: colors.textFaint,
    marginTop: spacing.md,
    lineHeight: 17,
  },
  goalHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  goalName: { ...typography.title, color: colors.text },
  badge: {
    ...typography.caption,
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
    borderRadius: radius.pill,
    overflow: 'hidden',
  },
  badgeOk: { backgroundColor: colors.whiteSoft, color: colors.text },
  badgeLate: { backgroundColor: colors.redSoft, color: colors.red },
  goalSub: { ...typography.caption, color: colors.textMuted, marginTop: spacing.xs },
  progress: { marginVertical: spacing.md },
  metrics: { flexDirection: 'row', gap: spacing.md, marginBottom: spacing.sm },
  metric: { flex: 1 },
  metricLabel: { ...typography.caption, color: colors.textFaint },
  metricValue: { ...typography.body, color: colors.text, marginTop: 2 },
  warning: { ...typography.caption, color: colors.red, marginBottom: spacing.md },
  simulator: { flexDirection: 'row', gap: spacing.sm },
  input: {
    flex: 1,
    backgroundColor: colors.surfaceAlt,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    color: colors.text,
  },
  button: {
    backgroundColor: colors.red,
    borderRadius: radius.md,
    paddingHorizontal: spacing.lg,
    justifyContent: 'center',
  },
  buttonText: { ...typography.body, color: colors.white },
  simulationResult: { ...typography.caption, color: colors.textMuted, marginTop: spacing.sm },
});
