/**
 * Cartão de crédito: quanto foi gasto, e a vigilância contra contar duas vezes.
 *
 * O cartão é o único lugar onde o mesmo dinheiro aparece em dois extratos. A
 * compra entra no extrato do cartão no dia em que acontece; semanas depois, o
 * pagamento da fatura entra no extrato da conta corrente. Importar os dois é o
 * caminho normal — e, sem cuidado, cada compra seria contada duas vezes.
 *
 * A regra: a despesa é a COMPRA, no dia dela. O pagamento da fatura é bolso
 * trocando de lugar. Por isso o número grande aqui é a soma das compras no
 * cartão, e não o valor da fatura: os dois quase nunca são iguais, porque a
 * fatura de novembro cobra compras de outubro.
 *
 * Quando uma linha de fatura escapa da classificação — o banco escreveu de um
 * jeito que nenhuma regra reconheceu — ela entra como gasto e ninguém avisa. É
 * esse silêncio que a lista do fim da tela quebra.
 */

import React, { useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';

import { useCardSummary, useCategories, useRecategorize } from '@/api/queries';
import { MonthPicker, mesAtualISO } from '@/components/MonthPicker';
import { Botao, Card, Mensagem, Screen, SectionTitle } from '@/components/ui';
import { colors, spacing, typography } from '@/theme';
import { dayLabel, money } from '@/theme/format';

export function CardsScreen(): React.ReactElement {
  const [mes, setMes] = useState(mesAtualISO);
  const { data, isLoading } = useCardSummary(mes);
  const { data: categorias } = useCategories();
  const recategorizar = useRecategorize();
  const [erro, setErro] = useState<string | null>(null);

  // Os dois destinos da linha de pagamento de fatura. Buscados pelo caminho, e
  // nao pelo nome: nome muda, caminho e identidade.
  const destinos = React.useMemo(() => {
    const achar = (caminho: string): string | null => {
      const procurar = (nos: typeof categorias): string | null => {
        for (const no of nos ?? []) {
          if (no.path === caminho) return no.id;
          const dentro = procurar(no.children);
          if (dentro) return dentro;
        }
        return null;
      };
      return procurar(categorias);
    };
    return {
      semDetalhe: achar('despesas.cartao_sem_detalhe'),
      pagamento: achar('transferencias.pagamento_cartao'),
    };
  }, [categorias]);

  async function trocarDestino(id: string, contarComoGasto: boolean): Promise<void> {
    const destino = contarComoGasto ? destinos.semDetalhe : destinos.pagamento;
    if (!destino) {
      setErro('Nao achei a categoria. Atualize o sistema e tente de novo.');
      return;
    }
    setErro(null);
    try {
      // learn_rule desligado: isto e uma decisao sobre ESTE mes, e aprender com
      // ela faria toda fatura futura entrar como gasto sem ninguem pedir.
      await recategorizar.mutateAsync({ id, category_id: destino, learn_rule: false });
    } catch (err) {
      setErro(err instanceof Error ? err.message : 'Nao consegui mudar.');
    }
  }

  if (isLoading || !data) {
    return (
      <Screen>
        <ActivityIndicator color={colors.red} />
      </Screen>
    );
  }

  const total = Number(data.total_spent);

  return (
    <Screen>
      <MonthPicker value={mes} onChange={setMes} />

      <Card>
        <Text style={styles.rotulo}>Comprado no cartão neste mês</Text>
        <Text style={styles.valor}>{money(total)}</Text>
        <Text style={styles.hint}>
          É a soma das compras feitas no mês, e não o valor da fatura — a fatura
          que chega agora cobra compras do mês passado.
        </Text>
      </Card>

      {data.cards.length === 0 ? (
        <Card>
          <Text style={styles.hint}>
            Nenhum cartão cadastrado. Em Mais › Contas e cartões, cadastre um com o
            tipo “Cartão de crédito”.
          </Text>
        </Card>
      ) : (
        <>
          <SectionTitle>Por cartão</SectionTitle>
          <Card>
            {data.cards.map((cartao) => (
              <View key={cartao.id} style={styles.linha}>
                <View style={styles.linhaMain}>
                  <Text style={styles.nome}>{cartao.name}</Text>
                  <Text style={styles.detalhe}>
                    {cartao.transactions === 1
                      ? '1 compra'
                      : `${cartao.transactions} compras`}
                    {cartao.statement_due_day
                      ? ` · vence dia ${cartao.statement_due_day}`
                      : ''}
                  </Text>
                </View>
                <Text style={styles.linhaValor}>{money(cartao.spent)}</Text>
              </View>
            ))}
          </Card>

          <SectionTitle>Pontos</SectionTitle>
          <Card>
            <Text style={styles.hint}>
              Os pontos costumam ser por real gasto, então a base de cálculo é o
              número de cima: {money(total)} neste mês. O fator de cada programa e o
              saldo acumulado ficam em Investimentos.
            </Text>
          </Card>
        </>
      )}

      <SectionTitle>Fatura paga</SectionTitle>
      <Card>
        <Text style={styles.faturaValor}>{money(data.bill_paid)}</Text>
        <Text style={styles.hint}>
          Saiu da conta corrente neste mês para pagar fatura. Não entra no gasto do
          mês: a despesa foi a compra, no dia dela. Este número está aqui só para
          você poder conferir contra o extrato.
        </Text>
        {Number(data.purchases_known) > 0 ? (
          <Text style={styles.hint}>
            Compras de cartão que o sistema conhece no período que essa fatura cobre:{' '}
            {money(data.purchases_known)}.
          </Text>
        ) : null}
      </Card>

      {erro ? <Mensagem tom="erro">{erro}</Mensagem> : null}

      {data.aviso_sem_detalhe ? (
        <>
          <SectionTitle>Falta o detalhe do cartão</SectionTitle>
          <Mensagem tom="erro">{data.aviso_sem_detalhe}</Mensagem>
        </>
      ) : null}

      {Number(data.sem_detalhe) > 0 ? (
        <Card>
          <Text style={styles.rotulo}>Contado como gasto sem detalhe</Text>
          <Text style={styles.faturaValor}>{money(data.sem_detalhe)}</Text>
          <Text style={styles.hint}>
            Você escolheu contar a fatura como um gasto só, sem as compras. Se um dia
            importar essa fatura, desfaça aqui — senão o mês conta o cartão duas vezes.
          </Text>
        </Card>
      ) : null}

      {data.bill_payments.length > 0 ? (
        <Card>
          <Text style={styles.rotulo}>Pagamentos de fatura deste mês</Text>
          {data.bill_payments.map((pagamento) => (
            <View key={pagamento.id} style={styles.suspeita}>
              <View style={styles.linhaMain}>
                <Text style={styles.nome} numberOfLines={1}>
                  {money(pagamento.amount)}
                </Text>
                <Text style={styles.detalhe}>
                  {dayLabel(pagamento.booked_on)} · {pagamento.description}
                </Text>
                <Text style={pagamento.counted_as_expense ? styles.contado : styles.detalhe}>
                  {pagamento.counted_as_expense
                    ? 'contando como gasto (sem detalhe)'
                    : 'não conta como gasto — a despesa é a compra'}
                </Text>
              </View>
              <Botao
                tom="secundario"
                disabled={recategorizar.isPending}
                onPress={() => void trocarDestino(pagamento.id, !pagamento.counted_as_expense)}
              >
                {pagamento.counted_as_expense ? 'Voltar a não contar' : 'Contar como gasto'}
              </Botao>
            </View>
          ))}
        </Card>
      ) : null}

      {data.possible_duplicates.length > 0 ? (
        <>
          <SectionTitle>Pode estar contado em dobro</SectionTitle>
          <Mensagem tom="erro">{data.aviso ?? ''}</Mensagem>
          <Card>
            {data.possible_duplicates.map((linha) => (
              <View key={linha.id} style={styles.suspeita}>
                <View style={styles.linhaMain}>
                  <Text style={styles.nome} numberOfLines={1}>
                    {linha.description}
                  </Text>
                  <Text style={styles.detalhe}>
                    {dayLabel(linha.booked_on)} · {linha.account_name} ·{' '}
                    {linha.category_name ?? 'sem categoria'}
                  </Text>
                </View>
                <Text style={styles.suspeitaValor}>{money(linha.amount)}</Text>
              </View>
            ))}
            <Text style={styles.comoResolver}>
              Para resolver: na aba Gastos, abra o lançamento e mude a categoria
              para “Pagamento de fatura”. Ele continua saindo da conta, mas para de
              ser contado como gasto.
            </Text>
          </Card>
        </>
      ) : (
        <Card>
          <Text style={styles.semSuspeita}>
            ✓ Nenhuma linha de fatura está sendo contada como gasto neste mês.
          </Text>
        </Card>
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  rotulo: { ...typography.caption, color: colors.textFaint },
  valor: { ...typography.display, color: colors.text, marginTop: 2 },
  contado: { ...typography.caption, color: colors.red, marginTop: 2 },
  faturaValor: { ...typography.title, color: colors.textMuted },
  hint: { ...typography.caption, color: colors.textMuted, marginTop: spacing.sm },
  linha: {
    flexDirection: 'row',
    alignItems: 'center',
    minHeight: 50,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  linhaMain: { flex: 1, paddingRight: spacing.sm },
  nome: { ...typography.body, color: colors.text },
  detalhe: { ...typography.caption, color: colors.textFaint, marginTop: 2 },
  linhaValor: { ...typography.body, color: colors.text },
  suspeita: {
    flexDirection: 'row',
    alignItems: 'center',
    minHeight: 50,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  suspeitaValor: { ...typography.body, color: colors.red },
  comoResolver: { ...typography.caption, color: colors.textMuted, marginTop: spacing.md },
  semSuspeita: { ...typography.caption, color: colors.textMuted },
});
