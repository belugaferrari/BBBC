/**
 * Imposto de Renda: separacao tributavel / isenta / exclusiva, deducoes das
 * duas filhas e comparacao entre modelo completo e simplificado.
 */

import React, { useState } from 'react';
import { ActivityIndicator, ScrollView, StyleSheet, Text, View } from 'react-native';

import { useTaxAssessment } from '@/api/queries';
import type { TaxModelResult } from '@/api/types';
import { Card, MoneyValue, SectionTitle, StatTile } from '@/components/ui';
import { colors, radius, spacing, typography } from '@/theme';
import { money, percent } from '@/theme/format';

const DEDUCTION_LABELS: Record<string, string> = {
  saude: 'Saude',
  educacao: 'Educacao',
  dependentes: 'Dependentes',
  previdencia_oficial: 'INSS',
  previdencia_privada_pgbl: 'PGBL',
  pensao_alimenticia: 'Pensao',
  livro_caixa: 'Livro-caixa',
  desconto_simplificado: 'Desconto simplificado',
};

export function TaxScreen(): React.ReactElement {
  const [year] = useState(new Date().getFullYear());
  const { data, isLoading, error } = useTaxAssessment(year);

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
        <Text style={styles.empty}>
          Sem parametros fiscais cadastrados para {year}. Cadastre a tabela do ano-calendario.
        </Text>
      </View>
    );
  }

  const best = data.recommended_model === 'COMPLETO' ? data.completo : data.simplificado;
  const toPay = Number(best.balance) > 0;

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <Text style={styles.label}>Ano-calendario {data.year}</Text>
      <MoneyValue
        value={Math.abs(Number(best.balance))}
        size="display"
        direction={toPay ? 'out' : 'in'}
      />
      <Text style={styles.subtitle}>
        {toPay ? 'imposto a pagar' : 'restituicao estimada'} pelo modelo{' '}
        {data.recommended_model.toLowerCase()}
      </Text>

      {data.table_status === 'PROVISORIO' && (
        <View style={styles.notice}>
          <Text style={styles.noticeText}>
            Os parametros de {data.year} estao marcados como provisorios. Confira a tabela
            oficial antes de usar este numero para recolher imposto.
          </Text>
        </View>
      )}

      <Card style={{ marginTop: spacing.lg }}>
        <SectionTitle>Classificacao dos rendimentos</SectionTitle>
        <Row label="Tributavel" value={money(data.taxable_income)} />
        <Row label="Isento e nao tributavel" value={money(data.exempt_income)} />
        <Row label="Tributacao exclusiva na fonte" value={money(data.exclusive_income)} />
        <Row label="Imposto ja retido" value={money(data.withheld_tax)} />
      </Card>

      <Card>
        <SectionTitle>Completo x simplificado</SectionTitle>
        <View style={styles.tiles}>
          <StatTile
            label="Completo"
            value={money(data.completo.tax_due)}
            hint={`Deducoes ${money(data.completo.total_deductions)}`}
            tone={data.recommended_model === 'COMPLETO' ? 'neutral' : 'alert'}
          />
          <StatTile
            label="Simplificado"
            value={money(data.simplificado.tax_due)}
            hint={`Desconto ${money(data.simplificado.total_deductions)}`}
            tone={data.recommended_model === 'SIMPLIFICADO' ? 'neutral' : 'alert'}
          />
        </View>
        <Text style={styles.hint}>
          O modelo {data.recommended_model.toLowerCase()} economiza{' '}
          {money(data.savings_vs_other)}. Aliquota marginal de {percent(data.marginal_rate, 1)}.
        </Text>
      </Card>

      <DeductionBreakdown result={best} />
    </ScrollView>
  );
}

function DeductionBreakdown({ result }: { result: TaxModelResult }): React.ReactElement {
  const entries = Object.entries(result.deductions_breakdown);
  const capped = Object.entries(result.capped_amounts);

  return (
    <Card>
      <SectionTitle>Deducoes consideradas</SectionTitle>
      {entries.map(([key, value]) => (
        <Row key={key} label={DEDUCTION_LABELS[key] ?? key} value={money(value)} />
      ))}
      {entries.length === 0 && <Text style={styles.empty}>Nenhuma deducao lancada.</Text>}

      {capped.length > 0 && (
        <View style={styles.cappedBox}>
          <Text style={styles.cappedTitle}>Perdido por teto legal</Text>
          {capped.map(([key, value]) => (
            <Text key={key} style={styles.cappedItem}>
              {DEDUCTION_LABELS[key] ?? key}: {money(value)} acima do limite
            </Text>
          ))}
          <Text style={styles.cappedHint}>
            O teto de instrucao vale por pessoa — o excedente de uma filha nao migra para a outra.
          </Text>
        </View>
      )}
    </Card>
  );
}

function Row({ label, value }: { label: string; value: string }): React.ReactElement {
  return (
    <View style={styles.row}>
      <Text style={styles.rowLabel}>{label}</Text>
      <Text style={styles.rowValue}>{value}</Text>
    </View>
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
  label: { ...typography.caption, color: colors.textFaint },
  subtitle: { ...typography.caption, color: colors.textMuted, marginTop: spacing.xs },
  notice: {
    backgroundColor: colors.redSoft,
    borderRadius: radius.md,
    padding: spacing.md,
    marginTop: spacing.md,
  },
  noticeText: { ...typography.caption, color: colors.red },
  tiles: { flexDirection: 'row', gap: spacing.sm },
  hint: { ...typography.caption, color: colors.textMuted, marginTop: spacing.md },
  row: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: spacing.sm },
  rowLabel: { ...typography.body, color: colors.textMuted },
  rowValue: { ...typography.body, color: colors.text },
  empty: { ...typography.body, color: colors.textFaint, textAlign: 'center' },
  cappedBox: {
    marginTop: spacing.md,
    padding: spacing.md,
    backgroundColor: colors.surfaceAlt,
    borderRadius: radius.md,
  },
  cappedTitle: { ...typography.caption, color: colors.red, marginBottom: spacing.xs },
  cappedItem: { ...typography.caption, color: colors.textMuted },
  cappedHint: { ...typography.caption, color: colors.textFaint, marginTop: spacing.sm },
});
