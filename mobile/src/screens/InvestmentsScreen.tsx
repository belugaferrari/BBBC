/** Investimentos: custodia consolidada e comparativo contra CDI / IPCA. */

import React, { useMemo, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import {
  useCardPrograms,
  useEvolution,
  useHoldings,
  useNetWorth,
  usePortfolio,
} from '@/api/queries';
import { Card, MoneyValue, ProgressBar, SectionTitle, StatTile } from '@/components/ui';
import { colors, radius, spacing, typography } from '@/theme';
import { dayLabel, money, percent } from '@/theme/format';

const BENCHMARKS = ['CDI', 'IPCA', 'IBOV'] as const;

type Aba = 'carteira' | 'bens' | 'pontos';

export function InvestmentsScreen(): React.ReactElement {
  const [aba, setAba] = useState<Aba>('carteira');
  const [benchmark, setBenchmark] = useState<string>('CDI');
  const { start, end } = useMemo(() => {
    const now = new Date();
    const from = new Date(now.getFullYear() - 1, now.getMonth(), 1);
    return { start: from.toISOString().slice(0, 10), end: now.toISOString().slice(0, 10) };
  }, []);

  const { data: portfolio, isLoading } = usePortfolio();
  const { data: evolution } = useEvolution(start, end, benchmark);
  const { data: patrimonio } = useNetWorth();
  const { data: bens } = useHoldings();
  const { data: pontos } = useCardPrograms();

  if (isLoading || !portfolio) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={colors.red} />
      </View>
    );
  }

  const profit = Number(portfolio.total_profit);

  const participacoes = (bens ?? []).filter((b) => b.kind === 'PARTICIPACAO');
  const outrosBens = (bens ?? []).filter((b) => b.kind !== 'PARTICIPACAO');

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      {patrimonio ? (
        <View style={styles.netWorth}>
          <Text style={styles.label}>Patrimônio total</Text>
          <Text style={styles.netWorthValue}>{money(patrimonio.total)}</Text>
          <Text style={styles.netWorthHint}>
            {money(patrimonio.liquid)} em conta · {money(patrimonio.invested)} investido ·{' '}
            {money(patrimonio.holdings)} em bens
            {Number(patrimonio.debts) > 0 ? ` · −${money(patrimonio.debts)} de dívida` : ''}
          </Text>
          {Number(patrimonio.illiquid_share) > 0.6 ? (
            <Text style={styles.illiquid}>
              {percent(patrimonio.illiquid_share, 0)} do patrimônio está em bens — não vira
              dinheiro rápido.
            </Text>
          ) : null}
        </View>
      ) : null}

      <View style={styles.tabs}>
        {(['carteira', 'bens', 'pontos'] as const).map((opcao) => (
          <Pressable
            key={opcao}
            onPress={() => setAba(opcao)}
            style={[styles.tab, aba === opcao && styles.tabActive]}
          >
            <Text style={[styles.tabText, aba === opcao && { color: colors.white }]}>
              {opcao === 'carteira' ? 'Carteira' : opcao === 'bens' ? 'Bens' : 'Pontos'}
            </Text>
          </Pressable>
        ))}
      </View>

      {aba === 'bens' ? (
        <>
          <SectionTitle>Imóveis e outros bens</SectionTitle>
          <Card>
            {outrosBens.map((bem) => (
              <View key={bem.id} style={styles.holding}>
                <View style={styles.holdingHead}>
                  <Text style={styles.holdingName}>{bem.name}</Text>
                  <Text style={styles.holdingValue}>{money(bem.current_value)}</Text>
                </View>
                {bem.acquisition_value ? (
                  <Text style={styles.holdingHint}>
                    Comprado por {money(bem.acquisition_value)}
                    {Number(bem.unrealized_gain ?? 0) !== 0
                      ? ` · ${Number(bem.unrealized_gain) > 0 ? '+' : ''}${money(
                          bem.unrealized_gain ?? 0,
                        )} de valorização`
                      : ''}
                  </Text>
                ) : null}
                {bem.ir_declared_value ? (
                  <Text style={styles.holdingIr}>
                    No IR: {money(bem.ir_declared_value)} — a Receita declara pelo custo de
                    aquisição, não pelo valor de mercado.
                  </Text>
                ) : null}
              </View>
            ))}
            {outrosBens.length === 0 && (
              <Text style={styles.empty}>Nenhum bem cadastrado ainda.</Text>
            )}
          </Card>

          <SectionTitle>Participações em empresas</SectionTitle>
          <Card>
            {participacoes.map((parte) => (
              <View key={parte.id} style={styles.holding}>
                <View style={styles.holdingHead}>
                  <Text style={styles.holdingName}>{parte.name}</Text>
                  <Text style={styles.holdingValue}>{money(parte.current_value)}</Text>
                </View>
                <Text style={styles.holdingHint}>
                  {percent(Number(parte.ownership_percentage ?? 0) / 100, 1)} da empresa
                  {parte.company_cnpj ? ` · CNPJ ${parte.company_cnpj}` : ''}
                </Text>
              </View>
            ))}
            {participacoes.length === 0 && (
              <Text style={styles.empty}>Nenhuma participação cadastrada ainda.</Text>
            )}
          </Card>
        </>
      ) : null}

      {aba === 'pontos' ? (
        <>
          <SectionTitle>Pontos e milhas</SectionTitle>
          <Card>
            <Text style={styles.pointsTotal}>
              {Number(pontos?.total_points ?? 0).toLocaleString('pt-BR')} pontos
            </Text>
            {Number(pontos?.total_value_brl ?? 0) > 0 ? (
              <Text style={styles.holdingHint}>
                valem cerca de {money(pontos?.total_value_brl ?? 0)}
              </Text>
            ) : null}

            {(pontos?.programs ?? []).map((programa) => (
              <View key={programa.id} style={styles.holding}>
                <View style={styles.holdingHead}>
                  <Text style={styles.holdingName}>{programa.name}</Text>
                  <Text style={styles.holdingValue}>
                    {Number(programa.balance).toLocaleString('pt-BR')}
                  </Text>
                </View>
                {programa.card_name ? (
                  <Text style={styles.holdingHint}>{programa.card_name}</Text>
                ) : null}
                {programa.expires_next_on ? (
                  <Text
                    style={[
                      styles.holdingHint,
                      programa.should_alert && { color: colors.red },
                    ]}
                  >
                    {Number(programa.expires_next_points ?? 0).toLocaleString('pt-BR')}{' '}
                    pontos expiram em {dayLabel(programa.expires_next_on)}
                    {programa.days_to_expire !== null
                      ? ` (${programa.days_to_expire} dias)`
                      : ''}
                  </Text>
                ) : null}
              </View>
            ))}
            {(pontos?.programs ?? []).length === 0 && (
              <Text style={styles.empty}>Nenhum programa cadastrado ainda.</Text>
            )}
          </Card>
        </>
      ) : null}

      {aba !== 'carteira' ? null : (
      <>
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
          {percent(portfolio.exempt_share, 0)} da carteira está em papel isento de IR.
        </Text>
      </Card>
      </>
      )}
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
  netWorth: { marginBottom: spacing.md },
  netWorthValue: {
    ...typography.display,
    color: colors.text,
    fontSize: 32,
    marginTop: 2,
  },
  netWorthHint: { ...typography.caption, color: colors.textMuted, marginTop: spacing.xs },
  illiquid: { ...typography.caption, color: colors.textFaint, marginTop: spacing.xs },
  tabs: {
    flexDirection: 'row',
    backgroundColor: colors.surfaceAlt,
    borderRadius: radius.pill,
    padding: 3,
    marginBottom: spacing.md,
  },
  tab: { flex: 1, paddingVertical: 7, borderRadius: radius.pill, alignItems: 'center' },
  tabActive: { backgroundColor: colors.red },
  tabText: { ...typography.caption, color: colors.textMuted },
  holding: { marginTop: spacing.md },
  holdingHead: { flexDirection: 'row', justifyContent: 'space-between', gap: spacing.sm },
  holdingName: { ...typography.body, color: colors.text, flex: 1 },
  holdingValue: { ...typography.body, color: colors.text },
  holdingHint: { ...typography.caption, color: colors.textMuted, marginTop: 3 },
  holdingIr: { ...typography.caption, color: colors.textFaint, marginTop: 3 },
  pointsTotal: { ...typography.title, color: colors.text },
  empty: { ...typography.caption, color: colors.textFaint, marginTop: spacing.sm },
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
