/**
 * Doações recebidas: quem deu, quanto no ano, e o imposto que importa.
 *
 * Os avós depositam todo mês para pagar a escola das meninas. O dinheiro passa
 * pela conta da família, mas não é dela — e é por isso que esta tela existe
 * separada do Resumo: no Resumo a doação sai da renda, aqui ela é somada por
 * quem deu, que é a conta que o imposto pede e que nenhuma planilha de gastos
 * costuma ter.
 *
 * SOBRE O IMPOSTO, com cuidado, porque são dois e confundi-los é o erro comum:
 *
 *   • IMPOSTO DE RENDA (federal). Doação recebida não paga. Ela é declarada em
 *     "Rendimentos Isentos e Não Tributáveis", e o sistema já a leva para lá
 *     sozinho, pela categoria.
 *
 *   • ITCMD (estadual). Esse sim incide sobre doação, e é dele o limite de
 *     isenção. A alíquota e o limite MUDAM DE ESTADO PARA ESTADO e são
 *     corrigidos todo ano — não existe um número nacional. Por isso o campo
 *     nasce vazio em vez de vir preenchido: um número chutado tranquilizaria
 *     sobre um limite que pode não ser o deste estado, o que é pior que não
 *     dizer nada.
 *
 *   • E a ESCOLA continua dedutível por quem a pagou e declara a dependente.
 *     Receber doação isenta não tira esse direito.
 *
 * Nada aqui apura nem recolhe imposto: a conversa final é com o contador.
 */

import React, { useState } from 'react';
import { ActivityIndicator, StyleSheet, Text, View } from 'react-native';

import {
  useArchiveDonor,
  useCreateDonor,
  useDonationsSummary,
  useDonors,
  useSaveItcmdLimit,
  useSetDonor,
} from '@/api/queries';
import { Botao, Card, Chip, Field, Mensagem, Screen, SectionTitle } from '@/components/ui';
import { colors, radius, spacing, typography } from '@/theme';
import { dayLabel, money, percent } from '@/theme/format';

/** Aceita "64.000", "64000,00" e "64 mil" não — número é número. */
function paraValor(texto: string): number | null {
  const limpo = texto.trim().replace(/[^\d.,]/g, '').replace(/\./g, '').replace(',', '.');
  if (!limpo) return null;
  const n = Number(limpo);
  return Number.isFinite(n) && n >= 0 ? n : null;
}

function anoAtual(): number {
  return new Date().getFullYear();
}

export function DonationsScreen(): React.ReactElement {
  const [ano, setAno] = useState(anoAtual);
  const { data, isLoading } = useDonationsSummary(ano);
  const { data: doadores } = useDonors();
  const criar = useCreateDonor();
  const arquivar = useArchiveDonor();
  const salvarLimite = useSaveItcmdLimit();
  const apontarDoador = useSetDonor();

  const [nome, setNome] = useState('');
  const [parentesco, setParentesco] = useState('');
  const [uf, setUf] = useState('');
  const [limite, setLimite] = useState('');
  const [editandoLimite, setEditandoLimite] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [recado, setRecado] = useState<string | null>(null);

  if (isLoading || !data) {
    return (
      <Screen>
        <ActivityIndicator color={colors.red} />
      </Screen>
    );
  }

  async function cadastrar(): Promise<void> {
    setErro(null);
    setRecado(null);
    try {
      await criar.mutateAsync({
        name: nome.trim(),
        ...(parentesco.trim() ? { relationship: parentesco.trim() } : {}),
      });
      setRecado(`${nome.trim()} cadastrado. Já aparece no lançamento de entrada.`);
      setNome('');
      setParentesco('');
    } catch (err) {
      setErro(err instanceof Error ? err.message : 'Nao consegui cadastrar.');
    }
  }

  async function gravarLimite(): Promise<void> {
    setErro(null);
    setRecado(null);
    const valor = paraValor(limite);
    try {
      await salvarLimite.mutateAsync({
        itcmd_state: uf.trim().toUpperCase() || undefined,
        itcmd_annual_exemption: valor,
      });
      setEditandoLimite(false);
      setRecado(
        valor === null
          ? 'Limite apagado. Volto a avisar que ele não está preenchido.'
          : `Limite de ${money(valor)} por doador, por ano, guardado.`,
      );
    } catch (err) {
      setErro(err instanceof Error ? err.message : 'Nao consegui guardar o limite.');
    }
  }

  const anos = [anoAtual(), anoAtual() - 1, anoAtual() - 2];

  return (
    <Screen>
      {recado ? <Mensagem tom="ok">{recado}</Mensagem> : null}
      {erro ? <Mensagem tom="erro">{erro}</Mensagem> : null}

      <View style={styles.anos}>
        {anos.map((a) => (
          <Chip key={a} active={a === ano} onPress={() => setAno(a)}>
            {String(a)}
          </Chip>
        ))}
      </View>

      <Card>
        <Text style={styles.rotulo}>Recebido em doação em {ano}</Text>
        <Text style={styles.valor}>{money(data.total)}</Text>
        <Text style={styles.hint}>
          Esse dinheiro entrou na conta e NÃO está somado na renda do mês. No imposto de renda ele
          é isento — vai em “Rendimentos Isentos e Não Tributáveis”.
        </Text>
      </Card>

      {data.aviso ? <Mensagem tom="neutro">{data.aviso}</Mensagem> : null}

      <SectionTitle>Por quem doou</SectionTitle>
      {data.donors.length === 0 ? (
        <Card>
          <Text style={styles.hint}>
            Ninguém cadastrado ainda. Cadastre quem deposita aqui embaixo — depois, ao lançar a
            entrada, escolha o nome e para que o dinheiro foi dado.
          </Text>
        </Card>
      ) : (
        data.donors.map((doador) => (
          <Card key={doador.id}>
            <View style={styles.linha}>
              <View style={styles.linhaMain}>
                <Text style={styles.nome}>
                  {doador.name}
                  {doador.relationship ? <Text style={styles.hint}>{`  ${doador.relationship}`}</Text> : null}
                </Text>
                <Text style={styles.hint}>
                  {doador.deposits === 0
                    ? 'Nenhum depósito neste ano'
                    : `${doador.deposits} depósito${doador.deposits > 1 ? 's' : ''}${
                        doador.last_on ? ` · último em ${dayLabel(doador.last_on)}` : ''
                      }`}
                </Text>
                {!doador.is_active ? (
                  <Text style={styles.hint}>Arquivado — fica aqui pelo que doou neste ano.</Text>
                ) : null}
              </View>
              <Text style={styles.total}>{money(doador.total)}</Text>
            </View>

            {doador.used_pct !== null ? (
              <View style={styles.barraFora}>
                <View
                  style={[
                    styles.barraDentro,
                    {
                      width: `${Math.min(100, Number(doador.used_pct) * 100)}%`,
                      backgroundColor: doador.should_alert ? colors.red : colors.white,
                    },
                  ]}
                />
              </View>
            ) : null}
            {doador.used_pct !== null ? (
              <Text style={doador.should_alert ? styles.alerta : styles.hint}>
                {`${percent(doador.used_pct)} do limite de isenção. Restam ${money(
                  doador.remaining,
                )} neste ano.`}
              </Text>
            ) : null}

            {doador.is_active ? (
              <Botao
                tom="secundario"
                disabled={arquivar.isPending}
                onPress={async () => {
                  setErro(null);
                  try {
                    const r = await arquivar.mutateAsync(doador.id);
                    setRecado(`${r.nome} saiu da lista. O que já doou continua no histórico.`);
                  } catch (err) {
                    setErro(err instanceof Error ? err.message : 'Nao consegui arquivar.');
                  }
                }}
              >
                Tirar da lista
              </Botao>
            ) : null}
          </Card>
        ))
      )}

      {Number(data.sem_doador) > 0 ? (
        <Card>
          <Text style={styles.rotulo}>Doação sem dono</Text>
          <Text style={styles.total}>{money(data.sem_doador)}</Text>
          <Text style={styles.hint}>
            Entrou como doação, mas sem dizer quem depositou — é assim que o depósito chega do
            extrato, porque o banco não sabe quem foi. Está no total do ano e fora da conta por
            doador, e o limite de isenção é contado por doador. Toque no nome para resolver.
          </Text>
          {data.sem_doador_lancamentos.map((lancamento) => (
            <View key={lancamento.id} style={styles.pendente}>
              <View style={styles.linha}>
                <View style={styles.linhaMain}>
                  <Text style={styles.nome}>{money(lancamento.amount)}</Text>
                  <Text style={styles.hint}>
                    {`${dayLabel(lancamento.booked_on)} · ${lancamento.description}`}
                  </Text>
                </View>
              </View>
              <View style={styles.chips}>
                {(doadores ?? []).map((doador) => (
                  <Chip
                    key={doador.id}
                    active={false}
                    onPress={async () => {
                      setErro(null);
                      setRecado(null);
                      try {
                        await apontarDoador.mutateAsync({
                          transaction_id: lancamento.id,
                          donor_id: doador.id,
                        });
                        setRecado(`${money(lancamento.amount)} agora conta como doação de ${doador.name}.`);
                      } catch (err) {
                        setErro(err instanceof Error ? err.message : 'Nao consegui apontar.');
                      }
                    }}
                  >
                    {doador.name}
                  </Chip>
                ))}
              </View>
              {(doadores ?? []).length === 0 ? (
                <Text style={styles.hint}>
                  Cadastre quem deposita aqui embaixo e o nome aparece para escolher.
                </Text>
              ) : null}
            </View>
          ))}
        </Card>
      ) : null}

      <SectionTitle>Quem deposita</SectionTitle>
      <Card>
        <Field label="Nome" value={nome} onChangeText={setNome} placeholder="Vera, José…" />
        <Field
          label="Parentesco"
          value={parentesco}
          onChangeText={setParentesco}
          placeholder="sogra, sogro, tio…"
          opcional
        />
        <Botao onPress={cadastrar} disabled={!nome.trim() || criar.isPending}>
          {criar.isPending ? 'Cadastrando…' : 'Cadastrar'}
        </Botao>
        {(doadores ?? []).length > 0 ? (
          <Text style={styles.hint}>
            {`Na lista hoje: ${(doadores ?? []).map((d) => d.name).join(', ')}.`}
          </Text>
        ) : null}
      </Card>

      <SectionTitle>Limite de isenção (ITCMD)</SectionTitle>
      <Card>
        {editandoLimite ? (
          <>
            <Field
              label="Estado"
              value={uf}
              onChangeText={setUf}
              placeholder="SP, RJ, MG…"
              autoCapitalize="characters"
            />
            <Field
              label="Limite por doador, por ano"
              value={limite}
              onChangeText={setLimite}
              placeholder="0,00"
              keyboardType="decimal-pad"
              ajuda="Deixe vazio para apagar o limite e voltar ao aviso."
            />
            <Botao onPress={gravarLimite} disabled={salvarLimite.isPending}>
              {salvarLimite.isPending ? 'Guardando…' : 'Guardar'}
            </Botao>
          </>
        ) : (
          <>
            <Text style={styles.rotulo}>
              {data.itcmd_state ? `Estado: ${data.itcmd_state}` : 'Estado não informado'}
            </Text>
            <Text style={styles.total}>
              {data.itcmd_annual_exemption ? money(data.itcmd_annual_exemption) : 'não preenchido'}
            </Text>
            <Botao
              tom="secundario"
              onPress={() => {
                setUf(data.itcmd_state ?? '');
                setLimite(
                  data.itcmd_annual_exemption
                    ? String(Number(data.itcmd_annual_exemption)).replace('.', ',')
                    : '',
                );
                setEditandoLimite(true);
              }}
            >
              {data.itcmd_annual_exemption ? 'Mudar o limite' : 'Preencher o limite'}
            </Botao>
          </>
        )}
        <Text style={styles.hint}>
          O ITCMD é imposto ESTADUAL: a alíquota e o limite mudam de estado para estado e são
          corrigidos todo ano. Por isso o número é digitado aqui, e não embutido no sistema —
          confirme o do seu estado com o contador. Isto aqui só soma e avisa: não apura nem
          recolhe nada.
        </Text>
        <Text style={styles.hint}>
          Lembrando que são dois impostos diferentes: no imposto de renda a doação recebida é
          isenta, e a escola continua dedutível por quem a pagou e declara a dependente.
        </Text>
      </Card>
    </Screen>
  );
}

const styles = StyleSheet.create({
  anos: { flexDirection: 'row', gap: spacing.sm, marginBottom: spacing.sm },
  rotulo: { ...typography.caption, color: colors.textMuted },
  valor: { ...typography.display, color: colors.text, marginVertical: 4 },
  total: { ...typography.title, color: colors.text, marginVertical: 2 },
  hint: { ...typography.caption, color: colors.textMuted, marginTop: spacing.sm },
  alerta: { ...typography.caption, color: colors.red, marginTop: spacing.sm, fontWeight: '700' },
  linha: { flexDirection: 'row', alignItems: 'flex-start', gap: spacing.md },
  linhaMain: { flex: 1 },
  nome: { ...typography.body, color: colors.text, fontWeight: '700' },
  barraFora: {
    height: 6,
    backgroundColor: colors.surfaceAlt,
    borderRadius: radius.sm,
    marginTop: spacing.md,
    overflow: 'hidden',
  },
  barraDentro: { height: 6, borderRadius: radius.sm },
  pendente: {
    marginTop: spacing.md,
    paddingTop: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm, marginTop: spacing.sm },
});
