/**
 * Contas e cartões: ver as que existem e cadastrar outra.
 *
 * O formulário pede duas coisas - o nome do banco e o titular - e esconde o
 * resto atrás de "mais detalhes". Essa escolha não é só de ergonomia: enquanto
 * o sistema não conversa com banco nenhum, digitar agência, conta e limite seria
 * guardar informação sensível sem nada em troca. O servidor, por garantia, apaga
 * número de conta que venha grudado no nome antes de gravar.
 */

import React, { useMemo, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';

import { useAccounts, useCreateAccount, useMe, useMembers } from '@/api/queries';
import type { AccountType } from '@/api/types';
import {
  Botao,
  Card,
  Chip,
  Field,
  Mensagem,
  Screen,
  SectionTitle,
  SwitchRow,
} from '@/components/ui';
import { colors, spacing, typography } from '@/theme';
import { money } from '@/theme/format';

/** Os tipos na ordem em que aparecem na vida: o primeiro é o padrão. */
const TIPOS: { valor: AccountType; rotulo: string }[] = [
  { valor: 'CONTA_CORRENTE', rotulo: 'Conta corrente' },
  { valor: 'CARTAO_CREDITO', rotulo: 'Cartão de crédito' },
  { valor: 'DINHEIRO', rotulo: 'Dinheiro' },
  { valor: 'POUPANCA', rotulo: 'Poupança' },
  { valor: 'INVESTIMENTO', rotulo: 'Investimento' },
  { valor: 'PJ', rotulo: 'Conta da empresa' },
  { valor: 'OUTRO', rotulo: 'Outro' },
];

const ROTULO_TIPO: Record<AccountType, string> = TIPOS.reduce(
  (acc, t) => ({ ...acc, [t.valor]: t.rotulo }),
  {} as Record<AccountType, string>,
);

/** Aceita "1.234,56", "1234.56" e "1234". Vazio vira undefined, não zero. */
function paraNumero(texto: string): number | undefined {
  const limpo = texto.trim().replace(/\s/g, '').replace(/\./g, '').replace(',', '.');
  if (!limpo) return undefined;
  const n = Number(limpo);
  return Number.isFinite(n) ? n : undefined;
}

function paraDia(texto: string): number | undefined {
  const n = paraNumero(texto);
  if (n === undefined) return undefined;
  const dia = Math.trunc(n);
  return dia >= 1 && dia <= 31 ? dia : undefined;
}

export function AccountsScreen(): React.ReactElement {
  const { data: accounts, isLoading } = useAccounts();
  const { data: members } = useMembers();
  const { data: eu } = useMe();
  const criar = useCreateAccount();

  const [nome, setNome] = useState('');
  const [titular, setTitular] = useState<string | null>(null);
  const [tipo, setTipo] = useState<AccountType>('CONTA_CORRENTE');
  const [detalhes, setDetalhes] = useState(false);
  const [saldo, setSaldo] = useState('');
  const [limite, setLimite] = useState('');
  const [fechamento, setFechamento] = useState('');
  const [vencimento, setVencimento] = useState('');
  const [compartilhada, setCompartilhada] = useState(false);
  const [daEmpresa, setDaEmpresa] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [gravada, setGravada] = useState<string | null>(null);

  const donoEscolhido = titular ?? eu?.id ?? null;
  const podeGravar = nome.trim().length > 0 && Boolean(donoEscolhido) && !criar.isPending;

  const cartao = tipo === 'CARTAO_CREDITO';

  const total = useMemo(
    () =>
      (accounts ?? [])
        .filter((c) => !c.is_business)
        .reduce((soma, c) => soma + Number(c.current_balance), 0),
    [accounts],
  );

  function limpar(): void {
    setNome('');
    setSaldo('');
    setLimite('');
    setFechamento('');
    setVencimento('');
    setCompartilhada(false);
    setDaEmpresa(false);
    setDetalhes(false);
    setTipo('CONTA_CORRENTE');
  }

  async function gravar(): Promise<void> {
    if (!podeGravar || !donoEscolhido) return;
    setErro(null);
    setGravada(null);
    try {
      const conta = await criar.mutateAsync({
        name: nome.trim(),
        type: tipo,
        owner_member_id: donoEscolhido,
        // os campos em branco não vão na requisição: o servidor usa o padrão
        ...(paraNumero(saldo) !== undefined ? { current_balance: paraNumero(saldo) } : {}),
        ...(cartao && paraNumero(limite) !== undefined
          ? { credit_limit: paraNumero(limite) }
          : {}),
        ...(paraDia(fechamento) !== undefined
          ? { statement_close_day: paraDia(fechamento) }
          : {}),
        ...(paraDia(vencimento) !== undefined ? { statement_due_day: paraDia(vencimento) } : {}),
        ...(compartilhada ? { is_shared: true } : {}),
        ...(daEmpresa || tipo === 'PJ' ? { is_business: true } : {}),
      });
      setGravada(conta.name);
      limpar();
    } catch (err) {
      setErro(err instanceof Error ? err.message : 'Nao consegui cadastrar a conta.');
    }
  }

  return (
    <Screen>
      <SectionTitle>Contas cadastradas</SectionTitle>
      <Card>
        {isLoading ? (
          <ActivityIndicator color={colors.red} />
        ) : (accounts ?? []).length === 0 ? (
          <Text style={styles.vazio}>
            Nenhuma conta ainda. Cadastre a primeira aqui embaixo — é ela que recebe os
            lançamentos e os extratos.
          </Text>
        ) : (
          <>
            {(accounts ?? []).map((conta) => (
              <View key={conta.id} style={styles.linha}>
                <View style={styles.linhaMain}>
                  <Text style={styles.linhaNome}>{conta.name}</Text>
                  <Text style={styles.linhaTipo}>
                    {ROTULO_TIPO[conta.type] ?? conta.type}
                    {conta.is_business ? ' · da empresa' : ''}
                    {conta.is_shared ? ' · conjunta' : ''}
                  </Text>
                </View>
                <Text style={styles.linhaSaldo}>{money(conta.current_balance)}</Text>
              </View>
            ))}
            <View style={styles.totalLinha}>
              <Text style={styles.totalRotulo}>Somando as suas</Text>
              <Text style={styles.totalValor}>{money(total)}</Text>
            </View>
          </>
        )}
      </Card>

      <SectionTitle>Cadastrar conta</SectionTitle>
      <Card>
        {gravada ? <Mensagem tom="ok">{`Pronto: "${gravada}" foi cadastrada.`}</Mensagem> : null}
        {erro ? <Mensagem tom="erro">{erro}</Mensagem> : null}

        <Field
          label="Nome do banco"
          value={nome}
          onChangeText={setNome}
          placeholder="Itaú, Nubank, BB…"
          autoCapitalize="words"
          ajuda="Só o banco. Não escreva agência nem número de conta — não servem para nada aqui."
        />

        <Text style={styles.rotulo}>Titular</Text>
        <View style={styles.opcoes}>
          {(members ?? []).map((membro) => (
            <Chip
              key={membro.id}
              active={membro.id === donoEscolhido}
              onPress={() => setTitular(membro.id)}
            >
              {membro.name}
            </Chip>
          ))}
        </View>

        <Text style={styles.rotulo}>Tipo</Text>
        <View style={styles.opcoes}>
          {TIPOS.map((t) => (
            <Chip key={t.valor} active={t.valor === tipo} onPress={() => setTipo(t.valor)}>
              {t.rotulo}
            </Chip>
          ))}
        </View>

        <Pressable
          onPress={() => setDetalhes((v) => !v)}
          accessibilityRole="button"
          style={styles.maisLinha}
        >
          <Text style={styles.maisTexto}>
            {detalhes ? '− Esconder os detalhes' : '+ Mais detalhes (tudo opcional)'}
          </Text>
        </Pressable>

        {detalhes ? (
          <View style={styles.detalhes}>
            <Field
              label="Saldo de hoje"
              value={saldo}
              onChangeText={setSaldo}
              placeholder="0,00"
              keyboardType="decimal-pad"
              opcional
              ajuda="Em branco, começa em zero. O saldo se ajusta sozinho conforme os lançamentos entram."
            />
            {cartao ? (
              <Field
                label="Limite do cartão"
                value={limite}
                onChangeText={setLimite}
                placeholder="0,00"
                keyboardType="decimal-pad"
                opcional
              />
            ) : null}
            <Field
              label="Dia em que a fatura ou o extrato fecha"
              value={fechamento}
              onChangeText={setFechamento}
              placeholder="1 a 31"
              keyboardType="number-pad"
              opcional
              ajuda="Serve para o sistema avisar quando um extrato do mês não chegou."
            />
            <Field
              label="Dia do vencimento"
              value={vencimento}
              onChangeText={setVencimento}
              placeholder="1 a 31"
              keyboardType="number-pad"
              opcional
            />
            <SwitchRow
              label="Conta conjunta"
              ajuda="Aparece na visão “só eu” de todo mundo que usa a conta."
              value={compartilhada}
              onChange={setCompartilhada}
            />
            <SwitchRow
              label="Conta da empresa"
              ajuda="O saldo fica fora do patrimônio da família, e o extrato dela é triado linha a linha."
              value={daEmpresa || tipo === 'PJ'}
              onChange={setDaEmpresa}
            />
          </View>
        ) : null}

        <Botao onPress={gravar} disabled={!podeGravar}>
          {criar.isPending ? 'Cadastrando…' : 'Cadastrar conta'}
        </Botao>
      </Card>
    </Screen>
  );
}

const styles = StyleSheet.create({
  vazio: { ...typography.caption, color: colors.textMuted },
  linha: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  linhaMain: { flex: 1 },
  linhaNome: { ...typography.body, color: colors.text },
  linhaTipo: { ...typography.caption, color: colors.textFaint, marginTop: 2 },
  linhaSaldo: { ...typography.body, color: colors.text },
  totalLinha: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingTop: spacing.md,
  },
  totalRotulo: { ...typography.caption, color: colors.textFaint },
  totalValor: { ...typography.body, color: colors.text, fontWeight: '700' },
  rotulo: { ...typography.caption, color: colors.textMuted, marginBottom: 6 },
  opcoes: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
    marginBottom: spacing.md,
  },
  maisLinha: { paddingVertical: spacing.sm },
  maisTexto: { ...typography.caption, color: colors.red, fontWeight: '700' },
  detalhes: { marginTop: spacing.sm },
});
