/**
 * O ano inteiro numa tela.
 *
 * "Esse sim será o grande resumo da coisa toda. Ano na parte superior. Uma tela
 * com 12 retângulos com as abreviações de cada mês mostrando ali quanto entrou e
 * o quanto saiu em cada mês. Abaixo o acumulado do ano (entradas; saídas;
 * Lucros/Prejuízos). Abaixo disso o resumo da atualidade: Patrimônio; Reservas;
 * Gastos mês anterior."
 *
 * Três alturas de leitura, da mais larga para a mais estreita — e é a largura
 * que define o que cada uma responde. O ano mês a mês mostra onde estão os
 * picos; o acumulado diz se o ano foi de lucro ou prejuízo; o retrato de hoje
 * diz quanto a família tem agora.
 *
 * Os doze meses aparecem sempre, inclusive os vazios e os que ainda não
 * aconteceram: um calendário com buraco obriga quem lê a contar nos dedos qual
 * mês é qual.
 */

import React, { useState } from 'react';
import { ActivityIndicator, Pressable, RefreshControl, StyleSheet, Text, View } from 'react-native';

import { useNavigation } from '@react-navigation/native';
import type { NavigationProp } from '@react-navigation/native';

import { useCalendario } from '@/api/queries';
import type { Scope } from '@/api/types';
import { Card, Screen, ScopeToggle, SectionTitle } from '@/components/ui';
import { colors, layout, radius, spacing, typography } from '@/theme';
import { money, monthLabel } from '@/theme/format';

const ABREVIACOES = [
  'JAN', 'FEV', 'MAR', 'ABR', 'MAI', 'JUN',
  'JUL', 'AGO', 'SET', 'OUT', 'NOV', 'DEZ',
];

/** Valor curto para caber no retângulo: "12,5 mil" em vez de "R$ 12.500,00". */
function curto(valor: string): string {
  const n = Math.abs(Number(valor));
  if (n === 0) return '—';
  if (n >= 1000) {
    const milhares = n / 1000;
    return `${milhares.toFixed(milhares >= 10 ? 0 : 1).replace('.', ',')} mil`;
  }
  return n.toFixed(0);
}

/**
 * Para onde o toque num mês leva, e com o quê.
 *
 * Separado da tela para poder ser conferido sem um celular: o que importa aqui
 * é que o mês vai inteiro ("2026-01-01", como o servidor mandou, e não um
 * número de mês remontado à mão) e que dois toques no mesmo mês saem com
 * carimbos diferentes — é o carimbo que faz o segundo toque valer.
 */
export function paraOResumo(mesISO: string, agora: number): ['Dashboard', { mes: string; carimbo: number }] {
  return ['Dashboard', { mes: mesISO, carimbo: agora }];
}

export function CalendarScreen(): React.ReactElement {
  // Daqui se vai para o Resumo do mes tocado. O calendario responde "em que mes
  // doeu"; a pergunta seguinte e sempre "doeu com o que" - e ela se responde no
  // Resumo, que ja tem o gasto por categoria e a lista inteira do mes. Sem o
  // toque, o caminho era voltar na aba Resumo e andar com a setinha ate la,
  // onze toques para ver janeiro em dezembro.
  //
  // O carimbo vai junto de proposito: sem ele, tocar DUAS vezes no mesmo mes
  // manda os mesmos parametros, a identidade nao muda, e o Resumo - que guarda
  // o mes escolhido - ignora o segundo toque. Quem voltou para o calendario,
  // mudou de mes no Resumo e tocou de novo no mesmo retangulo ficaria olhando
  // para o mes errado sem entender por que.
  const navigation = useNavigation<NavigationProp<{ Dashboard: { mes: string; carimbo: number } }>>();
  const [ano, setAno] = useState(() => new Date().getFullYear());
  const [scope, setScope] = useState<Scope>('familia');
  const { data, isLoading, refetch, isRefetching } = useCalendario(ano, scope);

  const mesAtual = new Date().getMonth();
  const anoCorrente = ano === new Date().getFullYear();

  return (
    <Screen
      refreshControl={
        <RefreshControl refreshing={isRefetching} onRefresh={refetch} tintColor={colors.red} />
      }
    >
      <View style={styles.cabecalho}>
        <Pressable
          onPress={() => setAno((a) => a - 1)}
          accessibilityRole="button"
          accessibilityLabel="Ano anterior"
          hitSlop={12}
        >
          <Text style={styles.seta}>‹</Text>
        </Pressable>
        <Text style={styles.ano}>{ano}</Text>
        <Pressable
          onPress={() => setAno((a) => a + 1)}
          accessibilityRole="button"
          accessibilityLabel="Próximo ano"
          hitSlop={12}
        >
          <Text style={styles.seta}>›</Text>
        </Pressable>
      </View>
      <View style={styles.escopo}>
        <ScopeToggle value={scope} onChange={setScope} />
      </View>

      {isLoading || !data ? (
        <ActivityIndicator color={colors.red} style={{ marginTop: spacing.xl }} />
      ) : (
        <>
          <View style={styles.grade}>
            {data.months.map((mes, indice) => {
              const entrou = Number(mes.entrou);
              const saiu = Number(mes.saiu);
              const vazio = entrou === 0 && saiu === 0;
              const futuro = anoCorrente && indice > mesAtual;
              return (
                <Pressable
                  key={mes.month}
                  onPress={() => navigation.navigate(...paraOResumo(mes.month, Date.now()))}
                  accessibilityRole="button"
                  accessibilityLabel={`Ver o resumo de ${monthLabel(mes.month)}`}
                  // O mes vazio tambem abre: "nao tem nada aqui" e uma resposta,
                  // e um retangulo que nao responde ao toque parece defeito.
                  style={({ pressed }) => [
                    styles.mes,
                    anoCorrente && indice === mesAtual && styles.mesDeHoje,
                    (vazio || futuro) && styles.mesVazio,
                    pressed && styles.mesTocado,
                  ]}
                >
                  <Text style={styles.mesNome}>{ABREVIACOES[indice]}</Text>
                  <Text style={styles.mesEntrou} numberOfLines={1}>
                    {curto(mes.entrou)}
                  </Text>
                  <Text style={styles.mesSaiu} numberOfLines={1}>
                    {curto(mes.saiu)}
                  </Text>
                </Pressable>
              );
            })}
          </View>
          <Text style={styles.legenda}>
            Em cada mês: o que <Text style={styles.legendaEntrou}>entrou</Text> em cima e o que{' '}
            <Text style={styles.legendaSaiu}>saiu</Text> embaixo, em milhares. Pagamento de fatura
            e transferência entre contas próprias ficam de fora dos dois — senão o cartão
            contaria duas vezes.{'\n'}
            <Text style={styles.legendaToque}>Toque num mês para abrir o resumo dele.</Text>
          </Text>

          <SectionTitle>{`No ano de ${ano}`}</SectionTitle>
          <Card>
            <Linha rotulo="Entradas" valor={data.ano.entrou} />
            <Linha rotulo="Saídas" valor={data.ano.saiu} tom="saida" />
            <Linha
              rotulo={Number(data.ano.net) >= 0 ? 'Lucro' : 'Prejuízo'}
              valor={data.ano.net}
              tom={Number(data.ano.net) >= 0 ? 'lucro' : 'saida'}
              forte
            />
          </Card>

          <SectionTitle>Hoje</SectionTitle>
          <Card>
            <Linha rotulo="Patrimônio" valor={data.hoje.patrimonio} forte />
            <Linha rotulo="Reservas (dá para usar hoje)" valor={data.hoje.reservas} />
            <Linha rotulo="Investido" valor={data.hoje.investido} />
            {Number(data.hoje.na_empresa) !== 0 ? (
              <Linha rotulo="Na empresa (fora do patrimônio)" valor={data.hoje.na_empresa} />
            ) : null}
            {/* No lugar da "fatura em aberto": as faturas que ele importa já
                vêm pagas, e o saldo acumulado do cartão mostrado ali dizia uma
                dívida que não existe. O gasto médio responde a pergunta que ele
                de fato faz ao abrir esta tela — quanto custa um mês meu. */}
            {data.hoje.meses_na_media > 0 ? (
              <Linha
                rotulo={
                  data.hoje.meses_na_media >= 12
                    ? 'Gasto médio mensal'
                    : `Gasto médio mensal (${data.hoje.meses_na_media} ${
                        data.hoje.meses_na_media === 1 ? 'mês' : 'meses'
                      })`
                }
                valor={data.hoje.gasto_medio_mensal}
                tom="saida"
              />
            ) : null}
            <Linha
              rotulo={`Gastos de ${monthLabel(data.hoje.mes_anterior)}`}
              valor={data.hoje.gastos_mes_anterior}
              tom="saida"
            />
            <Text style={styles.nota}>
              O dinheiro que está na empresa aparece separado de propósito: ele tem sócio e tem
              imposto para sair de lá, então somá-lo ao patrimônio inflaria justamente o número
              que serve para decidir se dá para comprar alguma coisa.{'\n\n'}
              O mês anterior é o último fechado — o mês corrente ainda está acontecendo, e
              comparar com ele no dia 3 não diz nada. O gasto médio segue a mesma regra: são os
              últimos doze meses fechados, e só contam no divisor os que tiveram movimento —
              dividir por doze quem tem três meses de sistema mostraria um quarto do gasto real.
            </Text>
          </Card>
        </>
      )}
    </Screen>
  );
}

function Linha({
  rotulo,
  valor,
  tom,
  forte,
}: {
  rotulo: string;
  valor: string;
  tom?: 'saida' | 'lucro';
  forte?: boolean;
}): React.ReactElement {
  return (
    <View style={styles.linha}>
      <Text style={styles.linhaRotulo}>{rotulo}</Text>
      <Text
        style={[
          styles.linhaValor,
          forte && styles.linhaValorForte,
          tom === 'saida' && styles.linhaValorSaida,
          tom === 'lucro' && styles.linhaValorLucro,
        ]}
      >
        {money(valor)}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  cabecalho: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.lg,
    ...layout.coluna,
  },
  seta: { ...typography.title, color: colors.red, paddingHorizontal: spacing.sm },
  ano: { ...typography.display, color: colors.text },
  escopo: { alignItems: 'center', marginTop: spacing.sm, marginBottom: spacing.md },
  grade: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
    justifyContent: 'space-between',
  },
  mes: {
    width: '31%',
    borderRadius: radius.md,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    paddingVertical: 10,
    paddingHorizontal: 8,
    marginBottom: spacing.sm,
  },
  mesDeHoje: { borderColor: colors.red },
  mesTocado: { opacity: 0.6 },
  mesVazio: { opacity: 0.45 },
  mesNome: { ...typography.caption, color: colors.textFaint, fontWeight: '700' },
  mesEntrou: { ...typography.caption, color: colors.white, marginTop: 4 },
  mesSaiu: { ...typography.caption, color: colors.red },
  legenda: { ...typography.caption, color: colors.textMuted, marginBottom: spacing.md },
  legendaEntrou: { color: colors.white },
  legendaSaiu: { color: colors.red },
  legendaToque: { color: colors.textFaint },
  linha: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.md,
    paddingVertical: 9,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  linhaRotulo: { ...typography.body, color: colors.textMuted, flex: 1 },
  linhaValor: { ...typography.body, color: colors.text },
  linhaValorForte: { ...typography.title, color: colors.text },
  linhaValorSaida: { color: colors.red },
  linhaValorLucro: { color: colors.white, fontWeight: '700' },
  nota: { ...typography.caption, color: colors.textFaint, marginTop: spacing.sm },
});
