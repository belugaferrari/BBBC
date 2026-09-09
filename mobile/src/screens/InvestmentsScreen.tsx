/** Investimentos: custodia consolidada e comparativo contra CDI / IPCA. */

import React, { useMemo, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { useEvolution, usePortfolio } from '@/api/queries';
import { Card, MoneyValue, ProgressBar, SectionTitle, StatTile } from '@/components/ui';
import { colors, radius, spacing, typography } from '@/theme';
import { money, percent } from '@/theme/format';

const BENCHMARKS = ['CDI', 'IPCA', 'IBOV'] as const;

export function InvestmentsScreen(): React.ReactElement {
  const [benchmark, setBenchmark] = useState<string>('CDI');
  const { start, end } = useMemo(() => {
    const now = new Date();
    const from = new Date(now.getFullYear() - 1, now.getMonth(), 1);
    return { start: from.toISOString().slice(0, 10), end: now.toISOString().slice(0, 10) };
  }, []);

  const { data: portfolio, isLoading } = usePortfolio();
  const { data: evolution } = useEvolution(start, end, benchmark);

  if (isLoading || !portfolio) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={colors.red} />
      </View>
    );
  }

  const profit = Number(portfolio.total_profit);

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <Text style={styles.label}>Patrimonio investido</Text>
      <MoneyValue value={portfolio.total_market_value} size="display" />
      <Text style={[styles.subtitle, { color: profit >= 0 ? colors.textMuted : colors.red }]}>
        {profit >= 0 ? '+' : ''}
        {money(portfolio.total_profit)} ({percent(portfolio.total_profit_pct)}) sobre{' '}
        {money(portfolio.total_invested)}
      </Text>

      {evolution && (
        <Card style={{ marginTop: spacing.lg }}>
          <SectionTitle>Contra o indicador</SectionTitle>
          <View style={styles.benchmarkTabs}>
            {BENCHMARKS.map((code) => (
              <Pressable
                key={code}
                onPress={() => setBenchmark(code)}
                style={[styles.tab, benchmark === code && styles.tabActive]}
              >
                <Text style={[styles.tabText, benchmark === code && styles.tabTextActive]}>
                  {code}
                </Text>
              </Pressable>
            ))}
          </View>
          <View style={styles.tiles}>
            <StatTile label="Carteira" value={percent(evolution.portfolio_return)} />
            <StatTile label={benchmark} value={percent(evolution.benchmark_return)} />
          </View>
          <Text style={styles.benchmarkHint}>
            {Number(evolution.pct_of_benchmark) >= 1
              ? `Rendendo ${percent(evolution.pct_of_benchmark, 0)} do ${benchmark}.`
              : `Abaixo do ${benchmark} em ${percent(Math.abs(Number(evolution.excess_return)))}.`}
            {'  '}Real (descontado o IPCA): {percent(evolution.real_return_vs_ipca)}
          </Text>
        </Card>
      )}

      <Card>
        <SectionTitle>Alocacao por classe</SectionTitle>
        {portfolio.by_class.map((allocation) => (
          <View key={allocation.asset_class} style={styles.allocation}>
            <View style={styles.allocationHeader}>
              <Text style={styles.allocationName}>{formatClass(allocation.asset_class)}</Text>
              <Text style={styles.allocationValue}>
                {money(allocation.market_value)}{' '}
                <Text style={styles.allocationWeight}>{percent(allocation.weight, 0)}</Text>
              </Text>
            </View>
            <ProgressBar ratio={Number(allocation.weight)} />
            <Text
              style={[
                styles.allocationProfit,
                { color: Number(allocation.profit) >= 0 ? colors.textMuted : colors.red },
              ]}
            >
              {percent(allocation.profit_pct)} de resultado
            </Text>
          </View>
        ))}
      </Card>

      <Card>
        <SectionTitle>Por titular</SectionTitle>
        {Object.entries(portfolio.by_owner).map(([owner, value]) => (
          <View key={owner} style={styles.ownerRow}>
            <Text style={styles.ownerName}>{owner}</Text>
            <Text style={styles.ownerValue}>{money(value)}</Text>
          </View>
        ))}
        <Text style={styles.exempt}>
          {percent(portfolio.exempt_share, 0)} da carteira esta em papel isento de IR.
        </Text>
      </Card>
    </ScrollView>
  );
}

function formatClass(assetClass: string): string {
  const labels: Record<string, string> = {
    RENDA_FIXA_POS: 'Renda fixa pos-fixada',
    RENDA_FIXA_PRE: 'Renda fixa prefixada',
    RENDA_FIXA_IPCA: 'Renda fixa IPCA+',
    ACAO: 'Acoes',
    FII: 'Fundos imobiliarios',
    ETF: 'ETFs',
    FUNDO: 'Fundos',
    PREVIDENCIA: 'Previdencia',
    EXTERIOR: 'Exterior',
    CRIPTO: 'Cripto',
  };
  return labels[assetClass] ?? assetClass;
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.md, paddingBottom: spacing.xl },
  center: { flex: 1, backgroundColor: colors.background, alignItems: 'center', justifyContent: 'center' },
  label: { ...typography.caption, color: colors.textFaint },
  subtitle: { ...typography.caption, marginTop: spacing.xs },
  benchmarkTabs: { flexDirection: 'row', gap: spacing.sm, marginBottom: spacing.md },
  tab: {
    paddingHorizontal: spacing.md,
    paddingVertical: 6,
    borderRadius: radius.pill,
    backgroundColor: colors.surfaceAlt,
  },
  tabActive: { backgroundColor: colors.red },
  tabText: { ...typography.caption, color: colors.textMuted },
  tabTextActive: { color: colors.white },
  tiles: { flexDirection: 'row', gap: spacing.sm },
  benchmarkHint: { ...typography.caption, color: colors.textMuted, marginTop: spacing.md },
  allocation: { marginBottom: spacing.md },
  allocationHeader: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: spacing.sm },
  allocationName: { ...typography.body, color: colors.text },
  allocationValue: { ...typography.body, color: colors.text },
  allocationWeight: { color: colors.textFaint },
  allocationProfit: { ...typography.caption, marginTop: spacing.xs },
  ownerRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: spacing.sm },
  ownerName: { ...typography.body, color: colors.text },
  ownerValue: { ...typography.body, color: colors.text },
  exempt: { ...typography.caption, color: colors.textMuted, marginTop: spacing.sm },
});
