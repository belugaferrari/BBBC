/**
 * Uma categoria no tempo: o mês, a meta, o ano passado e os doze meses.
 *
 * As três comparações existem porque cada uma pega um tipo diferente de
 * problema. Contra a META: estou dentro do combinado. Contra o MESMO MÊS DO ANO
 * PASSADO: subiu de verdade ou é sazonalidade (escola em fevereiro, IPVA em
 * janeiro, presente em dezembro). Contra os DOZE MESES: qual é o tamanho normal
 * desta categoria, para o mês esquisito aparecer como esquisito.
 *
 * A mesma tela serve para a subcategoria — tocar em "Gasolina" dentro de
 * "Transporte" abre esta tela outra vez, com os números dela. É o que permite
 * descer no detalhe quando o balde grande estoura e não se sabe por quê.
 */

import { useNavigation, useRoute, type RouteProp } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import React, { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  useWindowDimensions,
  View,
} from 'react-native';

import {
  useCategoryAnalysis,
  useCreateCategory,
  useDeleteBudgetCap,
  useDeleteCategory,
  useSaveBudgetCap,
  useUpdateCategory,
} from '@/api/queries';
import { BarSeries } from '@/components/BarSeries';
import { MonthPicker } from '@/components/MonthPicker';
import {
  Botao,
  Card,
  Field,
  Mensagem,
  ProgressBar,
  Screen,
  SectionTitle,
  StatTile,
} from '@/components/ui';
import { colors, layout, spacing, typography } from '@/theme';
import { money, percent } from '@/theme/format';

type Params = { Categoria: { id: string; nome: string; mes: string } };

function severidade(usado: number): 'INFO' | 'ATENCAO' | 'CRITICO' {
  if (usado >= 1) return 'CRITICO';
  if (usado >= 0.8) return 'ATENCAO';
  return 'INFO';
}

/** "+18%" ou "−12%". Null quando não havia base de comparação. */
function variacao(pct: string | null): string | null {
  if (pct === null) return null;
  const n = Number(pct);
  return `${n >= 0 ? '+' : '−'}${percent(Math.abs(n), 0)}`;
}

function paraNumero(texto: string): number | null {
  const limpo = texto.trim().replace(/[^\d.,]/g, '').replace(/\./g, '').replace(',', '.');
  if (!limpo) return null;
  const n = Number(limpo);
  return Number.isFinite(n) && n > 0 ? n : null;
}

export function CategoryDetailScreen(): React.ReactElement {
  const { params } = useRoute<RouteProp<Params, 'Categoria'>>();
  const navigation = useNavigation<NativeStackNavigationProp<Params>>();
  const { width: larguraDaTela } = useWindowDimensions();
  const largura = Math.min(larguraDaTela, layout.maxWidth) - spacing.md * 4;

  const [mes, setMes] = useState(params.mes);
  const [meta, setMeta] = useState('');
  const [editandoMeta, setEditandoMeta] = useState(false);
  const [renomeando, setRenomeando] = useState(false);
  const [nomeNovo, setNomeNovo] = useState(params.nome);
  const [novaFilha, setNovaFilha] = useState('');
  const [criandoFilha, setCriandoFilha] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [recado, setRecado] = useState<string | null>(null);

  const { data, isLoading } = useCategoryAnalysis(params.id, mes);
  const salvarMeta = useSaveBudgetCap();
  const apagarMeta = useDeleteBudgetCap();
  const renomear = useUpdateCategory();
  const apagarCategoria = useDeleteCategory();
  const criarFilha = useCreateCategory();

  useEffect(() => {
    navigation.setOptions({ title: data?.category.name ?? params.nome });
  }, [navigation, data?.category.name, params.nome]);

  async function gravarMeta(): Promise<void> {
    const valor = paraNumero(meta);
    if (valor === null) {
      setErro('Diga quanto pode gastar por mês nesta categoria.');
      return;
    }
    setErro(null);
    try {
      await salvarMeta.mutateAsync({ category_id: params.id, amount: valor });
      setEditandoMeta(false);
      setMeta('');
      setRecado(`Meta de ${money(valor)} por mês guardada.`);
    } catch (err) {
      setErro(err instanceof Error ? err.message : 'Nao consegui guardar a meta.');
    }
  }

  async function removerMeta(): Promise<void> {
    if (!data?.cap) return;
    setErro(null);
    try {
      await apagarMeta.mutateAsync(data.cap.id);
      setRecado('Meta apagada. O gasto continua sendo contado.');
    } catch (err) {
      setErro(err instanceof Error ? err.message : 'Nao consegui apagar a meta.');
    }
  }

  async function gravarNome(): Promise<void> {
    if (!nomeNovo.trim()) return;
    setErro(null);
    try {
      await renomear.mutateAsync({ id: params.id, name: nomeNovo.trim() });
      setRenomeando(false);
    } catch (err) {
      setErro(err instanceof Error ? err.message : 'Nao consegui renomear.');
    }
  }

  async function excluir(): Promise<void> {
    setErro(null);
    try {
      const fim = await apagarCategoria.mutateAsync(params.id);
      // volta para a lista: a tela que mostrava esta categoria não existe mais
      navigation.goBack();
      if (fim.aviso) setRecado(fim.aviso);
    } catch (err) {
      setErro(err instanceof Error ? err.message : 'Nao consegui excluir.');
    }
  }

  async function gravarFilha(): Promise<void> {
    if (!novaFilha.trim()) return;
    setErro(null);
    try {
      await criarFilha.mutateAsync({ name: novaFilha.trim(), parent_id: params.id });
      setNovaFilha('');
      setCriandoFilha(false);
    } catch (err) {
      setErro(err instanceof Error ? err.message : 'Nao consegui criar a subcategoria.');
    }
  }

  if (isLoading || !data) {
    return (
      <View style={styles.centro}>
        <ActivityIndicator color={colors.red} />
      </View>
    );
  }

  const gasto = Number(data.spent);
  const valorMeta = data.cap ? Number(data.cap.amount) : 0;
  const usado = valorMeta > 0 ? gasto / valorMeta : 0;
  const anoPassado = Number(data.same_month_last_year);
  const media = Number(data.monthly_average);

  return (
    <Screen>
      <MonthPicker value={mes} onChange={setMes} />
      {recado ? <Mensagem tom="ok">{recado}</Mensagem> : null}
      {erro ? <Mensagem tom="erro">{erro}</Mensagem> : null}

      {/* ----------------------------------------------- o mês contra a meta */}
      <Card>
        <Text style={styles.gastoRotulo}>Gasto no mês</Text>
        <Text style={styles.gastoValor}>{money(gasto)}</Text>
        <Text style={styles.gastoHint}>
          {data.transactions === 1 ? '1 lançamento' : `${data.transactions} lançamentos`}
        </Text>

        {valorMeta > 0 ? (
          <View style={styles.metaBloco}>
            <ProgressBar ratio={usado} severity={severidade(usado)} />
            <Text
              style={[
                styles.metaTexto,
                usado >= 1 && { color: colors.red },
              ]}
            >
              {usado >= 1
                ? `${money(gasto - valorMeta)} acima da meta de ${money(valorMeta)}`
                : `${money(valorMeta - gasto)} ainda cabem na meta de ${money(valorMeta)}`}
            </Text>
          </View>
        ) : null}
      </Card>

      {/* ---------------------------------------------------- comparações */}
      <View style={styles.tiles}>
        <StatTile
          label="Mês passado"
          value={money(data.previous_month)}
        />
        <StatTile
          label={`Mesmo mês de ${Number(mes.slice(0, 4)) - 1}`}
          value={money(anoPassado)}
          hint={
            anoPassado === 0
              ? 'não havia histórico'
              : (variacao(data.vs_last_year_pct) ?? undefined)
          }
          tone={Number(data.vs_last_year_pct ?? 0) > 0.2 ? 'alert' : 'neutral'}
        />
      </View>
      <View style={styles.tiles}>
        <StatTile
          label="Últimos 12 meses"
          value={money(data.last_12_months)}
          hint={`média de ${money(media)} por mês`}
        />
        <StatTile
          label="Contra a média"
          value={variacao(data.vs_average_pct) ?? '—'}
          hint={media === 0 ? 'sem histórico' : 'deste mês contra a média'}
          tone={Number(data.vs_average_pct ?? 0) > 0.2 ? 'alert' : 'neutral'}
        />
      </View>

      <Card>
        <SectionTitle>Treze meses</SectionTitle>
        <BarSeries points={data.series} width={largura} media={media} />
      </Card>

      {/* ------------------------------------------------------- a meta */}
      <SectionTitle>Meta mensal</SectionTitle>
      <Card>
        {editandoMeta ? (
          <>
            <Field
              label="Quanto por mês"
              value={meta}
              onChangeText={setMeta}
              placeholder={valorMeta > 0 ? String(valorMeta).replace('.', ',') : '0,00'}
              keyboardType="decimal-pad"
              autoFocus
              ajuda="A meta soma esta categoria e tudo o que está dentro dela."
            />
            <Botao onPress={gravarMeta} disabled={salvarMeta.isPending}>
              {salvarMeta.isPending ? 'Guardando…' : 'Guardar meta'}
            </Botao>
            <Botao tom="secundario" onPress={() => setEditandoMeta(false)}>
              Cancelar
            </Botao>
          </>
        ) : valorMeta > 0 ? (
          <>
            <Text style={styles.metaAtual}>{money(valorMeta)} por mês</Text>
            <Botao
              tom="secundario"
              onPress={() => {
                setMeta(String(valorMeta).replace('.', ','));
                setEditandoMeta(true);
              }}
            >
              Mudar a meta
            </Botao>
            <Botao tom="secundario" onPress={removerMeta} disabled={apagarMeta.isPending}>
              {apagarMeta.isPending ? 'Apagando…' : 'Apagar a meta'}
            </Botao>
          </>
        ) : (
          <>
            <Text style={styles.semMeta}>
              Sem meta. Com uma, a barra acima avisa quando o mês passa do combinado.
            </Text>
            <Botao onPress={() => setEditandoMeta(true)}>Definir meta mensal</Botao>
          </>
        )}
      </Card>

      {/* ----------------------------------------------- subcategorias */}
      <SectionTitle>
        {data.children.length > 0 ? 'Subcategorias' : 'Sem subcategorias'}
      </SectionTitle>
      <Card>
        {data.children.map((filha) => {
          const gastoFilha = Number(filha.spent);
          const metaFilha = filha.cap ? Number(filha.cap.amount) : 0;
          return (
            <Pressable
              key={filha.id}
              accessibilityRole="button"
              onPress={() =>
                navigation.push('Categoria', { id: filha.id, nome: filha.name, mes })
              }
              style={styles.filha}
            >
              <View style={styles.filhaMain}>
                <Text style={styles.filhaNome}>{filha.name}</Text>
                <Text style={styles.filhaHint}>
                  {metaFilha > 0 ? `meta de ${money(metaFilha)}` : 'sem meta'}
                  {Number(filha.monthly_average) > 0
                    ? ` · média de ${money(filha.monthly_average)}`
                    : ''}
                </Text>
              </View>
              <View style={styles.filhaDireita}>
                <Text style={styles.filhaValor}>{money(gastoFilha)}</Text>
                <Text style={styles.filhaSeta}>›</Text>
              </View>
            </Pressable>
          );
        })}

        {criandoFilha ? (
          <>
            <Field
              label="Nome da subcategoria"
              value={novaFilha}
              onChangeText={setNovaFilha}
              placeholder="Ex.: Pedágio e tag"
              autoFocus
              autoCapitalize="sentences"
            />
            <Botao onPress={gravarFilha} disabled={!novaFilha.trim() || criarFilha.isPending}>
              {criarFilha.isPending ? 'Criando…' : 'Criar subcategoria'}
            </Botao>
            <Botao tom="secundario" onPress={() => setCriandoFilha(false)}>
              Cancelar
            </Botao>
          </>
        ) : (
          <Botao tom="secundario" onPress={() => setCriandoFilha(true)}>
            ＋ Nova subcategoria
          </Botao>
        )}
      </Card>

      {/* ------------------------------------------------- nome e exclusão */}
      <SectionTitle>Esta categoria</SectionTitle>
      <Card>
        {renomeando ? (
          <>
            <Field label="Nome" value={nomeNovo} onChangeText={setNomeNovo} autoFocus />
            <Botao onPress={gravarNome} disabled={renomear.isPending}>
              {renomear.isPending ? 'Salvando…' : 'Salvar nome'}
            </Botao>
            <Botao tom="secundario" onPress={() => setRenomeando(false)}>
              Cancelar
            </Botao>
          </>
        ) : (
          <Botao
            tom="secundario"
            onPress={() => {
              setNomeNovo(data.category.name);
              setRenomeando(true);
            }}
          >
            Renomear
          </Botao>
        )}

        <Text style={styles.avisoExcluir}>
          {data.transactions > 0 || Number(data.last_12_months) > 0
            ? 'Esta categoria já tem lançamentos. Excluir tira ela da tela, e os gastos antigos continuam contando onde sempre contaram.'
            : 'Nenhum lançamento usa esta categoria — excluir apaga de vez.'}
        </Text>
        <Botao tom="secundario" onPress={excluir} disabled={apagarCategoria.isPending}>
          {apagarCategoria.isPending ? 'Excluindo…' : 'Excluir categoria'}
        </Botao>
      </Card>
    </Screen>
  );
}

const styles = StyleSheet.create({
  centro: {
    flex: 1,
    backgroundColor: colors.background,
    alignItems: 'center',
    justifyContent: 'center',
  },
  gastoRotulo: { ...typography.caption, color: colors.textFaint },
  gastoValor: { ...typography.display, color: colors.text, marginTop: 2 },
  gastoHint: { ...typography.caption, color: colors.textMuted },
  metaBloco: { marginTop: spacing.md },
  metaTexto: { ...typography.caption, color: colors.textMuted, marginTop: spacing.sm },
  tiles: { flexDirection: 'row', gap: spacing.sm, marginBottom: spacing.sm },
  metaAtual: { ...typography.title, color: colors.text, marginBottom: spacing.sm },
  semMeta: { ...typography.caption, color: colors.textMuted },
  filha: {
    flexDirection: 'row',
    alignItems: 'center',
    minHeight: 52,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  filhaMain: { flex: 1 },
  filhaNome: { ...typography.body, color: colors.text },
  filhaHint: { ...typography.caption, color: colors.textFaint, marginTop: 2 },
  filhaDireita: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  filhaValor: { ...typography.body, color: colors.text },
  filhaSeta: { fontSize: 24, color: colors.textFaint },
  avisoExcluir: {
    ...typography.caption,
    color: colors.textMuted,
    marginTop: spacing.lg,
  },
});
