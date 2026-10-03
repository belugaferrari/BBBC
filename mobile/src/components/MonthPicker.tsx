/**
 * Seletor de mês: "‹ outubro de 2026 ›", com atalho para voltar a hoje.
 *
 * Simples de propósito. Um calendário completo serviria para escolher um dia, e
 * aqui o que se escolhe é um mês — e quase sempre o atual ou o anterior, que são
 * um toque de distância.
 */

import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { colors, radius, spacing, toque, typography } from '@/theme';
import { monthLabel } from '@/theme/format';

export function mesAtualISO(): string {
  const hoje = new Date();
  return `${hoje.getFullYear()}-${String(hoje.getMonth() + 1).padStart(2, '0')}-01`;
}

/** Anda `passo` meses a partir de um primeiro-dia-do-mês em ISO. */
export function andarMes(iso: string, passo: number): string {
  const [ano, mes] = iso.split('-').map(Number);
  const total = ano * 12 + (mes - 1) + passo;
  return `${Math.floor(total / 12)}-${String((total % 12) + 1).padStart(2, '0')}-01`;
}

export function MonthPicker({
  value,
  onChange,
}: {
  value: string;
  onChange: (iso: string) => void;
}): React.ReactElement {
  const atual = value === mesAtualISO();
  return (
    <View style={styles.linha}>
      <Pressable
        onPress={() => onChange(andarMes(value, -1))}
        accessibilityRole="button"
        accessibilityLabel="Mês anterior"
        style={styles.seta}
      >
        <Text style={styles.setaTexto}>‹</Text>
      </Pressable>

      <View style={styles.meio}>
        <Text style={styles.mes}>{monthLabel(value)}</Text>
        {!atual ? (
          <Pressable onPress={() => onChange(mesAtualISO())} accessibilityRole="button">
            <Text style={styles.voltar}>voltar para este mês</Text>
          </Pressable>
        ) : null}
      </View>

      <Pressable
        onPress={() => onChange(andarMes(value, 1))}
        accessibilityRole="button"
        accessibilityLabel="Mês seguinte"
        style={[styles.seta, atual && styles.setaFraca]}
        disabled={atual}
      >
        <Text style={[styles.setaTexto, atual && { color: colors.border }]}>›</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  linha: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: spacing.md,
  },
  seta: {
    width: toque,
    height: toque,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radius.pill,
    backgroundColor: colors.surfaceAlt,
  },
  setaFraca: { backgroundColor: 'transparent' },
  setaTexto: { fontSize: 26, color: colors.text, lineHeight: 30 },
  meio: { flex: 1, alignItems: 'center' },
  mes: { ...typography.body, color: colors.text, fontWeight: '700' },
  voltar: { ...typography.caption, color: colors.red, marginTop: 2 },
});
