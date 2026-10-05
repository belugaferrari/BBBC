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

import React, { useState } from 'react';
import {
  ActivityIndicator,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  useWindowDimensions,
  View,
} from 'react-native';

import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';

import { useDashboard, useEvolucao } from '@/api/queries';
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
import { money, monthLabel, percent } from '@/theme/format';

export function DashboardScreen(): React.ReactElement {
  const navigation = useNavigation<
    NativeStackNavigationProp<{ Cartoes: undefined }>
  >();
  const [scope, setScope] = useState<Scope>('familia');
  const [month, setMonth] = useState(mesAtualISO);
  const mesAtual = month === mesAtualISO();
  const { width: larguraDaTela } = useWindowDimensions();
  // o grafico nao pode ser mais largo que a coluna de conteudo
  const width = Math.min(larguraDaTela, layout.maxWidth);
  const { data, isLoading, refetch, isRefetching, error } = useDashboard(month, scope);
  const { data: evolucao } = useEvolucao(month, scope);

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

      <Botao tom="secundario" onPress={() => navigation.navigate('Cartoes')}>
        Ver o cartão de crédito do mês
      </Botao>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
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
