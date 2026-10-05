/**
 * Importar extrato: escolher arquivo, conferir e confirmar.
 *
 * A tela existe por causa do passo do meio. O backend nunca grava nada no
 * envio - o que chega aqui e uma proposta, e o usuario decide linha a linha.
 * Linhas ja existentes vem desmarcadas, com o motivo escrito.
 *
 * E a decisao inclui a CATEGORIA. Antes, a sugestao do sistema aparecia como
 * texto e nao havia o que fazer com ela: para trocar, era gravar errado e
 * corrigir depois, lancamento por lancamento, na lista de gastos. Agora a
 * categoria e um botao em cada linha, e a troca acontece antes de existir
 * lancamento - que e quando ela e mais barata.
 *
 * Duas coisas aparecem diferentes de proposito:
 *
 *   * a sugestao com base em algo ("SUPERMERCADO X" -> Mercado) vem como
 *     sugestao;
 *   * a ausencia de sugestao vem como "A definir", em vermelho, porque e o que
 *     precisa de atencao. Mostrar as duas iguais faria a segunda passar por
 *     sugestao e ser confirmada sem ninguem olhar.
 */

import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import * as DocumentPicker from 'expo-document-picker';
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';

import { useAccounts, useCategories, useStatementChecklist } from '@/api/queries';
import { confirmImport, desfazerImport, listImports, uploadStatement } from '@/api/imports';
import type {
  Category,
  ImportPreviewRow,
  StatementImport,
  StatementImportResumo,
} from '@/api/types';
import { Botao, Card, Field, MoneyValue, SectionTitle } from '@/components/ui';
import { colors, layout, radius, spacing, typography } from '@/theme';
import { filtrar } from '@/components/busca';
import { folhas } from '@/screens/EntryScreen';
import { dayLabel, mesLabel, money } from '@/theme/format';

type Phase = 'escolha' | 'lendo' | 'conferencia' | 'gravando' | 'pronto';

/**
 * O que o seletor de arquivos aceita.
 *
 * As extensoes estao na lista junto com os tipos MIME de proposito: no
 * navegador, o seletor usa esta lista como o atributo `accept`, e banco
 * brasileiro entrega .ofx com tipo MIME em branco ou generico - so o tipo MIME
 * deixaria o arquivo certo apagado na janela. O `*​/*` no fim garante que nada
 * fique de fora quando o banco inventar outra extensao.
 */
const ACCEPTED = [
  '.ofx',
  '.ofc',
  '.qfx',
  '.csv',
  '.txt',
  '.pdf',
  '.xlsx',
  '.xlsm',
  'application/x-ofx',
  'application/pdf',
  'text/csv',
  'text/comma-separated-values',
  'text/plain',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  '*/*',
];

type Lado = 'ENTRADA' | 'SAIDA';
type LinhaDoExtrato = { index: number; direction: Lado };

/** Todas as linhas estão do lado contrário ao que o arquivo disse. */
export function estaTudoVirado(
  preview: LinhaDoExtrato[],
  virado: Record<number, Lado>,
): boolean {
  if (preview.length === 0) return false;
  return preview.every((row) => virado[row.index] !== undefined);
}

/**
 * O "multiplicar tudo por -1": o que cada linha passa a ser depois do toque.
 *
 * O sistema já corrige sozinho a fatura que vem com o sinal da dívida, e cada
 * linha se vira sozinha no seletor. Isto é o atalho para quando o arquivo
 * inteiro está ao contrário: um toque em vez de trinta.
 *
 * Com tudo já virado, devolve o mapa vazio — virar o extrato errado tem de ser
 * tão fácil quanto virar o certo, então a volta fica no mesmo botão.
 */
export function virarTodasAsLinhas(
  preview: LinhaDoExtrato[],
  virado: Record<number, Lado>,
): Record<number, Lado> {
  if (estaTudoVirado(preview, virado)) return {};
  return Object.fromEntries(
    preview.map((row) => [row.index, row.direction === 'SAIDA' ? 'ENTRADA' : 'SAIDA']),
  );
}

function mesAtual(): string {
  const hoje = new Date();
  return `${hoje.getFullYear()}-${String(hoje.getMonth() + 1).padStart(2, '0')}-01`;
}

export function ImportScreen(): React.ReactElement {
  const navigation = useNavigation<NativeStackNavigationProp<{ Contas: undefined }>>();
  const { data: accounts } = useAccounts();
  const { data: checklist } = useStatementChecklist(mesAtual());
  const [accountId, setAccountId] = useState<string | null>(null);
  const [phase, setPhase] = useState<Phase>('escolha');
  const [batch, setBatch] = useState<StatementImport | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [error, setError] = useState<string | null>(null);
  // index da linha -> categoria escolhida a mao nesta conferencia
  const [escolhidas, setEscolhidas] = useState<Record<number, string>>({});
  // index da linha -> lado virado a mao. O sistema ja corrige o sinal invertido
  // da fatura de cartao sozinho; isto e a saida de emergencia para o leiaute que
  // ele ainda nao conhece - porque direcao errada, depois de gravada, era o
  // unico erro que nao tinha conserto pela tela.
  const [direcoes, setDirecoes] = useState<Record<number, 'ENTRADA' | 'SAIDA'>>({});
  // Os lotes já importados, para poder DESFAZER um.
  //
  // Nasceu de um caso concreto: a fatura do cartão entrou com o sinal invertido
  // e as compras viraram renda. Sem desfazer, a saída era apagar dezenas de
  // linhas uma por uma - e reimportar o arquivo corrigido deixaria as duas
  // versões somadas, porque a direção entra na impressão digital.
  const [lotes, setLotes] = useState<StatementImportResumo[]>([]);
  const [confirmandoDesfazer, setConfirmandoDesfazer] = useState<string | null>(null);
  const [desfazendo, setDesfazendo] = useState<string | null>(null);
  const [desfeito, setDesfeito] = useState<string | null>(null);
  // qual linha esta com o seletor aberto (uma por vez: duas listas abertas na
  // mesma tela nao cabem no celular)
  const [escolhendo, setEscolhendo] = useState<number | null>(null);
  const { data: categories } = useCategories();
  const queryClient = useQueryClient();

  // Importar e desfazer mexem no mês inteiro, e as telas de números guardam
  // cópia. Sem jogar a cópia fora, ele confirma a importação e volta para um
  // Resumo que ainda não viu o que entrou.
  const recalcular = useCallback(() => {
    for (const chave of [
      'dashboard',
      'transactions',
      'by-category',
      'category-overview',
      'forecast',
      'card-summary',
      'evolucao',
      'statement-checklist',
      'reembolsaveis',
    ]) {
      queryClient.invalidateQueries({ queryKey: [chave] });
    }
  }, [queryClient]);

  const opcoes = useMemo(() => folhas(categories ?? []), [categories]);
  const nomePorId = useMemo(() => {
    const mapa = new Map<string, string>();
    opcoes.forEach((f) => mapa.set(f.categoria.id, f.caminho));
    return mapa;
  }, [opcoes]);

  const conta = accountId ?? accounts?.[0]?.id ?? null;
  const contaEscolhida = (accounts ?? []).find((c) => c.id === conta) ?? null;

  const totals = useMemo(() => {
    if (!batch) return { entrada: 0, saida: 0 };
    return batch.preview
      .filter((row) => selected.has(row.index))
      .reduce(
        (acc, row) => {
          const value = Number(row.amount);
          if ((direcoes[row.index] ?? row.direction) === 'ENTRADA') acc.entrada += value;
          else acc.saida += value;
          return acc;
        },
        { entrada: 0, saida: 0 },
      );
  }, [batch, selected, direcoes]);

  // Quantas linhas marcadas ainda vao entrar sem categoria de verdade. Nao
  // impede de confirmar - e o ponto do "A definir" poder ser resolvido depois -
  // mas dizer o numero antes e o que evita a surpresa no fim do mes.
  const pendentes = useMemo(() => {
    if (!batch) return 0;
    return batch.preview.filter(
      (row) =>
        selected.has(row.index) && !escolhidas[row.index] && row.suggested_is_pending,
    ).length;
  }, [batch, selected, escolhidas]);

  const carregarLotes = useCallback(async () => {
    try {
      const todos = await listImports();
      // só o que de fato está valendo: lote descartado não tem o que desfazer
      setLotes(todos.filter((l) => l.status === 'CONFIRMADO' && l.rows_imported > 0));
    } catch {
      // sem servidor a lista fica vazia, e a tela de importar não depende dela
      setLotes([]);
    }
  }, []);

  useEffect(() => {
    if (phase === 'escolha') void carregarLotes();
  }, [phase, carregarLotes]);

  async function desfazer(id: string): Promise<void> {
    setDesfazendo(id);
    setError(null);
    try {
      const resultado = await desfazerImport(id);
      setDesfeito(
        resultado.lancamentos_apagados === 1
          ? '1 lançamento apagado. Pode importar o arquivo de novo.'
          : `${resultado.lancamentos_apagados} lançamentos apagados. Pode importar o arquivo de novo.`,
      );
      setConfirmandoDesfazer(null);
      recalcular();
      await carregarLotes();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Nao consegui desfazer');
    } finally {
      setDesfazendo(null);
    }
  }

  const tudoVirado = Boolean(batch) && estaTudoVirado(batch?.preview ?? [], direcoes);

  function virarTudo(): void {
    if (!batch) return;
    setDirecoes(virarTodasAsLinhas(batch.preview, direcoes));
    // as sugestões eram todas do outro lado
    setEscolhidas({});
  }

  async function escolherArquivo(): Promise<void> {
    if (!conta) {
      setError('Cadastre uma conta antes de importar — o botão acima leva até lá.');
      return;
    }
    const picked = await DocumentPicker.getDocumentAsync({
      type: ACCEPTED,
      copyToCacheDirectory: true,
    });
    if (picked.canceled || !picked.assets?.[0]) return;

    setPhase('lendo');
    setError(null);
    try {
      const resultado = await uploadStatement(conta, picked.assets[0]);
      setBatch(resultado);
      setSelected(new Set(resultado.preview.filter((r) => r.selected).map((r) => r.index)));
      setPhase('conferencia');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Nao consegui ler o arquivo');
      setPhase('escolha');
    }
  }

  async function confirmar(): Promise<void> {
    if (!batch) return;
    setPhase('gravando');
    try {
      const resultado = await confirmImport(batch.id, [...selected], escolhidas, direcoes);
      setBatch(resultado);
      recalcular();
      setPhase('pronto');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Nao consegui confirmar');
      setPhase('conferencia');
    }
  }

  function alternar(index: number): void {
    setSelected((atual) => {
      const proximo = new Set(atual);
      if (proximo.has(index)) proximo.delete(index);
      else proximo.add(index);
      return proximo;
    });
  }

  if (phase === 'lendo' || phase === 'gravando') {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={colors.red} />
        <Text style={styles.hint}>
          {phase === 'lendo' ? 'Lendo o extrato...' : 'Gravando os lancamentos...'}
        </Text>
      </View>
    );
  }

  if (phase === 'pronto' && batch) {
    return (
      <View style={styles.center}>
        <Text style={styles.done}>{batch.rows_imported}</Text>
        <Text style={styles.doneLabel}>
          {batch.rows_imported === 1 ? 'lancamento importado' : 'lancamentos importados'}
        </Text>
        {batch.rows_duplicated > 0 && (
          <Text style={styles.hint}>
            {batch.rows_duplicated} ja existiam e foram ignorados.
          </Text>
        )}
        <Pressable
          style={styles.button}
          onPress={() => {
            setBatch(null);
            setSelected(new Set());
            setEscolhidas({});
            setDirecoes({});
            setEscolhendo(null);
            setPhase('escolha');
          }}
        >
          <Text style={styles.buttonText}>Importar outro</Text>
        </Pressable>
      </View>
    );
  }

  if (phase === 'escolha' || !batch) {
    return (
      <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
        {checklist && checklist.expected > 0 ? (
          <>
            <SectionTitle>Extratos deste mês</SectionTitle>
            <Card>
              <Text style={styles.checklistTitle}>
                {checklist.received} de {checklist.expected} bancos já mandaram
              </Text>
              {checklist.late_list.map((conta) => (
                <View key={conta.account_id} style={styles.checkline}>
                  <Text style={styles.checkLate}>●</Text>
                  <Text style={styles.checkName}>{conta.name}</Text>
                  <Text style={styles.checkLate}>
                    {conta.days_late ? `${conta.days_late} dias de atraso` : 'atrasado'}
                  </Text>
                </View>
              ))}
              {checklist.pending_list.map((conta) => (
                <View key={conta.account_id} style={styles.checkline}>
                  <Text style={styles.checkPending}>○</Text>
                  <Text style={styles.checkName}>{conta.name}</Text>
                  <Text style={styles.checkPending}>
                    {conta.expected_day ? `sai dia ${conta.expected_day}` : 'aguardando'}
                  </Text>
                </View>
              ))}
              {checklist.received_list.map((conta) => (
                <View key={conta.account_id} style={styles.checkline}>
                  <Text style={styles.checkDone}>✓</Text>
                  <Text style={[styles.checkName, styles.checkDoneName]}>{conta.name}</Text>
                </View>
              ))}
            </Card>
          </>
        ) : null}

        <SectionTitle>Conta de destino</SectionTitle>
        {(accounts ?? []).length === 0 ? (
          <Card>
            <Text style={styles.explain}>
              O extrato precisa de uma conta para onde ir — é ela que diz de qual banco vieram os
              lançamentos. Cadastre uma e volte aqui; leva meio minuto, só o nome do banco é
              obrigatório.
            </Text>
            <Botao onPress={() => navigation.navigate('Contas')}>Cadastrar conta</Botao>
          </Card>
        ) : null}
        <View style={styles.accounts}>
          {(accounts ?? []).map((account) => {
            const ativa = account.id === conta;
            return (
              <Pressable
                key={account.id}
                onPress={() => setAccountId(account.id)}
                style={[styles.accountChip, ativa && styles.accountChipActive]}
              >
                <Text style={[styles.accountText, ativa && { color: colors.white }]}>
                  {account.name}
                  {account.type === 'CARTAO_CREDITO' ? ' · cartão' : ''}
                </Text>
              </Pressable>
            );
          })}
        </View>

        {contaEscolhida?.type === 'CARTAO_CREDITO' ? (
          <Card>
            <Text style={styles.checklistTitle}>Este extrato é de cartão de crédito</Text>
            <Text style={styles.explain}>
              As compras vão aparecer no dia em que foram feitas, mas só contam como gasto no
              mês em que a fatura é paga — que é quando o dinheiro sai da conta. Compra
              parcelada conta uma parcela por mês, e as que ainda não vieram aparecem como
              compromisso.
            </Text>
            {contaEscolhida.statement_close_day && contaEscolhida.statement_due_day ? (
              <Text style={styles.explain}>
                {`Fatura fecha dia ${contaEscolhida.statement_close_day} e vence dia ${contaEscolhida.statement_due_day}. A conferência mostra, linha por linha, em que mês cada compra vai contar.`}
              </Text>
            ) : (
              <>
                <Text style={styles.explain}>
                  Os dias da fatura deste cartão não estão cadastrados, então estou supondo que
                  ela fecha no fim do mês e vence no dia 10 do mês seguinte — ou seja, a compra
                  de setembro conta em outubro. Com os dias certos, o mês fica exato.
                </Text>
                <Botao tom="secundario" onPress={() => navigation.navigate('Contas')}>
                  Informar os dias da fatura
                </Botao>
              </>
            )}
          </Card>
        ) : null}

        <Card style={{ marginTop: spacing.lg }}>
          <SectionTitle>Enviar extrato</SectionTitle>
          <Text style={styles.explain}>
            Aceita <Text style={styles.strong}>OFX</Text>, <Text style={styles.strong}>CSV</Text>,{' '}
            <Text style={styles.strong}>Excel</Text> (.xlsx) e <Text style={styles.strong}>PDF</Text>.
            Se o seu banco oferecer OFX, prefira: a leitura é exata, porque cada lançamento vem
            com identificador próprio.
          </Text>
          <Text style={styles.explain}>
            Planilha em <Text style={styles.strong}>.xls</Text> (formato antigo) não abre: abra no
            Excel e salve como .xlsx.
          </Text>
          <Text style={styles.explain}>
            Nada é gravado no envio — você confere lançamento a lançamento antes de confirmar.
          </Text>
          {error ? <Text style={styles.error}>{error}</Text> : null}
          <Pressable style={styles.button} onPress={escolherArquivo}>
            <Text style={styles.buttonText}>Escolher arquivo</Text>
          </Pressable>
        </Card>

        {lotes.length > 0 ? (
          <>
            <SectionTitle>Extratos já importados</SectionTitle>
            <Card>
              <Text style={styles.explain}>
                Importou e saiu errado? Desfazer apaga os lançamentos daquele arquivo — e só
                deles. O que você lançou à mão não é tocado.
              </Text>
              {desfeito ? <Text style={styles.explain}>{desfeito}</Text> : null}
              {lotes.map((lote) => (
                <View key={lote.id} style={styles.lote}>
                  <View style={styles.loteMain}>
                    <Text style={styles.loteTitulo}>{lote.rotulo}</Text>
                    <Text style={styles.hint}>
                      {lote.rows_imported}{' '}
                      {lote.rows_imported === 1 ? 'lançamento' : 'lançamentos'}
                    </Text>
                  </View>
                  <Pressable
                    onPress={() =>
                      confirmandoDesfazer === lote.id
                        ? void desfazer(lote.id)
                        : setConfirmandoDesfazer(lote.id)
                    }
                    accessibilityRole="button"
                    disabled={desfazendo === lote.id}
                    style={[
                      styles.desfazer,
                      confirmandoDesfazer === lote.id && styles.desfazerArmado,
                    ]}
                  >
                    <Text
                      style={[
                        styles.desfazerTexto,
                        confirmandoDesfazer === lote.id && styles.desfazerTextoArmado,
                      ]}
                    >
                      {desfazendo === lote.id
                        ? 'apagando…'
                        : confirmandoDesfazer === lote.id
                          ? `apagar ${lote.rows_imported}?`
                          : 'desfazer'}
                    </Text>
                  </Pressable>
                </View>
              ))}
            </Card>
          </>
        ) : null}

        {(accounts ?? []).length > 0 ? (
          <Botao tom="secundario" onPress={() => navigation.navigate('Contas')}>
            Cadastrar outra conta
          </Botao>
        ) : null}
      </ScrollView>
    );
  }

  return (
    <View style={styles.screen}>
      <ScrollView contentContainerStyle={styles.content}>
        {/* O rótulo, e não o nome do arquivo: extrato de banco traz o banco e o
            número da conta no próprio nome, e isso não vai para a tela. */}
        <Text style={styles.filename}>{batch.rotulo}</Text>
        <Text style={styles.hint}>
          {batch.file_format} · {batch.rows_detected} lançamentos
          {batch.period_start
            ? ` · ${dayLabel(batch.period_start)} a ${dayLabel(batch.period_end ?? batch.period_start)}`
            : ''}
        </Text>

        {batch.warnings.map((aviso) => (
          <View key={aviso} style={styles.warning}>
            <Text style={styles.warningText}>{aviso}</Text>
          </View>
        ))}

        <Pressable
          onPress={virarTudo}
          accessibilityRole="button"
          style={[styles.virarTudo, tudoVirado && styles.virarTudoOn]}
        >
          <Text style={[styles.virarTudoTexto, tudoVirado && styles.virarTudoTextoOn]}>
            {tudoVirado ? '↩︎  Desfazer a inversão' : '± Inverter o extrato inteiro'}
          </Text>
          <Text style={[styles.virarTudoHint, tudoVirado && styles.virarTudoTextoOn]}>
            {tudoVirado
              ? 'Cada linha está do lado contrário ao do arquivo. Toque para voltar.'
              : 'Troca gasto por entrada em todas as linhas. Os totais abaixo mostram como fica.'}
          </Text>
        </Pressable>

        {batch.preview.map((row) => (
          <PreviewRow
            key={row.index}
            row={row}
            checked={selected.has(row.index)}
            onToggle={() => alternar(row.index)}
            categoria={
              escolhidas[row.index]
                ? (nomePorId.get(escolhidas[row.index]) ?? 'categoria escolhida')
                : (row.suggested_category_name ?? 'sem categoria')
            }
            pendente={!escolhidas[row.index] && row.suggested_is_pending}
            trocada={Boolean(escolhidas[row.index])}
            aberto={escolhendo === row.index}
            opcoes={opcoes}
            direcao={direcoes[row.index] ?? row.direction}
            direcaoVirada={Boolean(direcoes[row.index])}
            onDirecao={(lado) => {
              setDirecoes((atual) => {
                const proximo = { ...atual };
                if (lado === row.direction) delete proximo[row.index];
                else proximo[row.index] = lado;
                return proximo;
              });
              // A categoria sugerida era do outro lado - "Salario" num gasto
              // nao quer dizer nada. Esquecer a escolha aqui faz a lista abrir
              // no lado certo, e o servidor manda para "A definir" se ninguem
              // escolher nada.
              setEscolhidas((atual) => {
                const proximo = { ...atual };
                delete proximo[row.index];
                return proximo;
              });
              setSelected((atual) => new Set(atual).add(row.index));
            }}
            onAbrir={() => setEscolhendo(escolhendo === row.index ? null : row.index)}
            onEscolher={(categoriaId) => {
              setEscolhidas((atual) => ({ ...atual, [row.index]: categoriaId }));
              setEscolhendo(null);
              // escolher categoria e dizer "esta linha entra": desmarcada, a
              // escolha nao teria efeito nenhum e o toque seria perdido
              setSelected((atual) => new Set(atual).add(row.index));
            }}
          />
        ))}
      </ScrollView>

      <View style={styles.footer}>
        <View style={styles.footerMain}>
          <Text style={styles.footerLabel}>
            {selected.size} de {batch.rows_detected} marcados
          </Text>
          <Text style={styles.footerTotals}>
            +{money(totals.entrada)} · −{money(totals.saida)}
          </Text>
          {pendentes > 0 ? (
            <Text style={styles.footerPendentes}>
              {pendentes === 1
                ? '1 vai entrar como “A definir”'
                : `${pendentes} vão entrar como “A definir”`}
            </Text>
          ) : null}
        </View>
        <Pressable
          style={[styles.button, styles.buttonCompact, selected.size === 0 && styles.buttonOff]}
          onPress={confirmar}
          disabled={selected.size === 0}
        >
          <Text style={styles.buttonText}>Confirmar</Text>
        </Pressable>
      </View>
    </View>
  );
}

type Folha = ReturnType<typeof folhas>[number];

/**
 * Uma linha da conferencia.
 *
 * O toque na linha marca e desmarca; o toque na CATEGORIA abre a escolha. Sao
 * dois alvos separados de proposito: a categoria fica num botao proprio, com
 * borda, porque um texto que vira lista ao ser tocado nao se anuncia.
 */
function PreviewRow({
  row,
  checked,
  onToggle,
  categoria,
  pendente,
  trocada,
  aberto,
  opcoes,
  direcao,
  direcaoVirada,
  onAbrir,
  onEscolher,
  onDirecao,
}: {
  row: ImportPreviewRow;
  checked: boolean;
  onToggle: () => void;
  categoria: string;
  pendente: boolean;
  trocada: boolean;
  aberto: boolean;
  opcoes: Folha[];
  direcao: 'ENTRADA' | 'SAIDA';
  direcaoVirada: boolean;
  onAbrir: () => void;
  onEscolher: (categoriaId: string) => void;
  onDirecao: (lado: 'ENTRADA' | 'SAIDA') => void;
}): React.ReactElement {
  const [busca, setBusca] = useState('');

  // mesma direcao da linha: num gasto, oferecer categoria de receita e oferecer
  // um erro
  const doLado = useMemo(
    () =>
      opcoes.filter((f) =>
        direcao === 'SAIDA'
          ? f.categoria.kind === 'DESPESA' || f.categoria.kind === 'INVESTIMENTO'
          : f.categoria.kind === 'RECEITA',
      ),
    [opcoes, direcao],
  );

  // Sem corte: a lista cortada em doze itens escondia justamente o fim da
  // árvore de entrada, onde ficam doação e reembolso. Quem não vê conclui que
  // não existe.
  const visiveis = useMemo(
    () => filtrar(doLado, busca, (f) => f.caminho),
    [doLado, busca],
  );

  return (
    <View style={styles.rowWrap}>
      <Pressable onPress={onToggle} style={styles.row}>
        <View style={[styles.checkbox, checked && styles.checkboxOn]}>
          {checked ? <Text style={styles.check}>✓</Text> : null}
        </View>
        <View style={styles.rowMain}>
          <Text style={styles.rowTitle} numberOfLines={1}>
            {row.description}
          </Text>
          <Text style={styles.rowSubtitle}>
            {dayLabel(row.booked_on)}
            {row.paid_on.slice(0, 7) !== row.booked_on.slice(0, 7)
              ? ` · conta em ${mesLabel(row.paid_on)}`
              : ''}
          </Text>
          {row.installment_total ? (
            <Text style={styles.rowSubtitle}>
              {`parcela ${row.installment_no} de ${row.installment_total}`}
              {row.valor_da_compra ? ` · compra de ${money(row.valor_da_compra)}` : ''}
              {row.parcelas_faltando > 0
                ? ` · faltam ${row.parcelas_faltando}`
                : ' · é a última'}
            </Text>
          ) : null}
          {row.duplicate_reason ? (
            <Text style={styles.duplicate}>{row.duplicate_reason}</Text>
          ) : null}
        </View>
        <MoneyValue value={row.amount} direction={direcao === 'SAIDA' ? 'out' : 'in'} />
      </Pressable>

      <Pressable
        onPress={onAbrir}
        accessibilityRole="button"
        accessibilityLabel={`Categoria: ${categoria}. Toque para trocar.`}
        style={[
          styles.categoriaBotao,
          pendente && styles.categoriaPendente,
          trocada && styles.categoriaTrocada,
        ]}
      >
        <Text
          style={[
            styles.categoriaTexto,
            pendente && styles.categoriaTextoPendente,
            trocada && styles.categoriaTextoTrocada,
          ]}
          numberOfLines={1}
        >
          {categoria}
        </Text>
        <Text style={styles.categoriaAcao}>{aberto ? 'fechar' : 'trocar'}</Text>
      </Pressable>

      {aberto ? (
        <View style={styles.escolha}>
          <Text style={styles.hint}>Esta linha é</Text>
          <View style={styles.lados}>
            {(['SAIDA', 'ENTRADA'] as const).map((lado) => (
              <Pressable
                key={lado}
                onPress={() => onDirecao(lado)}
                accessibilityRole="button"
                style={[styles.lado, direcao === lado && styles.ladoOn]}
              >
                <Text style={[styles.ladoTexto, direcao === lado && styles.ladoTextoOn]}>
                  {lado === 'SAIDA' ? 'gasto' : 'entrada'}
                </Text>
              </Pressable>
            ))}
          </View>
          {direcaoVirada ? (
            <Text style={styles.hint}>
              Virado à mão. O arquivo dizia o contrário — vale o que está marcado aqui.
            </Text>
          ) : null}
          <Field
            label=""
            value={busca}
            onChangeText={setBusca}
            placeholder="Procurar categoria…"
            autoCapitalize="none"
          />
          <ScrollView style={styles.escolhaLista} nestedScrollEnabled keyboardShouldPersistTaps="handled">
            {visiveis.map((f) => (
              <Pressable
                key={f.categoria.id}
                onPress={() => {
                  setBusca('');
                  onEscolher(f.categoria.id);
                }}
                accessibilityRole="button"
                style={styles.escolhaItem}
              >
                <Text style={styles.escolhaTexto}>{f.caminho}</Text>
              </Pressable>
            ))}
            {visiveis.length === 0 ? (
              <Text style={styles.hint}>Nenhuma categoria com esse nome.</Text>
            ) : null}
          </ScrollView>
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.md, paddingBottom: spacing.xl, ...layout.coluna },
  center: {
    flex: 1,
    backgroundColor: colors.background,
    alignItems: 'center',
    justifyContent: 'center',
    padding: spacing.lg,
  },
  explain: { ...typography.caption, color: colors.textMuted, marginBottom: spacing.sm },
  virarTudo: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    padding: spacing.md,
    marginBottom: spacing.sm,
  },
  virarTudoOn: { borderColor: colors.red, backgroundColor: colors.red },
  virarTudoTexto: { ...typography.body, color: colors.text, fontWeight: '700' },
  virarTudoHint: { ...typography.caption, color: colors.textMuted, marginTop: 4 },
  virarTudoTextoOn: { color: colors.white },
  lados: { flexDirection: 'row', gap: spacing.sm, marginBottom: spacing.sm },
  lote: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  loteMain: { flex: 1 },
  loteTitulo: { ...typography.body, color: colors.text },
  desfazer: {
    paddingVertical: 6,
    paddingHorizontal: spacing.md,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.border,
  },
  desfazerArmado: { borderColor: colors.red, backgroundColor: colors.red },
  desfazerTexto: { ...typography.caption, color: colors.textMuted },
  desfazerTextoArmado: { color: colors.white, fontWeight: '700' },
  lado: {
    paddingVertical: 6,
    paddingHorizontal: spacing.md,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.border,
  },
  ladoOn: { backgroundColor: colors.red, borderColor: colors.red },
  ladoTexto: { ...typography.caption, color: colors.textMuted },
  ladoTextoOn: { color: colors.white, fontWeight: '700' },
  checklistTitle: { ...typography.body, color: colors.text, marginBottom: spacing.sm },
  checkline: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    paddingVertical: 5,
  },
  checkName: { ...typography.caption, color: colors.text, flex: 1 },
  checkDoneName: { color: colors.textMuted },
  checkDone: { ...typography.caption, color: colors.textMuted },
  checkPending: { ...typography.caption, color: colors.textFaint },
  checkLate: { ...typography.caption, color: colors.red },
  strong: { color: colors.text },
  hint: { ...typography.caption, color: colors.textMuted, marginTop: spacing.sm },
  error: { ...typography.caption, color: colors.red, marginBottom: spacing.sm },
  accounts: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  accountChip: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radius.pill,
    backgroundColor: colors.surfaceAlt,
  },
  accountChipActive: { backgroundColor: colors.red },
  accountText: { ...typography.caption, color: colors.textMuted },
  filename: { ...typography.title, color: colors.text },
  warning: {
    backgroundColor: colors.redSoft,
    borderRadius: radius.md,
    padding: spacing.md,
    marginTop: spacing.md,
  },
  warningText: { ...typography.caption, color: colors.red },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingTop: spacing.md,
    paddingBottom: spacing.sm,
    gap: spacing.sm,
  },
  checkbox: {
    width: 22,
    height: 22,
    borderRadius: 6,
    borderWidth: 1.5,
    borderColor: colors.border,
    alignItems: 'center',
    justifyContent: 'center',
  },
  checkboxOn: { backgroundColor: colors.red, borderColor: colors.red },
  check: { color: colors.white, fontSize: 13, fontWeight: '700' },
  rowWrap: { borderBottomWidth: 1, borderBottomColor: colors.border },
  rowMain: { flex: 1 },
  categoriaBotao: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.sm,
    marginLeft: 30,
    marginBottom: spacing.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surfaceAlt,
  },
  categoriaPendente: { borderColor: colors.redDark, backgroundColor: colors.redSoft },
  categoriaTrocada: { borderColor: colors.white },
  categoriaTexto: { ...typography.caption, color: colors.textMuted, flex: 1 },
  categoriaTextoPendente: { color: colors.red, fontWeight: '700' },
  categoriaTextoTrocada: { color: colors.text },
  categoriaAcao: { ...typography.caption, color: colors.textFaint },
  escolha: { marginLeft: 30, marginBottom: spacing.md },
  escolhaLista: { maxHeight: 220 },
  escolhaItem: { paddingVertical: 11, borderBottomWidth: 1, borderBottomColor: colors.border },
  escolhaTexto: { ...typography.caption, color: colors.text },
  rowTitle: { ...typography.body, color: colors.text },
  rowSubtitle: { ...typography.caption, color: colors.textMuted, marginTop: 2 },
  duplicate: { ...typography.caption, color: colors.red, marginTop: 2 },
  footer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    backgroundColor: colors.surface,
    ...layout.coluna,
  },
  footerMain: { flex: 1 },
  footerLabel: { ...typography.caption, color: colors.textMuted },
  footerPendentes: { ...typography.caption, color: colors.red, marginTop: 2 },
  footerTotals: { ...typography.body, color: colors.text, marginTop: 2 },
  button: {
    backgroundColor: colors.red,
    borderRadius: radius.md,
    padding: spacing.md,
    alignItems: 'center',
    marginTop: spacing.md,
  },
  buttonCompact: { marginTop: 0, paddingHorizontal: spacing.lg },
  buttonOff: { backgroundColor: colors.surfaceAlt },
  buttonText: { ...typography.body, color: colors.white },
  done: { ...typography.display, color: colors.white, fontSize: 56 },
  doneLabel: { ...typography.body, color: colors.textMuted },
});
