/**
 * Gastos: lista conciliada do Open Finance + manuais, com filtro individual /
 * familiar e recategorizacao (que alimenta o aprendizado de regras).
 */

import React, { useMemo, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  Modal,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import { useCategories, useRecategorize, useTransactions } from '@/api/queries';
import type { Category, Scope, Transaction } from '@/api/types';
import { Card, ScopeToggle, SectionTitle } from '@/components/ui';
import { colors, radius, spacing, typography } from '@/theme';
import { dayLabel, money } from '@/theme/format';

function monthRange(): { start: string; end: string } {
  const now = new Date();
  const start = new Date(now.getFullYear(), now.getMonth(), 1);
  const end = new Date(now.getFullYear(), now.getMonth() + 1, 0);
  return { start: start.toISOString().slice(0, 10), end: end.toISOString().slice(0, 10) };
}

/** Achata a arvore para o seletor, preservando a hierarquia na indentacao. */
function flatten(categories: Category[], depth = 0): { category: Category; depth: number }[] {
  return categories.flatMap((category) => [
    { category, depth },
    ...flatten(category.children, depth + 1),
  ]);
}

export function ExpensesScreen(): React.ReactElement {
  const [scope, setScope] = useState<Scope>('familia');
  const [search, setSearch] = useState('');
  const [onlyPending, setOnlyPending] = useState(false);
  const [editing, setEditing] = useState<Transaction | null>(null);

  const range = useMemo(monthRange, []);
  const { data: transactions, isLoading } = useTransactions({
    ...range,
    scope,
    search: search || undefined,
    only_uncategorized: onlyPending || undefined,
  });
  const { data: categories } = useCategories();
  const recategorize = useRecategorize();

  const categoryName = useMemo(() => {
    const map = new Map<string, string>();
    flatten(categories ?? []).forEach(({ category }) => map.set(category.id, category.name));
    return map;
  }, [categories]);

  const expenseOptions = useMemo(
    () => flatten(categories ?? []).filter(({ category }) => category.kind === 'DESPESA'),
    [categories],
  );

  return (
    <View style={styles.screen}>
      <View style={styles.toolbar}>
        <TextInput
          value={search}
          onChangeText={setSearch}
          placeholder="Buscar lancamento"
          placeholderTextColor={colors.textFaint}
          style={styles.search}
        />
        <ScopeToggle value={scope} onChange={setScope} />
      </View>

      <Pressable onPress={() => setOnlyPending((v) => !v)} style={styles.filterChip}>
        <Text style={[styles.filterText, onlyPending && { color: colors.white }]}>
          {onlyPending ? '✓ ' : ''}Só sem categoria
        </Text>
      </Pressable>

      {isLoading ? (
        <ActivityIndicator color={colors.red} style={{ marginTop: spacing.xl }} />
      ) : (
        <FlatList
          data={transactions ?? []}
          keyExtractor={(item) => item.id}
          contentContainerStyle={styles.list}
          ListEmptyComponent={<Text style={styles.empty}>Nenhum lancamento no periodo.</Text>}
          renderItem={({ item }) => (
            <Pressable onPress={() => setEditing(item)} style={styles.row}>
              <View style={styles.rowMain}>
                <Text style={styles.rowTitle} numberOfLines={1}>
                  {item.description}
                </Text>
                <Text style={styles.rowSubtitle}>
                  {dayLabel(item.booked_on)}
                  {' · '}
                  {item.category_id
                    ? categoryName.get(item.category_id) ?? 'Categoria'
                    : 'Sem categoria'}
                  {item.auto_confidence && Number(item.auto_confidence) < 0.6 ? ' · confirmar' : ''}
                </Text>
              </View>
              <Text
                style={[
                  styles.rowAmount,
                  { color: item.direction === 'SAIDA' ? colors.red : colors.white },
                ]}
              >
                {item.direction === 'SAIDA' ? '-' : '+'}
                {money(item.amount)}
              </Text>
            </Pressable>
          )}
        />
      )}

      <Modal visible={editing !== null} animationType="slide" transparent>
        <View style={styles.modalBackdrop}>
          <View style={styles.modalSheet}>
            <SectionTitle>Categorizar</SectionTitle>
            <Text style={styles.modalDescription} numberOfLines={2}>
              {editing?.description}
            </Text>
            <Text style={styles.modalHint}>
              A escolha vira regra: proximos lancamentos deste fornecedor entram ja categorizados.
            </Text>
            <FlatList
              data={expenseOptions}
              keyExtractor={({ category }) => category.id}
              style={styles.modalList}
              renderItem={({ item }) => (
                <Pressable
                  style={[styles.option, { paddingLeft: spacing.md + item.depth * spacing.md }]}
                  onPress={() => {
                    if (editing) {
                      recategorize.mutate({ id: editing.id, category_id: item.category.id });
                    }
                    setEditing(null);
                  }}
                >
                  <Text style={styles.optionText}>{item.category.name}</Text>
                </Pressable>
              )}
            />
            <Pressable style={styles.close} onPress={() => setEditing(null)}>
              <Text style={styles.closeText}>Fechar</Text>
            </Pressable>
          </View>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background, padding: spacing.md },
  toolbar: { flexDirection: 'row', gap: spacing.sm, alignItems: 'center' },
  search: {
    flex: 1,
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    color: colors.text,
  },
  filterChip: { alignSelf: 'flex-start', paddingVertical: spacing.sm },
  filterText: { ...typography.caption, color: colors.textMuted },
  list: { paddingBottom: spacing.xl },
  empty: { ...typography.body, color: colors.textFaint, textAlign: 'center', marginTop: spacing.xl },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  rowMain: { flex: 1, paddingRight: spacing.md },
  rowTitle: { ...typography.body, color: colors.text },
  rowSubtitle: { ...typography.caption, color: colors.textMuted, marginTop: 2 },
  rowAmount: { ...typography.body },
  modalBackdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.6)', justifyContent: 'flex-end' },
  modalSheet: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: radius.lg,
    borderTopRightRadius: radius.lg,
    padding: spacing.md,
    maxHeight: '75%',
  },
  modalDescription: { ...typography.body, color: colors.text },
  modalHint: { ...typography.caption, color: colors.textMuted, marginTop: spacing.xs },
  modalList: { marginTop: spacing.md },
  option: { paddingVertical: spacing.sm },
  optionText: { ...typography.body, color: colors.text },
  close: { alignItems: 'center', paddingVertical: spacing.md },
  closeText: { ...typography.body, color: colors.red },
});
