/**
 * Importar extrato: escolher arquivo, conferir e confirmar.
 *
 * A tela existe por causa do passo do meio. O backend nunca grava nada no
 * envio - o que chega aqui e uma proposta, e o usuario decide linha a linha.
 * Linhas ja existentes vem desmarcadas, com o motivo escrito.
 */

import * as DocumentPicker from 'expo-document-picker';
import React, { useMemo, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';

import { useAccounts } from '@/api/queries';
import { confirmImport, uploadStatement } from '@/api/imports';
import type { ImportPreviewRow, StatementImport } from '@/api/types';
import { Card, MoneyValue, SectionTitle } from '@/components/ui';
import { colors, radius, spacing, typography } from '@/theme';
import { dayLabel, money } from '@/theme/format';

type Phase = 'escolha' | 'lendo' | 'conferencia' | 'gravando' | 'pronto';

const ACCEPTED = [
  'application/x-ofx',
  'application/pdf',
  'text/csv',
  'text/comma-separated-values',
  'text/plain',
  '*/*',
];

export function ImportScreen(): React.ReactElement {
  const { data: accounts } = useAccounts();
  const [accountId, setAccountId] = useState<string | null>(null);
  const [phase, setPhase] = useState<Phase>('escolha');
  const [batch, setBatch] = useState<StatementImport | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [error, setError] = useState<string | null>(null);

  const conta = accountId ?? accounts?.[0]?.id ?? null;

  const totals = useMemo(() => {
    if (!batch) return { entrada: 0, saida: 0 };
    return batch.preview
      .filter((row) => selected.has(row.index))
      .reduce(
        (acc, row) => {
          const value = Number(row.amount);
          if (row.direction === 'ENTRADA') acc.entrada += value;
          else acc.saida += value;
          return acc;
        },
        { entrada: 0, saida: 0 },
      );
  }, [batch, selected]);

  async function escolherArquivo(): Promise<void> {
    if (!conta) {
      setError('Cadastre uma conta antes de importar.');
      return;
    }
    const picked = await DocumentPicker.getDocumentAsync({
      type: ACCEPTED,
      copyToCacheDirectory: true,
    });
    if (picked.canceled || !picked.assets?.[0]) return;

    setPhase('lendo');
    setError(null);
    try {
      const resultado = await uploadStatement(conta, picked.assets[0]);
      setBatch(resultado);
      setSelected(new Set(resultado.preview.filter((r) => r.selected).map((r) => r.index)));
      setPhase('conferencia');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Nao consegui ler o arquivo');
      setPhase('escolha');
    }
  }

  async function confirmar(): Promise<void> {
    if (!batch) return;
    setPhase('gravando');
    try {
      const resultado = await confirmImport(batch.id, [...selected]);
      setBatch(resultado);
      setPhase('pronto');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Nao consegui confirmar');
      setPhase('conferencia');
    }
  }

  function alternar(index: number): void {
    setSelected((atual) => {
      const proximo = new Set(atual);
      if (proximo.has(index)) proximo.delete(index);
      else proximo.add(index);
      return proximo;
    });
  }

  if (phase === 'lendo' || phase === 'gravando') {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={colors.red} />
        <Text style={styles.hint}>
          {phase === 'lendo' ? 'Lendo o extrato...' : 'Gravando os lancamentos...'}
        </Text>
      </View>
    );
  }

  if (phase === 'pronto' && batch) {
    return (
      <View style={styles.center}>
        <Text style={styles.done}>{batch.rows_imported}</Text>
        <Text style={styles.doneLabel}>
          {batch.rows_imported === 1 ? 'lancamento importado' : 'lancamentos importados'}
        </Text>
        {batch.rows_duplicated > 0 && (
          <Text style={styles.hint}>
            {batch.rows_duplicated} ja existiam e foram ignorados.
          </Text>
        )}
        <Pressable
          style={styles.button}
          onPress={() => {
            setBatch(null);
            setSelected(new Set());
            setPhase('escolha');
          }}
        >
          <Text style={styles.buttonText}>Importar outro</Text>
        </Pressable>
      </View>
    );
  }

  if (phase === 'escolha' || !batch) {
    return (
      <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
        <SectionTitle>Conta de destino</SectionTitle>
        <View style={styles.accounts}>
          {(accounts ?? []).map((account) => {
            const ativa = account.id === conta;
            return (
              <Pressable
                key={account.id}
                onPress={() => setAccountId(account.id)}
                style={[styles.accountChip, ativa && styles.accountChipActive]}
              >
                <Text style={[styles.accountText, ativa && { color: colors.white }]}>
                  {account.name}
                </Text>
              </Pressable>
            );
          })}
        </View>

        <Card style={{ marginTop: spacing.lg }}>
          <SectionTitle>Enviar extrato</SectionTitle>
          <Text style={styles.explain}>
            Aceita <Text style={styles.strong}>OFX</Text>, <Text style={styles.strong}>CSV</Text> e{' '}
            <Text style={styles.strong}>PDF</Text>. Se o seu banco oferecer OFX, prefira: a
            leitura é exata, porque cada lançamento vem com identificador próprio.
          </Text>
          <Text style={styles.explain}>
            Nada é gravado no envio — você confere lançamento a lançamento antes de confirmar.
          </Text>
          {error ? <Text style={styles.error}>{error}</Text> : null}
          <Pressable style={styles.button} onPress={escolherArquivo}>
            <Text style={styles.buttonText}>Escolher arquivo</Text>
          </Pressable>
        </Card>
      </ScrollView>
    );
  }

  return (
    <View style={styles.screen}>
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.filename}>{batch.filename}</Text>
        <Text style={styles.hint}>
          {batch.file_format} · {batch.rows_detected} lançamentos
          {batch.period_start
            ? ` · ${dayLabel(batch.period_start)} a ${dayLabel(batch.period_end ?? batch.period_start)}`
            : ''}
        </Text>

        {batch.warnings.map((aviso) => (
          <View key={aviso} style={styles.warning}>
            <Text style={styles.warningText}>{aviso}</Text>
          </View>
        ))}

        {batch.preview.map((row) => (
          <PreviewRow
            key={row.index}
            row={row}
            checked={selected.has(row.index)}
            onToggle={() => alternar(row.index)}
          />
        ))}
      </ScrollView>

      <View style={styles.footer}>
        <View>
          <Text style={styles.footerLabel}>
            {selected.size} de {batch.rows_detected} marcados
          </Text>
          <Text style={styles.footerTotals}>
            +{money(totals.entrada)} · −{money(totals.saida)}
          </Text>
        </View>
        <Pressable
          style={[styles.button, styles.buttonCompact, selected.size === 0 && styles.buttonOff]}
          onPress={confirmar}
          disabled={selected.size === 0}
        >
          <Text style={styles.buttonText}>Confirmar</Text>
        </Pressable>
      </View>
    </View>
  );
}

function PreviewRow({
  row,
  checked,
  onToggle,
}: {
  row: ImportPreviewRow;
  checked: boolean;
  onToggle: () => void;
}): React.ReactElement {
  return (
    <Pressable onPress={onToggle} style={styles.row}>
      <View style={[styles.checkbox, checked && styles.checkboxOn]}>
        {checked ? <Text style={styles.check}>✓</Text> : null}
      </View>
      <View style={styles.rowMain}>
        <Text style={styles.rowTitle} numberOfLines={1}>
          {row.description}
        </Text>
        <Text style={styles.rowSubtitle}>
          {dayLabel(row.booked_on)}
          {row.suggested_category_name ? ` · ${row.suggested_category_name}` : ' · sem categoria'}
        </Text>
        {row.duplicate_reason ? (
          <Text style={styles.duplicate}>{row.duplicate_reason}</Text>
        ) : null}
      </View>
      <MoneyValue value={row.amount} direction={row.direction === 'SAIDA' ? 'out' : 'in'} />
    </Pressable>
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
  explain: { ...typography.caption, color: colors.textMuted, marginBottom: spacing.sm },
  strong: { color: colors.text },
  hint: { ...typography.caption, color: colors.textMuted, marginTop: spacing.sm },
  error: { ...typography.caption, color: colors.red, marginBottom: spacing.sm },
  accounts: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  accountChip: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radius.pill,
    backgroundColor: colors.surfaceAlt,
  },
  accountChipActive: { backgroundColor: colors.red },
  accountText: { ...typography.caption, color: colors.textMuted },
  filename: { ...typography.title, color: colors.text },
  warning: {
    backgroundColor: colors.redSoft,
    borderRadius: radius.md,
    padding: spacing.md,
    marginTop: spacing.md,
  },
  warningText: { ...typography.caption, color: colors.red },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    gap: spacing.sm,
  },
  checkbox: {
    width: 22,
    height: 22,
    borderRadius: 6,
    borderWidth: 1.5,
    borderColor: colors.border,
    alignItems: 'center',
    justifyContent: 'center',
  },
  checkboxOn: { backgroundColor: colors.red, borderColor: colors.red },
  check: { color: colors.white, fontSize: 13, fontWeight: '700' },
  rowMain: { flex: 1 },
  rowTitle: { ...typography.body, color: colors.text },
  rowSubtitle: { ...typography.caption, color: colors.textMuted, marginTop: 2 },
  duplicate: { ...typography.caption, color: colors.red, marginTop: 2 },
  footer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    backgroundColor: colors.surface,
  },
  footerLabel: { ...typography.caption, color: colors.textMuted },
  footerTotals: { ...typography.body, color: colors.text, marginTop: 2 },
  button: {
    backgroundColor: colors.red,
    borderRadius: radius.md,
    padding: spacing.md,
    alignItems: 'center',
    marginTop: spacing.md,
  },
  buttonCompact: { marginTop: 0, paddingHorizontal: spacing.lg },
  buttonOff: { backgroundColor: colors.surfaceAlt },
  buttonText: { ...typography.body, color: colors.white },
  done: { ...typography.display, color: colors.white, fontSize: 56 },
  doneLabel: { ...typography.body, color: colors.textMuted },
});
