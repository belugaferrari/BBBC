/**
 * Categorias: as quinze, com a meta do mês e o quanto já foi gasto em cada uma.
 *
 * É a tela de controle do mês. Cada linha mostra a barra de teto, e tocar nela
 * abre a leitura no tempo (mês anterior, mesmo mês do ano passado, doze meses).
 * As subcategorias ficam recolhidas atrás da seta: as quinze cabem numa tela, as
 * sessenta não — e abrir tudo de uma vez transformaria a tela de controle numa
 * lista para rolar.
 *
 * O gasto de cada linha já inclui a subárvore, então as linhas não se somam
 * entre si. O total do rodapé vem do servidor, que soma só o primeiro nível.
 */

import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import React, { useMemo, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';

import { useCategoryOverview, useCreateCategory } from '@/api/queries';
import type { CategoryOverviewRow } from '@/api/types';
import { MonthPicker, mesAtualISO } from '@/components/MonthPicker';
import {
  Botao,
  Card,
  Field,
  Mensagem,
  ProgressBar,
  Screen,
  SectionTitle,
} from '@/components/ui';
import { colors, radius, spacing, typography } from '@/theme';
import { money, percent } from '@/theme/format';

type Destino = { Categoria: { id: string; nome: string; mes: string } };

/** Vermelho só quando estourou de verdade; laranja quando está perto. */
function severidade(usado: number): 'INFO' | 'ATENCAO' | 'CRITICO' {
  if (usado >= 1) return 'CRITICO';
  if (usado >= 0.8) return 'ATENCAO';
  return 'INFO';
}

export function CategoriesScreen(): React.ReactElement {
  const navigation = useNavigation<NativeStackNavigationProp<Destino>>();
  const [mes, setMes] = useState(mesAtualISO);
  const [abertas, setAbertas] = useState<Set<string>>(new Set());
  const [criando, setCriando] = useState(false);
  const [nome, setNome] = useState('');
  const [erro, setErro] = useState<string | null>(null);

  const { data, isLoading } = useCategoryOverview(mes);
  const criar = useCreateCategory();

  const { baldes, filhasDe } = useMemo(() => {
    const linhas = data?.categories ?? [];
    // só a árvore de despesa: receita e transferência não têm meta de gasto
    const deDespesa = linhas.filter((l) => l.path.startsWith('despesas'));
    return {
      baldes: deDespesa.filter((l) => l.depth === 1),
      filhasDe: (id: string) => deDespesa.filter((l) => l.parent_id === id),
    };
  }, [data]);

  function alternar(id: string): void {
    setAbertas((atual) => {
      const proximo = new Set(atual);
      if (proximo.has(id)) proximo.delete(id);
      else proximo.add(id);
      return proximo;
    });
  }

  function abrir(linha: CategoryOverviewRow): void {
    navigation.navigate('Categoria', { id: linha.id, nome: linha.name, mes });
  }

  async function gravarNova(): Promise<void> {
    if (!nome.trim()) return;
    setErro(null);
    try {
      await criar.mutateAsync({ name: nome.trim() });
      setNome('');
      setCriando(false);
    } catch (err) {
      setErro(err instanceof Error ? err.message : 'Nao consegui criar a categoria.');
    }
  }

  const totalGasto = Number(data?.total_spent ?? 0);
  const totalMeta = Number(data?.total_cap ?? 0);

  return (
    <Screen>
      <MonthPicker value={mes} onChange={setMes} />

      <Card>
        <View style={styles.totalLinha}>
          <View>
            <Text style={styles.totalRotulo}>Gasto no mês</Text>
            <Text style={styles.totalValor}>{money(totalGasto)}</Text>
          </View>
          <View style={styles.totalDireita}>
            <Text style={styles.totalRotulo}>Somando as metas</Text>
            <Text style={styles.totalMeta}>
              {totalMeta > 0 ? money(totalMeta) : 'nenhuma ainda'}
            </Text>
          </View>
        </View>
        {totalMeta > 0 ? (
          <>
            <ProgressBar ratio={totalGasto / totalMeta} severity={severidade(totalGasto / totalMeta)} />
            <Text style={styles.totalHint}>
              {totalGasto > totalMeta
                ? `${money(totalGasto - totalMeta)} acima do combinado`
                : `${money(totalMeta - totalGasto)} ainda cabem no mês`}
            </Text>
          </>
        ) : (
          <Text style={styles.totalHint}>
            Toque numa categoria para definir a meta mensal dela.
          </Text>
        )}
      </Card>

      <SectionTitle>Categorias</SectionTitle>

      {isLoading ? (
        <ActivityIndicator color={colors.red} />
      ) : (
        baldes.map((balde) => {
          const filhas = filhasDe(balde.id);
          const aberta = abertas.has(balde.id);
          const meta = Number(balde.cap ?? 0);
          const gasto = Number(balde.spent);
          const usado = meta > 0 ? gasto / meta : 0;

          return (
            <View key={balde.id} style={styles.bloco}>
              <Pressable
                onPress={() => abrir(balde)}
                accessibilityRole="button"
                style={styles.linha}
              >
                <View style={styles.linhaMain}>
                  <Text style={styles.nome}>{balde.name}</Text>
                  <Text style={styles.detalhe}>
                    {meta > 0
                      ? `${money(gasto)} de ${money(meta)} · ${percent(usado)}`
                      : `${money(gasto)} · sem meta`}
                  </Text>
                </View>
                {filhas.length > 0 ? (
                  <Pressable
                    onPress={() => alternar(balde.id)}
                    accessibilityRole="button"
                    accessibilityLabel={
                      aberta
                        ? `Recolher subcategorias de ${balde.name}`
                        : `Ver subcategorias de ${balde.name}`
                    }
                    hitSlop={10}
                    style={styles.expandir}
                  >
                    <Text style={styles.expandirTexto}>{aberta ? '▾' : '▸'}</Text>
                  </Pressable>
                ) : null}
              </Pressable>

              {meta > 0 ? (
                <View style={styles.barra}>
                  <ProgressBar ratio={usado} severity={severidade(usado)} />
                </View>
              ) : null}

              {aberta
                ? filhas.map((filha) => (
                    <Pressable
                      key={filha.id}
                      onPress={() => abrir(filha)}
                      accessibilityRole="button"
                      style={styles.filha}
                    >
                      <Text style={styles.filhaNome}>{filha.name}</Text>
                      <Text style={styles.filhaValor}>
                        {money(filha.spent)}
                        {filha.cap ? ` de ${money(filha.cap)}` : ''}
                      </Text>
                    </Pressable>
                  ))
                : null}
            </View>
          );
        })
      )}

      {criando ? (
        <Card>
          <SectionTitle>Nova categoria</SectionTitle>
          {erro ? <Mensagem tom="erro">{erro}</Mensagem> : null}
          <Field
            label="Nome"
            value={nome}
            onChangeText={setNome}
            placeholder="Ex.: Pets"
            autoFocus
            autoCapitalize="sentences"
            ajuda="Para criar uma subcategoria, entre na categoria e use “Nova subcategoria”."
          />
          <Botao onPress={gravarNova} disabled={!nome.trim() || criar.isPending}>
            {criar.isPending ? 'Criando…' : 'Criar categoria'}
          </Botao>
          <Botao
            tom="secundario"
            onPress={() => {
              setCriando(false);
              setNome('');
              setErro(null);
            }}
          >
            Cancelar
          </Botao>
        </Card>
      ) : (
        <Botao tom="secundario" onPress={() => setCriando(true)}>
          ＋ Nova categoria
        </Botao>
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  totalLinha: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: spacing.sm },
  totalDireita: { alignItems: 'flex-end' },
  totalRotulo: { ...typography.caption, color: colors.textFaint },
  totalValor: { ...typography.title, color: colors.text },
  totalMeta: { ...typography.body, color: colors.textMuted, marginTop: spacing.xs },
  totalHint: { ...typography.caption, color: colors.textMuted, marginTop: spacing.sm },
  bloco: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    marginBottom: spacing.sm,
  },
  linha: { flexDirection: 'row', alignItems: 'center', minHeight: 44 },
  linhaMain: { flex: 1 },
  nome: { ...typography.body, color: colors.text },
  detalhe: { ...typography.caption, color: colors.textMuted, marginTop: 2 },
  expandir: { width: 36, alignItems: 'center', justifyContent: 'center' },
  expandirTexto: { fontSize: 18, color: colors.textFaint },
  barra: { marginTop: spacing.xs, marginBottom: spacing.xs },
  filha: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    minHeight: 40,
    paddingLeft: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  filhaNome: { ...typography.caption, color: colors.textMuted, flex: 1 },
  filhaValor: { ...typography.caption, color: colors.text },
});
