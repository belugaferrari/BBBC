/**
 * Visão geral do mês: como o mês está correndo, fluxo de caixa, saldos, metas
 * e alertas.
 *
 * O mês é escolhido, e não fixo no atual. Isso traz uma armadilha que a tela
 * precisa resolver na cara: o que vem do servidor NÃO é todo do mês escolhido.
 *
 *   * o fluxo (entrou, gastou, sobrou), o gráfico e as metas são do mês - olhar
 *     agosto mostra agosto;
 *   * os saldos (disponível, patrimônio, investido, fatura) são de HOJE, porque
 *     saem do saldo atual de cada conta, não de uma foto do passado.
 *
 * Mostrar o saldo de hoje embaixo do título "agosto" seria um número errado em
 * silêncio - o pior tipo. Então, em mês que não é o atual, esses quatro dizem
 * "hoje" no próprio rótulo. Os alertas, que também são do agora, saem da tela.
 */

import React, { useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  useWindowDimensions,
  View,
} from 'react-native';

import { useNavigation, useRoute } from '@react-navigation/native';
import type { RouteProp } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';

import {
  useCategoryOverview,
  useDashboard,
  useEvolucao,
  useTransactions,
} from '@/api/queries';
import { AvisoDeConexao } from '@/components/AvisoDeConexao';
import type { Scope } from '@/api/types';
import { MonthPicker, mesAtualISO } from '@/components/MonthPicker';
import {
  Botao,
  BudgetRow,
  Card,
  MoneyValue,
  ScopeToggle,
  SectionTitle,
  StatTile,
} from '@/components/ui';
import { EvolucaoChart } from '@/components/EvolucaoChart';
import { colors, layout, severityColor, spacing, typography } from '@/theme';
import { dayLabel, money, monthLabel, percent } from '@/theme/format';

/** O primeiro e o último dia do mês, que é o recorte das duas listas. */
function janelaDoMes(mesISO: string): { start: string; end: string } {
  const [ano, mes] = mesISO.slice(0, 7).split('-').map(Number);
  const ultimo = new Date(ano, mes, 0).getDate();
  return {
    start: `${mesISO.slice(0, 7)}-01`,
    end: `${mesISO.slice(0, 7)}-${String(ultimo).padStart(2, '0')}`,
  };
}

export function DashboardScreen(): React.ReactElement {
  const navigation = useNavigation<
    NativeStackNavigationProp<{
      Cartoes: undefined;
      Gastos: undefined;
      Categoria: { id: string; nome: string; mes: string };
    }>
  >();
  const [scope, setScope] = useState<Scope>('familia');
  const [month, setMonth] = useState(mesAtualISO);

  // O Calendário manda para cá com um mês debaixo do braço: ele responde "em
  // que mês doeu", e a pergunta seguinte - "doeu com o quê" - se responde
  // aqui, onde já estão o gasto por categoria e a lista inteira do mês.
  //
  // O mês continua sendo estado desta tela, e não do parâmetro: depois de
  // chegar, a setinha do seletor tem de funcionar normalmente. O carimbo é o
  // que faz o segundo toque no MESMO mês valer - sem ele os parâmetros seriam
  // iguais aos de antes e este efeito não rodaria de novo.
  const rota = useRoute<RouteProp<{ Dashboard?: { mes?: string; carimbo?: number } }, 'Dashboard'>>();
  const mesPedido = rota.params?.mes;
  const carimbo = rota.params?.carimbo;
  useEffect(() => {
    if (mesPedido) setMonth(mesPedido);
  }, [mesPedido, carimbo]);

  const mesAtual = month === mesAtualISO();
  const { width: larguraDaTela } = useWindowDimensions();
  // o grafico nao pode ser mais largo que a coluna de conteudo
  const width = Math.min(larguraDaTela, layout.maxWidth);
  const { data, isLoading, refetch, isRefetching, error } = useDashboard(month, scope);
  const { data: evolucao } = useEvolucao(month, scope);
  // O mês inteiro, para as duas listas de baixo: para onde o dinheiro foi, e
  // cada lançamento. Ele pediu as duas coisas na tela do mês - "um resumo de
  // gastos por categoria dentro daquele mês e abaixo todos os gastos daquele
  // mês listados para conferência" - e não havia nem uma nem outra aqui.
  const janela = useMemo(() => janelaDoMes(month), [month]);
  const { data: porCategoria } = useCategoryOverview(month);
  const { data: lancamentos } = useTransactions({ ...janela, scope });

  const baldes = useMemo(
    () =>
      (porCategoria?.categories ?? [])
        .filter((c) => c.depth === 1 && Number(c.spent) > 0)
        .sort((a, b) => Number(b.spent) - Number(a.spent)),
    [porCategoria],
  );
  const doMes = useMemo(
    () =>
      [...(lancamentos ?? [])].sort((a, b) =>
        b.booked_on.localeCompare(a.booked_on),
      ),
    [lancamentos],
  );

  // O seletor de mes fica FORA do if de carregamento, e isso nao e detalhe: com
  // ele dentro, um mes que ainda esta carregando - ou que nao carregou - deixava
  // a tela sem nenhuma forma de sair dali. Quem abrisse um mes vazio ficava
  // presos nele, sem botao nenhum. O seletor e o que da para fazer sempre.
  const cabecalho = (
    <>
      <MonthPicker value={month} onChange={setMonth} />
      <AvisoDeConexao />
    </>
  );

  if (isLoading) {
    return (
      <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
        {cabecalho}
        <View style={styles.carregando}>
          <ActivityIndicator color={colors.red} />
        </View>
      </ScrollView>
    );
  }

  // `error` sozinho nao manda mais na tela: com a copia local do aparelho, a
  // consulta pode ter falhado AGORA e ainda haver numeros de antes para mostrar.
  // Trocar esses numeros por uma tela de erro seria jogar fora a unica coisa util
  // que o aplicativo tem offline - quem avisa que eles sao de antes, e de quando,
  // e a faixa no cabecalho.
  if (!data) {
    return (
      <ScrollView
        style={styles.screen}
        contentContainerStyle={styles.content}
        refreshControl={
          <RefreshControl refreshing={isRefetching} onRefresh={refetch} tintColor={colors.red} />
        }
      >
        {cabecalho}
        <Card>
          <Text style={styles.error}>
            {error
              ? `Nao consegui carregar ${monthLabel(month)}, e ainda nao tenho copia deste mes no aparelho. Puxe a tela para baixo para tentar de novo, ou escolha outro mes acima.`
              : `Nao consegui carregar ${monthLabel(month)}. Puxe a tela para baixo para tentar de novo, ou escolha outro mes acima.`}
          </Text>
        </Card>
      </ScrollView>
    );
  }

  const { cashflow, balances, budget_caps: caps, alerts, pendentes } = data;
  const net = Number(cashflow.net);
  // O que entrou e NÃO é renda fica em linha separada - somado à renda, inflaria
  // o mês e a taxa de poupança, e é o tipo de número que depois ninguém
  // desconfia. São duas coisas diferentes, e por isso dois números: doação
  // recebida, e o resto (transferência entre contas próprias, devolução).
  const doacoes = Number(cashflow.doacoes);
  const reembolsos = Number(cashflow.reembolsos ?? 0);
  const outras = Number(cashflow.outras_entradas ?? 0);
  const foraDaRenda = doacoes + reembolsos + outras;
  const cobriu = Number(cashflow.doacoes_aplicadas);
  // o que voltou de reembolso sai do consumo pelo mesmo motivo que a doação: o
  // dinheiro saiu da conta, mas não ficou com a casa
  const voltou = Number(cashflow.reembolsos_aplicados ?? 0);
  const descontado = cobriu + voltou;
  const avisos: string[] = [];
  if (doacoes > 0) avisos.push(`+ ${money(doacoes)} de doação`);
  if (reembolsos > 0) avisos.push(`+ ${money(reembolsos)} de reembolso`);
  if (outras > 0) avisos.push(`+ ${money(outras)} que não é renda`);
  const comoFoiDescontado = [
    cobriu > 0 ? `${money(cobriu)} foram pagos com doação` : null,
    voltou > 0 ? `${money(voltou)} voltaram em reembolso` : null,
  ].filter(Boolean) as string[];

  return (
    <ScrollView
      style={styles.screen}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl refreshing={isRefetching} onRefresh={refetch} tintColor={colors.red} />
      }
    >
      {cabecalho}

      <View style={styles.header}>
        <View style={styles.headerMain}>
          <MoneyValue value={cashflow.net} size="display" direction={net >= 0 ? 'in' : 'out'} />
          <Text style={styles.headerHint}>
            {net >= 0 ? 'sobrou no mês' : 'faltou no mês'} · poupança de{' '}
            {percent(cashflow.savings_rate)}
          </Text>
        </View>
        <ScopeToggle value={scope} onChange={setScope} />
      </View>

      <View style={styles.tiles}>
        <StatTile
          label={foraDaRenda > 0 ? 'Renda' : 'Entrou'}
          value={money(foraDaRenda > 0 ? cashflow.renda : cashflow.inflow)}
          hint={avisos.length > 0 ? avisos.join(' · ') : undefined}
        />
        <StatTile
          label="Gastou"
          value={money(descontado > 0 ? cashflow.consumo_proprio : cashflow.consumo)}
          tone="alert"
          hint={
            comoFoiDescontado.length > 0
              ? comoFoiDescontado.join(' · ')
              : Number(cashflow.patrimonio) > 0
                ? `+ ${money(cashflow.patrimonio)} viraram patrimônio`
                : undefined
          }
        />
      </View>
      {doacoes > 0 ? (
        <Text style={styles.avisoDoSaldo}>
          A doação entrou na conta, mas não conta como renda — e o gasto que ela cobriu saiu do
          que a casa gastou. Em Mais › Doações recebidas está a soma do ano, por quem deu.
        </Text>
      ) : null}
      {Number(cashflow.gasto_no_cartao ?? 0) > 0 ? (
        <Text style={styles.avisoDoSaldo}>
          {`${money(cashflow.gasto_no_cartao)} deste mês são a fatura do cartão: compras feitas antes, que só agora saíram da conta. O gasto conta no mês em que o dinheiro sai — é o que faz este número bater com o seu extrato.`}
        </Text>
      ) : null}
      {reembolsos > 0 ? (
        <Text style={styles.avisoDoSaldo}>
          O reembolso é dinheiro seu voltando, então não conta como renda — e a parte dos amigos
          sai do que a casa gastou. O gasto continua inteiro na categoria dele, com o quanto
          voltou escrito ao lado.
        </Text>
      ) : null}
      {Number(cashflow.credito_no_cartao ?? 0) > 0 ? (
        <Text style={styles.avisoDoSaldo}>
          {`${money(cashflow.credito_no_cartao)} foram creditados no cartão (o pagamento da própria fatura, que vem dentro do extrato dele). Não é dinheiro entrando na família: o saldo de um cartão é dívida.`}
        </Text>
      ) : null}
      <View style={styles.tiles}>
        <StatTile
          label={mesAtual ? 'Disponível' : 'Disponível hoje'}
          value={money(balances.liquid)}
          hint={`Fatura aberta ${money(balances.credit_card_debt)}`}
        />
        <StatTile
          label={mesAtual ? 'Patrimônio' : 'Patrimônio hoje'}
          value={money(balances.net_worth)}
          hint={`Investido ${money(balances.invested)}`}
        />
      </View>
      {Number(balances.na_empresa ?? 0) !== 0 ? (
        <Text style={styles.avisoDoSaldo}>
          {`Fora destes dois: ${money(balances.na_empresa)} na conta da empresa. Esse dinheiro tem sócio e tem imposto para sair de lá — somá-lo ao patrimônio inflaria justamente o número que serve para decidir se dá para comprar alguma coisa. O que a empresa paga de conta sua continua contando como gasto da casa, linha a linha, na conferência do extrato.`}
        </Text>
      ) : null}
      {!mesAtual ? (
        <Text style={styles.avisoDoSaldo}>
          Estes dois são o saldo de hoje, e não o de {monthLabel(month)} — o saldo
          sai da conta no estado em que ela está agora, não de uma foto do passado.
        </Text>
      ) : null}

      {pendentes && pendentes.quantos > 0 ? (
        <Card>
          <Text style={styles.pendentesTitulo}>
            {pendentes.quantos === 1
              ? '1 lançamento esperando categoria'
              : `${pendentes.quantos} lançamentos esperando categoria`}
          </Text>
          <Text style={styles.pendentesValor}>{money(pendentes.total)}</Text>
          <Text style={styles.pendentesHint}>
            Estão em “A definir”: contam no gasto do mês, mas ainda não dizem em quê. Na aba
            Gastos, o filtro “só os pendentes” mostra só eles.
          </Text>
        </Card>
      ) : null}

      {mesAtual && alerts.length > 0 && (
        <Card>
          <SectionTitle>Alertas</SectionTitle>
          {alerts.map((alert) => (
            <View key={alert.id} style={styles.alert}>
              <View style={[styles.alertDot, { backgroundColor: severityColor[alert.severity] }]} />
              <View style={styles.alertBody}>
                <Text style={styles.alertTitle}>{alert.title}</Text>
                {alert.body ? <Text style={styles.alertText}>{alert.body}</Text> : null}
              </View>
            </View>
          ))}
        </Card>
      )}

      <Card>
        <SectionTitle>Como o mês está correndo</SectionTitle>
        {evolucao ? (
          <EvolucaoChart dados={evolucao} width={width - spacing.md * 4} />
        ) : (
          <ActivityIndicator color={colors.red} />
        )}
      </Card>

      {caps.length > 0 ? (
        <Card>
          <SectionTitle>Metas do mes</SectionTitle>
          {caps.map((cap) => (
            <BudgetRow
              key={cap.category_id}
              name={cap.category_name}
              cap={cap.cap}
              spent={cap.spent}
              usedPct={cap.used_pct}
              severity={cap.severity}
              overflow={cap.projected_overflow}
            />
          ))}
        </Card>
      ) : (
        <Card>
          <SectionTitle>Metas do mes</SectionTitle>
          <Text style={styles.semMeta}>
            Nenhuma meta definida. Na aba Categorias, abra uma categoria e diga
            quanto pode gastar nela por mês.
          </Text>
        </Card>
      )}

      <SectionTitle>Para onde o dinheiro foi</SectionTitle>
      <Card>
        {baldes.length === 0 ? (
          <Text style={styles.semMeta}>
            Nenhum gasto em {monthLabel(month)} ainda.
          </Text>
        ) : (
          <>
            {baldes.map((balde) => (
              <Pressable
                key={balde.id}
                onPress={() =>
                  navigation.navigate('Categoria', {
                    id: balde.id,
                    nome: balde.name,
                    mes: month,
                  })
                }
                accessibilityRole="button"
                style={styles.linhaCategoria}
              >
                <Text style={styles.categoriaNome} numberOfLines={1}>
                  {balde.name}
                </Text>
                <Text style={styles.categoriaValor}>{money(balde.spent)}</Text>
              </Pressable>
            ))}
            <Text style={styles.pendentesHint}>
              Cada linha já inclui as subcategorias dela. Toque para abrir.
            </Text>
          </>
        )}
      </Card>

      <SectionTitle>
        {doMes.length === 1
          ? '1 lançamento no mês'
          : `${doMes.length} lançamentos no mês`}
      </SectionTitle>
      <Card>
        {doMes.length === 0 ? (
          <Text style={styles.semMeta}>
            Nada lançado em {monthLabel(month)}. Importe um extrato ou lance à mão.
          </Text>
        ) : (
          doMes.map((item) => (
            <View key={item.id} style={styles.linhaLancamento}>
              <View style={styles.lancamentoMain}>
                <Text style={styles.lancamentoNome} numberOfLines={1}>
                  {item.description}
                </Text>
                <Text style={styles.lancamentoData}>
                  {dayLabel(item.booked_on)}
                  {item.paid_on && item.paid_on.slice(0, 7) !== item.booked_on.slice(0, 7)
                    ? ' · veio na fatura'
                    : ''}
                  {item.installment_total
                    ? ` · parcela ${item.installment_no}/${item.installment_total}`
                    : ''}
                </Text>
              </View>
              <Text
                style={[
                  styles.lancamentoValor,
                  item.direction === 'ENTRADA' && styles.lancamentoEntrada,
                ]}
              >
                {item.direction === 'SAIDA' ? '−' : '+'}
                {money(item.amount)}
              </Text>
            </View>
          ))
        )}
      </Card>

      <Botao tom="secundario" onPress={() => navigation.navigate('Gastos')}>
        Conferir e corrigir os lançamentos
      </Botao>

      <Botao tom="secundario" onPress={() => navigation.navigate('Cartoes')}>
        Ver o cartão de crédito do mês
      </Botao>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  linhaCategoria: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.md,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  categoriaNome: { ...typography.body, color: colors.text, flex: 1 },
  categoriaValor: { ...typography.body, color: colors.text, fontWeight: '700' },
  linhaLancamento: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    paddingVertical: 9,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  lancamentoMain: { flex: 1 },
  lancamentoNome: { ...typography.caption, color: colors.text },
  lancamentoData: { ...typography.caption, color: colors.textFaint, marginTop: 1 },
  lancamentoValor: { ...typography.caption, color: colors.red, fontWeight: '700' },
  lancamentoEntrada: { color: colors.white },
  pendentesTitulo: { ...typography.body, color: colors.text, fontWeight: '700' },
  pendentesValor: { ...typography.title, color: colors.red, marginTop: 2 },
  pendentesHint: { ...typography.caption, color: colors.textMuted, marginTop: spacing.sm },
  screen: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.md, paddingBottom: spacing.xl, ...layout.coluna },
  center: {
    flex: 1,
    backgroundColor: colors.background,
    alignItems: 'center',
    justifyContent: 'center',
    padding: spacing.lg,
  },
  error: { ...typography.body, color: colors.textMuted },
  carregando: { paddingVertical: spacing.xl * 2, alignItems: 'center' },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: spacing.lg,
  },
  headerMain: { flex: 1 },
  headerHint: { ...typography.caption, color: colors.textMuted, marginTop: spacing.xs },
  tiles: { flexDirection: 'row', gap: spacing.sm, marginBottom: spacing.md },
  avisoDoSaldo: {
    ...typography.caption,
    color: colors.textFaint,
    marginTop: -spacing.sm,
    marginBottom: spacing.md,
  },
  alert: { flexDirection: 'row', gap: spacing.sm, marginBottom: spacing.sm },
  alertDot: { width: 6, height: 6, borderRadius: 3, marginTop: 6 },
  alertBody: { flex: 1 },
  alertTitle: { ...typography.body, color: colors.text },
  alertText: { ...typography.caption, color: colors.textMuted, marginTop: 2 },
  semMeta: { ...typography.caption, color: colors.textMuted },
});
