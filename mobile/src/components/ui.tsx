/** Blocos visuais reaproveitados pelas telas. */

import React from 'react';
import { Pressable, StyleSheet, Text, View, type ViewStyle } from 'react-native';

import { colors, radius, severityColor, spacing, typography } from '@/theme';
import { money, percent } from '@/theme/format';
import type { Scope } from '@/api/types';

export function Card({
  children,
  style,
}: {
  children: React.ReactNode;
  style?: ViewStyle;
}): React.ReactElement {
  return <View style={[styles.card, style]}>{children}</View>;
}

export function SectionTitle({ children }: { children: string }): React.ReactElement {
  return <Text style={styles.sectionTitle}>{children.toUpperCase()}</Text>;
}

export function MoneyValue({
  value,
  direction = 'neutral',
  size = 'body',
}: {
  value: string | number;
  direction?: 'in' | 'out' | 'neutral';
  size?: 'body' | 'display' | 'title';
}): React.ReactElement {
  const color =
    direction === 'out' ? colors.outflow : direction === 'in' ? colors.inflow : colors.text;
  const prefix = direction === 'out' ? '-' : direction === 'in' ? '+' : '';
  return (
    <Text style={[typography[size], { color }]}>
      {prefix}
      {money(value)}
    </Text>
  );
}

/** Barra de teto: fica vermelha assim que o gasto passa do limite. */
export function ProgressBar({
  ratio,
  severity = 'INFO',
}: {
  ratio: number;
  severity?: 'INFO' | 'ATENCAO' | 'CRITICO';
}): React.ReactElement {
  const clamped = Math.max(0, Math.min(1, ratio));
  return (
    <View style={styles.progressTrack}>
      <View
        style={[
          styles.progressFill,
          { width: `${clamped * 100}%`, backgroundColor: severityColor[severity] },
        ]}
      />
    </View>
  );
}

export function ScopeToggle({
  value,
  onChange,
}: {
  value: Scope;
  onChange: (scope: Scope) => void;
}): React.ReactElement {
  return (
    <View style={styles.toggle}>
      {(['familia', 'individual'] as const).map((option) => {
        const active = option === value;
        return (
          <Pressable
            key={option}
            onPress={() => onChange(option)}
            style={[styles.toggleOption, active && styles.toggleOptionActive]}
            accessibilityRole="button"
            accessibilityState={{ selected: active }}
          >
            <Text style={[styles.toggleText, active && styles.toggleTextActive]}>
              {option === 'familia' ? 'Família' : 'Só eu'}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

export function StatTile({
  label,
  value,
  hint,
  tone = 'neutral',
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: 'neutral' | 'alert';
}): React.ReactElement {
  return (
    <View style={styles.tile}>
      <Text style={styles.tileLabel}>{label}</Text>
      <Text style={[styles.tileValue, tone === 'alert' && { color: colors.red }]}>{value}</Text>
      {hint ? <Text style={styles.tileHint}>{hint}</Text> : null}
    </View>
  );
}

export function BudgetRow({
  name,
  cap,
  spent,
  usedPct,
  severity,
  overflow,
}: {
  name: string;
  cap: string;
  spent: string;
  usedPct: string;
  severity: 'INFO' | 'ATENCAO' | 'CRITICO';
  overflow: string;
}): React.ReactElement {
  return (
    <View style={styles.budgetRow}>
      <View style={styles.budgetHeader}>
        <Text style={styles.budgetName}>{name}</Text>
        <Text style={styles.budgetValue}>
          {money(spent)} <Text style={styles.budgetCap}>de {money(cap)}</Text>
        </Text>
      </View>
      <ProgressBar ratio={Number(usedPct)} severity={severity} />
      <Text style={[styles.budgetHint, severity === 'CRITICO' && { color: colors.red }]}>
        {Number(overflow) > 0
          ? `No ritmo atual estoura em ${money(overflow)}`
          : `${percent(usedPct)} do teto usado`}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
    marginBottom: spacing.md,
  },
  sectionTitle: {
    ...typography.section,
    color: colors.textFaint,
    marginBottom: spacing.sm,
  },
  progressTrack: {
    height: 6,
    backgroundColor: colors.surfaceAlt,
    borderRadius: radius.pill,
    overflow: 'hidden',
  },
  progressFill: { height: '100%', borderRadius: radius.pill },
  toggle: {
    flexDirection: 'row',
    backgroundColor: colors.surfaceAlt,
    borderRadius: radius.pill,
    padding: 3,
  },
  toggleOption: {
    paddingVertical: 6,
    paddingHorizontal: spacing.md,
    borderRadius: radius.pill,
  },
  toggleOptionActive: { backgroundColor: colors.red },
  toggleText: { ...typography.caption, color: colors.textMuted },
  toggleTextActive: { color: colors.white },
  tile: {
    flex: 1,
    backgroundColor: colors.surfaceAlt,
    borderRadius: radius.md,
    padding: spacing.md,
  },
  tileLabel: { ...typography.caption, color: colors.textFaint },
  tileValue: { ...typography.title, color: colors.text, marginTop: spacing.xs },
  tileHint: { ...typography.caption, color: colors.textMuted, marginTop: 2 },
  budgetRow: { marginBottom: spacing.md },
  budgetHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: spacing.sm,
  },
  budgetName: { ...typography.body, color: colors.text },
  budgetValue: { ...typography.body, color: colors.text },
  budgetCap: { color: colors.textFaint },
  budgetHint: { ...typography.caption, color: colors.textMuted, marginTop: spacing.xs },
});
