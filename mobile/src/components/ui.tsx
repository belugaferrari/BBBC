/** Blocos visuais reaproveitados pelas telas. */

import React from 'react';
import {
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
  type KeyboardTypeOptions,
  type RefreshControlProps,
  type ViewStyle,
} from 'react-native';

import { colors, layout, radius, severityColor, spacing, toque, typography } from '@/theme';
import { money, percent } from '@/theme/format';
import type { Scope } from '@/api/types';

/**
 * Moldura de tela que rola.
 *
 * Centraliza a coluna de conteudo e limita a largura - ver `layout.coluna`.
 * Telas que precisam de rodape fixo montam o ScrollView na mao e usam
 * `layout.coluna` direto; as outras usam isto.
 */
export function Screen({
  children,
  refreshControl,
}: {
  children: React.ReactNode;
  refreshControl?: React.ReactElement<RefreshControlProps>;
}): React.ReactElement {
  return (
    <ScrollView
      style={styles.screen}
      contentContainerStyle={[styles.screenContent, layout.coluna]}
      keyboardShouldPersistTaps="handled"
      refreshControl={refreshControl}
    >
      {children}
    </ScrollView>
  );
}

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

// ---------------------------------------------------------------- formulario ---

/**
 * Campo de texto com rotulo.
 *
 * `opcional` escreve "opcional" ao lado do rotulo, em vez de marcar o
 * obrigatorio com asterisco. Num formulario onde quase tudo e dispensavel, dizer
 * o que da para pular e mais util que avisar o que nao da.
 */
export function Field({
  label,
  value,
  onChangeText,
  placeholder,
  opcional = false,
  ajuda,
  keyboardType,
  autoFocus,
  multiline,
  autoCapitalize,
}: {
  label: string;
  value: string;
  onChangeText: (text: string) => void;
  placeholder?: string;
  opcional?: boolean;
  ajuda?: string;
  keyboardType?: KeyboardTypeOptions;
  autoFocus?: boolean;
  multiline?: boolean;
  autoCapitalize?: 'none' | 'sentences' | 'words' | 'characters';
}): React.ReactElement {
  return (
    <View style={styles.field}>
      {label ? (
        <View style={styles.fieldHead}>
          <Text style={styles.fieldLabel}>{label}</Text>
          {opcional ? <Text style={styles.fieldOptional}>opcional</Text> : null}
        </View>
      ) : null}
      <TextInput
        style={[styles.input, multiline && styles.inputMultiline]}
        value={value}
        onChangeText={onChangeText}
        placeholder={placeholder}
        placeholderTextColor={colors.textFaint}
        keyboardType={keyboardType}
        autoFocus={autoFocus}
        multiline={multiline}
        autoCapitalize={autoCapitalize}
      />
      {ajuda ? <Text style={styles.fieldHelp}>{ajuda}</Text> : null}
    </View>
  );
}

export function Botao({
  children,
  onPress,
  disabled = false,
  tom = 'principal',
}: {
  children: string;
  onPress: () => void;
  disabled?: boolean;
  tom?: 'principal' | 'secundario';
}): React.ReactElement {
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      accessibilityRole="button"
      style={[
        styles.button,
        tom === 'secundario' && styles.buttonSecondary,
        disabled && styles.buttonOff,
      ]}
    >
      <Text style={[styles.buttonText, tom === 'secundario' && styles.buttonTextSecondary]}>
        {children}
      </Text>
    </Pressable>
  );
}

/** Opcao em forma de pilula. Varias lado a lado fazem um seletor. */
export function Chip({
  children,
  active,
  onPress,
}: {
  children: string;
  active: boolean;
  onPress: () => void;
}): React.ReactElement {
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityState={{ selected: active }}
      style={[styles.chip, active && styles.chipActive]}
    >
      <Text style={[styles.chipText, active && styles.chipTextActive]}>{children}</Text>
    </Pressable>
  );
}

/** Linha com rotulo e marcador de ligado/desligado. */
export function SwitchRow({
  label,
  ajuda,
  value,
  onChange,
}: {
  label: string;
  ajuda?: string;
  value: boolean;
  onChange: (value: boolean) => void;
}): React.ReactElement {
  return (
    <Pressable
      onPress={() => onChange(!value)}
      accessibilityRole="switch"
      accessibilityState={{ checked: value }}
      style={styles.switchRow}
    >
      <View style={styles.switchMain}>
        <Text style={styles.switchLabel}>{label}</Text>
        {ajuda ? <Text style={styles.switchHelp}>{ajuda}</Text> : null}
      </View>
      <View style={[styles.switchBox, value && styles.switchBoxOn]}>
        {value ? <Text style={styles.switchCheck}>✓</Text> : null}
      </View>
    </Pressable>
  );
}

/** Linha clicavel de menu, com seta. */
export function MenuRow({
  title,
  subtitle,
  onPress,
  icon,
}: {
  title: string;
  subtitle?: string;
  onPress: () => void;
  icon?: string;
}): React.ReactElement {
  return (
    <Pressable onPress={onPress} accessibilityRole="button" style={styles.menuRow}>
      {icon ? <Text style={styles.menuIcon}>{icon}</Text> : null}
      <View style={styles.menuMain}>
        <Text style={styles.menuTitle}>{title}</Text>
        {subtitle ? <Text style={styles.menuSubtitle}>{subtitle}</Text> : null}
      </View>
      <Text style={styles.menuArrow}>›</Text>
    </Pressable>
  );
}

export function Mensagem({
  children,
  tom = 'neutro',
}: {
  children: string;
  tom?: 'neutro' | 'erro' | 'ok';
}): React.ReactElement {
  return (
    <View
      style={[
        styles.mensagem,
        tom === 'erro' && styles.mensagemErro,
        tom === 'ok' && styles.mensagemOk,
      ]}
    >
      <Text
        style={[
          styles.mensagemTexto,
          tom === 'erro' && { color: colors.red },
          tom === 'ok' && { color: colors.text },
        ]}
      >
        {children}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  screenContent: { padding: spacing.md, paddingBottom: spacing.xl },
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
    marginBottom: spacing.sm,
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
    paddingVertical: 8,
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

  field: { marginBottom: spacing.md },
  fieldHead: { flexDirection: 'row', alignItems: 'baseline', gap: spacing.sm },
  fieldLabel: { ...typography.caption, color: colors.textMuted, marginBottom: 6 },
  fieldOptional: { ...typography.caption, color: colors.textFaint, fontSize: 12 },
  input: {
    backgroundColor: colors.surfaceAlt,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    paddingHorizontal: spacing.md,
    paddingVertical: 12,
    minHeight: toque,
    ...typography.body,
    color: colors.text,
  },
  inputMultiline: { minHeight: toque * 1.8, textAlignVertical: 'top' },
  fieldHelp: { ...typography.caption, color: colors.textFaint, marginTop: 6 },
  button: {
    backgroundColor: colors.red,
    borderRadius: radius.md,
    minHeight: toque + 4,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: spacing.lg,
    marginTop: spacing.sm,
  },
  buttonSecondary: {
    backgroundColor: 'transparent',
    borderWidth: 1,
    borderColor: colors.border,
  },
  buttonOff: { backgroundColor: colors.surfaceAlt, borderColor: colors.border },
  buttonText: { ...typography.body, color: colors.white, fontWeight: '700' },
  buttonTextSecondary: { color: colors.textMuted },
  chip: {
    paddingHorizontal: spacing.md,
    paddingVertical: 10,
    minHeight: 40,
    justifyContent: 'center',
    borderRadius: radius.pill,
    backgroundColor: colors.surfaceAlt,
    borderWidth: 1,
    borderColor: colors.border,
  },
  chipActive: { backgroundColor: colors.red, borderColor: colors.red },
  chipText: { ...typography.caption, color: colors.textMuted },
  chipTextActive: { color: colors.white, fontWeight: '700' },
  switchRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    minHeight: toque,
    paddingVertical: spacing.sm,
  },
  switchMain: { flex: 1 },
  switchLabel: { ...typography.body, color: colors.text },
  switchHelp: { ...typography.caption, color: colors.textFaint, marginTop: 2 },
  switchBox: {
    width: 26,
    height: 26,
    borderRadius: 7,
    borderWidth: 1.5,
    borderColor: colors.border,
    alignItems: 'center',
    justifyContent: 'center',
  },
  switchBoxOn: { backgroundColor: colors.red, borderColor: colors.red },
  switchCheck: { color: colors.white, fontSize: 15, fontWeight: '700' },
  menuRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    minHeight: toque + 10,
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  menuIcon: { fontSize: 22, color: colors.red, width: 28, textAlign: 'center' },
  menuMain: { flex: 1 },
  menuTitle: { ...typography.body, color: colors.text },
  menuSubtitle: { ...typography.caption, color: colors.textFaint, marginTop: 2 },
  menuArrow: { fontSize: 26, color: colors.textFaint },
  mensagem: {
    backgroundColor: colors.surfaceAlt,
    borderRadius: radius.md,
    padding: spacing.md,
    marginBottom: spacing.sm,
  },
  mensagemErro: { backgroundColor: colors.redSoft },
  mensagemOk: { backgroundColor: colors.whiteSoft },
  mensagemTexto: { ...typography.caption, color: colors.textMuted },
});
