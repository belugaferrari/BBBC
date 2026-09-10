/** Visao geral do mes: fluxo de caixa, saldos, Sankey, tetos e alertas. */

import React, { useState } from 'react';
import {
  ActivityIndicator,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  useWindowDimensions,
  View,
} from 'react-native';

import { useDashboard } from '@/api/queries';
import type { Scope } from '@/api/types';
import { BudgetRow, Card, MoneyValue, ScopeToggle, SectionTitle, StatTile } from '@/components/ui';
import { SankeyChart } from '@/components/SankeyChart';
import { colors, severityColor, spacing, typography } from '@/theme';
import { money, monthLabel, percent } from '@/theme/format';

function currentMonth(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-01`;
}

export function DashboardScreen(): React.ReactElement {
  const [scope, setScope] = useState<Scope>('familia');
  const month = currentMonth();
  const { width } = useWindowDimensions();
  const { data, isLoading, refetch, isRefetching, error } = useDashboard(month, scope);

  if (isLoading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={colors.red} />
      </View>
    );
  }

  if (error || !data) {
    return (
      <View style={styles.center}>
        <Text style={styles.error}>Nao consegui carregar o mes. Puxe para tentar de novo.</Text>
      </View>
    );
  }

  const { cashflow, balances, sankey, budget_caps: caps, alerts } = data;
  const net = Number(cashflow.net);

  return (
    <ScrollView
      style={styles.screen}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl refreshing={isRefetching} onRefresh={refetch} tintColor={colors.red} />
      }
    >
      <View style={styles.header}>
        <View>
          <Text style={styles.headerLabel}>{monthLabel(data.reference_month)}</Text>
          <MoneyValue value={cashflow.net} size="display" direction={net >= 0 ? 'in' : 'out'} />
          <Text style={styles.headerHint}>
            {net >= 0 ? 'sobrou no mes' : 'faltou no mes'} · poupanca de{' '}
            {percent(cashflow.savings_rate)}
          </Text>
        </View>
        <ScopeToggle value={scope} onChange={setScope} />
      </View>

      <View style={styles.tiles}>
        <StatTile label="Entrou" value={money(cashflow.inflow)} />
        <StatTile
          label="Gastou"
          value={money(cashflow.consumo)}
          tone="alert"
          hint={
            Number(cashflow.patrimonio) > 0
              ? `+ ${money(cashflow.patrimonio)} viraram patrimônio`
              : undefined
          }
        />
      </View>
      <View style={styles.tiles}>
        <StatTile
          label="Disponivel"
          value={money(balances.liquid)}
          hint={`Fatura aberta ${money(balances.credit_card_debt)}`}
        />
        <StatTile
          label="Patrimonio"
          value={money(balances.net_worth)}
          hint={`Investido ${money(balances.invested)}`}
        />
      </View>

      {alerts.length > 0 && (
        <Card>
          <SectionTitle>Alertas</SectionTitle>
          {alerts.map((alert) => (
            <View key={alert.id} style={styles.alert}>
              <View style={[styles.alertDot, { backgroundColor: severityColor[alert.severity] }]} />
              <View style={styles.alertBody}>
                <Text style={styles.alertTitle}>{alert.title}</Text>
                {alert.body ? <Text style={styles.alertText}>{alert.body}</Text> : null}
              </View>
            </View>
          ))}
        </Card>
      )}

      <Card>
        <SectionTitle>Para onde foi o dinheiro</SectionTitle>
        <SankeyChart data={sankey} width={width} />
      </Card>

      {caps.length > 0 && (
        <Card>
          <SectionTitle>Tetos do mes</SectionTitle>
          {caps.map((cap) => (
            <BudgetRow
              key={cap.category_id}
              name={cap.category_name}
              cap={cap.cap}
              spent={cap.spent}
              usedPct={cap.used_pct}
              severity={cap.severity}
              overflow={cap.projected_overflow}
            />
          ))}
        </Card>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.md, paddingBottom: spacing.xl },
  center: {
    flex: 1,
    backgroundColor: colors.background,
    alignItems: 'center',
    justifyContent: 'center',
    padding: spacing.lg,
  },
  error: { ...typography.body, color: colors.textMuted, textAlign: 'center' },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: spacing.lg,
  },
  headerLabel: { ...typography.caption, color: colors.textFaint, marginBottom: spacing.xs },
  headerHint: { ...typography.caption, color: colors.textMuted, marginTop: spacing.xs },
  tiles: { flexDirection: 'row', gap: spacing.sm, marginBottom: spacing.md },
  alert: { flexDirection: 'row', gap: spacing.sm, marginBottom: spacing.sm },
  alertDot: { width: 6, height: 6, borderRadius: 3, marginTop: 6 },
  alertBody: { flex: 1 },
  alertTitle: { ...typography.body, color: colors.text },
  alertText: { ...typography.caption, color: colors.textMuted, marginTop: 2 },
});
