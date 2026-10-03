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

import { useCardSummary } from '@/api/queries';
import { MonthPicker, mesAtualISO } from '@/components/MonthPicker';
import { Card, Mensagem, Screen, SectionTitle } from '@/components/ui';
import { colors, spacing, typography } from '@/theme';
import { dayLabel, money } from '@/theme/format';

export function CardsScreen(): React.ReactElement {
  const [mes, setMes] = useState(mesAtualISO);
  const { data, isLoading } = useCardSummary(mes);

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
      </Card>

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
