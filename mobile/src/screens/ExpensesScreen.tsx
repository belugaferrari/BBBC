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
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import {
  useCategories,
  useMembers,
  useRecategorize,
  useSpendByCategory,
  useTransactions,
} from '@/api/queries';
import type { Category, Scope, Transaction } from '@/api/types';
import { Card, ProgressBar, ScopeToggle, SectionTitle } from '@/components/ui';
import { colors, radius, spacing, typography } from '@/theme';
import { dayLabel, money, percent } from '@/theme/format';

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
  const [modo, setModo] = useState<'lista' | 'categorias'>('lista');
  // 1 agrupa nos grandes blocos, 3 desce até a subcategoria
  const [nivel, setNivel] = useState(2);

  const range = useMemo(monthRange, []);
  const { data: transactions, isLoading } = useTransactions({
    ...range,
    scope,
    search: search || undefined,
    only_uncategorized: onlyPending || undefined,
  });
  const { data: categories } = useCategories();
  const { data: members } = useMembers();
  const segmentado = useSpendByCategory({ ...range, scope, depth: nivel });
  const recategorize = useRecategorize();

  const responsavel = useMemo(() => {
    const mapa = new Map<string, string>();
    (members ?? []).forEach((m) => mapa.set(m.id, m.name));
    return mapa;
  }, [members]);

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

      <View style={styles.viewSwitch}>
        {(['lista', 'categorias'] as const).map((opcao) => (
          <Pressable
            key={opcao}
            onPress={() => setModo(opcao)}
            style={[styles.switchOption, modo === opcao && styles.switchOptionOn]}
            accessibilityRole="button"
            accessibilityState={{ selected: modo === opcao }}
          >
            <Text style={[styles.switchText, modo === opcao && { color: colors.white }]}>
              {opcao === 'lista' ? 'Lançamentos' : 'Por categoria'}
            </Text>
          </Pressable>
        ))}
      </View>

      {modo === 'lista' && (
        <Pressable onPress={() => setOnlyPending((v) => !v)} style={styles.filterChip}>
          <Text style={[styles.filterText, onlyPending && { color: colors.white }]}>
            {onlyPending ? '✓ ' : ''}Só sem categoria
          </Text>
        </Pressable>
      )}

      {modo === 'categorias' && (
        <ScrollView style={styles.segmented} contentContainerStyle={styles.list}>
          <View style={styles.levels}>
            {[1, 2, 3].map((n) => (
              <Pressable
                key={n}
                onPress={() => setNivel(n)}
                style={[styles.level, nivel === n && styles.levelOn]}
              >
                <Text style={[styles.levelText, nivel === n && { color: colors.white }]}>
                  {n === 1 ? 'Blocos' : n === 2 ? 'Grupos' : 'Detalhe'}
                </Text>
              </Pressable>
            ))}
          </View>

          {segmentado.isLoading ? (
            <ActivityIndicator color={colors.red} style={{ marginTop: spacing.lg }} />
          ) : (
            <>
              <Card>
                <SectionTitle>Total do mês</SectionTitle>
                <Text style={styles.bigTotal}>{money(segmentado.data?.total ?? 0)}</Text>
                {(segmentado.data?.categories ?? []).map((fatia) => (
                  <View key={fatia.path} style={styles.slice}>
                    <View style={styles.sliceHead}>
                      <Text style={styles.sliceName} numberOfLines={1}>{fatia.name}</Text>
                      <Text style={styles.sliceValue}>{money(fatia.total)}</Text>
                    </View>
                    <ProgressBar ratio={Number(fatia.share)} />
                    <Text style={styles.sliceHint}>
                      {percent(fatia.share, 0)} do mês · {fatia.transactions}{' '}
                      {fatia.transactions === 1 ? 'lançamento' : 'lançamentos'}
                    </Text>
                  </View>
                ))}
                {(segmentado.data?.categories ?? []).length === 0 && (
                  <Text style={styles.empty}>Nenhum gasto no período.</Text>
                )}
              </Card>

              <Card>
                <SectionTitle>Quem gastou</SectionTitle>
                {(segmentado.data?.by_member ?? []).map((pessoa) => (
                  <View key={pessoa.member_id} style={styles.slice}>
                    <View style={styles.sliceHead}>
                      <Text style={styles.sliceName}>{pessoa.name}</Text>
                      <Text style={styles.sliceValue}>{money(pessoa.total)}</Text>
                    </View>
                    <ProgressBar ratio={Number(pessoa.share)} />
                  </View>
                ))}
              </Card>
            </>
          )}
        </ScrollView>
      )}

      {modo === 'lista' && isLoading ? (
        <ActivityIndicator color={colors.red} style={{ marginTop: spacing.xl }} />
      ) : modo === 'lista' ? (
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
                  {responsavel.get(item.owner_member_id)
                    ? ` · ${responsavel.get(item.owner_member_id)}`
                    : ''}
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
      ) : null}

      <Modal visible={editing !== null} animationType="slide" transparent>
        <View style={styles.modalBackdrop}>
          <View style={styles.modalSheet}>
            <SectionTitle>Categorizar</SectionTitle>
            <Text style={styles.modalDescription} numberOfLines={2}>
              {editing?.description}
            </Text>
            <Text style={styles.modalHint}>
              A escolha vira regra: próximos lançamentos deste fornecedor entram já categorizados.
            </Text>

            <SectionTitle>Responsável</SectionTitle>
            <View style={styles.people}>
              {(members ?? [])
                .filter((m) => m.can_login)
                .map((pessoa) => {
                  const ativo = editing?.owner_member_id === pessoa.id;
                  return (
                    <Pressable
                      key={pessoa.id}
                      style={[styles.person, ativo && styles.personOn]}
                      onPress={() => {
                        if (!editing) return;
                        recategorize.mutate({ id: editing.id, owner_member_id: pessoa.id });
                        setEditing({ ...editing, owner_member_id: pessoa.id });
                      }}
                    >
                      <Text style={[styles.personText, ativo && { color: colors.white }]}>
                        {pessoa.name}
                      </Text>
                    </Pressable>
                  );
                })}
            </View>
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
  viewSwitch: {
    flexDirection: 'row',
    backgroundColor: colors.surfaceAlt,
    borderRadius: radius.pill,
    padding: 3,
    marginTop: spacing.sm,
  },
  switchOption: {
    flex: 1,
    paddingVertical: 7,
    borderRadius: radius.pill,
    alignItems: 'center',
  },
  switchOptionOn: { backgroundColor: colors.red },
  switchText: { ...typography.caption, color: colors.textMuted },
  segmented: { marginTop: spacing.sm },
  levels: { flexDirection: 'row', gap: spacing.sm, marginBottom: spacing.md },
  level: {
    paddingHorizontal: spacing.md,
    paddingVertical: 6,
    borderRadius: radius.pill,
    backgroundColor: colors.surfaceAlt,
  },
  levelOn: { backgroundColor: colors.red },
  levelText: { ...typography.caption, color: colors.textMuted },
  bigTotal: {
    ...typography.title,
    color: colors.text,
    marginBottom: spacing.md,
  },
  slice: { marginBottom: spacing.md },
  sliceHead: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    gap: spacing.sm,
    marginBottom: spacing.sm,
  },
  sliceName: { ...typography.body, color: colors.text, flex: 1 },
  sliceValue: { ...typography.body, color: colors.text },
  sliceHint: { ...typography.caption, color: colors.textMuted, marginTop: spacing.xs },
  people: { flexDirection: 'row', gap: spacing.sm, marginBottom: spacing.sm },
  person: {
    paddingHorizontal: spacing.md,
    paddingVertical: 7,
    borderRadius: radius.pill,
    backgroundColor: colors.surfaceAlt,
  },
  personOn: { backgroundColor: colors.red },
  personText: { ...typography.caption, color: colors.textMuted },
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
