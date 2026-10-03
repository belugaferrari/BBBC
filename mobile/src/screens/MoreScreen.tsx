/**
 * Mais: o que não é do dia a dia.
 *
 * As abas de baixo carregam o que se olha toda semana. O que se usa uma vez por
 * mês (mandar o extrato), uma vez por ano (o IR) ou uma vez na vida (cadastrar
 * a conta) fica aqui - e aqui é um lugar, não um esconderijo: cada linha diz
 * para que serve, porque "Contas" sem explicação foi exatamente o que não se
 * achou antes.
 */

import React from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { useAccounts, useMe } from '@/api/queries';
import { Card, MenuRow, Screen, SectionTitle } from '@/components/ui';
import { colors, spacing, typography } from '@/theme';

export interface MoreScreenProps {
  aoEscolher: (
    destino: 'Contas' | 'Importar' | 'Cartoes' | 'Previsoes' | 'Investimentos' | 'IR',
  ) => void;
}

export function MoreScreen({ aoEscolher }: MoreScreenProps): React.ReactElement {
  const { data: accounts } = useAccounts();
  const { data: eu } = useMe();
  const quantas = (accounts ?? []).length;

  return (
    <Screen>
      {eu ? (
        <View style={styles.cabecalho}>
          <Text style={styles.ola}>{eu.nickname || eu.full_name}</Text>
          <Text style={styles.olaHint}>
            {quantas === 0
              ? 'Nenhuma conta cadastrada ainda'
              : quantas === 1
                ? '1 conta cadastrada'
                : `${quantas} contas cadastradas`}
          </Text>
        </View>
      ) : null}

      <SectionTitle>Cadastro</SectionTitle>
      <Card>
        <MenuRow
          icon="▤"
          title="Contas e cartões"
          subtitle="Cadastrar banco, cartão ou carteira de dinheiro"
          onPress={() => aoEscolher('Contas')}
        />
        <MenuRow
          icon="↥"
          title="Importar extrato"
          subtitle="Mandar OFX, CSV ou PDF e conferir linha a linha"
          onPress={() => aoEscolher('Importar')}
        />
      </Card>

      <SectionTitle>No mês</SectionTitle>
      <Card>
        <MenuRow
          icon="▭"
          title="Cartão de crédito"
          subtitle="Quanto foi comprado no cartão, e o que pode estar contado em dobro"
          onPress={() => aoEscolher('Cartoes')}
        />
        <MenuRow
          icon="◎"
          title="Previsões"
          subtitle="Como ficam os próximos meses, com o que já está combinado"
          onPress={() => aoEscolher('Previsoes')}
        />
      </Card>

      <SectionTitle>Patrimônio e imposto</SectionTitle>
      <Card>
        <MenuRow
          icon="◈"
          title="Investimentos"
          subtitle="Carteira, rendimento e comparação com o CDI"
          onPress={() => aoEscolher('Investimentos')}
        />
        <MenuRow
          icon="%"
          title="Imposto de Renda"
          subtitle="Projeção do ano, completo contra simplificado"
          onPress={() => aoEscolher('IR')}
        />
      </Card>

      {quantas === 0 ? (
        <Text style={styles.dica}>
          Comece por “Contas e cartões”: é a conta que recebe tanto o lançamento à mão quanto o
          extrato importado.
        </Text>
      ) : null}
    </Screen>
  );
}

const styles = StyleSheet.create({
  cabecalho: { marginBottom: spacing.lg },
  ola: { ...typography.title, color: colors.text },
  olaHint: { ...typography.caption, color: colors.textFaint, marginTop: 2 },
  dica: { ...typography.caption, color: colors.textMuted, marginTop: spacing.md },
});
