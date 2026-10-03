/**
 * Lançar à mão - a tela do gasto pago em dinheiro.
 *
 * Nenhum extrato traz o que foi pago em cédula, então ou entra aqui ou some da
 * contabilidade da casa. Como é o lançamento que mais se repete no dia, a tela é
 * desenhada para o segundo lançamento ser mais rápido que o primeiro: depois de
 * gravar, só o valor e a descrição são limpos - conta, data, categoria e
 * responsável ficam como estavam.
 *
 * Cada lançamento leva uma `client_key` criada aqui. Se a resposta se perder no
 * caminho e o aplicativo tentar de novo, o servidor devolve o que já gravou em
 * vez de cobrar o gasto duas vezes.
 */

import React, { useMemo, useRef, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import {
  useAccounts,
  useCategories,
  useCreateAccount,
  useCreateDonor,
  useDonors,
  useLancar,
  useMe,
  useMembers,
} from '@/api/queries';
import type { Category } from '@/api/types';
import { Botao, Card, Chip, Field, Mensagem, Screen, SectionTitle } from '@/components/ui';
import { colors, radius, spacing, typography } from '@/theme';
import { money } from '@/theme/format';

type Direcao = 'SAIDA' | 'ENTRADA';

interface Folha {
  categoria: Category;
  caminho: string;
  /**
   * Nome do antepassado que exige explicação, se houver.
   *
   * A exigência é herdada no servidor: "Únicos" marcada vale para "Únicos ›
   * Viagens", e a filha chega aqui com a marca apagada. Sem descer a herança na
   * hora de achatar a árvore, o campo de explicação não apareceria e o
   * lançamento morreria num 422 que o usuário não teria como resolver na tela.
   */
  exigeNota: string | null;
  /**
   * A categoria é doação recebida: entra na conta, mas não é renda da família.
   *
   * Herdada como a exigência de explicação: uma subcategoria criada à mão dentro
   * de "Doações recebidas" nasce sem a marca, e sem descer a herança o
   * lançamento viraria renda em silêncio - que é justamente o erro que o
   * controle de doação existe para evitar.
   */
  ehDoacao: boolean;
}

/** Achata a árvore guardando o caminho legível: "Casa › Mercado". */
export function folhas(
  categorias: Category[],
  prefixo: string[] = [],
  notaHerdada: string | null = null,
  doacaoHerdada = false,
): Folha[] {
  return categorias.flatMap((categoria) => {
    const caminho = [...prefixo, categoria.name];
    const exigeNota = notaHerdada ?? (categoria.requires_note ? categoria.name : null);
    const ehDoacao =
      doacaoHerdada || (categoria.kind === 'RECEITA' && categoria.counts_as_income === false);
    const filhas = folhas(categoria.children, caminho, exigeNota, ehDoacao);
    // o nó só é escolhível quando é ponta da árvore: o pai de "Mercado" e
    // "Padaria" é "Alimentação", e lançar em "Alimentação" solta é o que a gente
    // quer evitar
    return filhas.length > 0
      ? filhas
      : [{ categoria, caminho: caminho.join(' › '), exigeNota, ehDoacao }];
  });
}

/** Os grupos de despesa, para dizer PARA QUE a doação foi dada. */
export function gruposDeDespesa(categorias: Category[]): Category[] {
  const despesas = categorias.filter((c) => c.kind === 'DESPESA');
  // um nível abaixo da raiz: "Educação", não "Educação › Escola". A doação é dada
  // para a escola das meninas, e o abatimento vale para a subárvore inteira.
  return despesas.flatMap((raiz) => (raiz.children.length > 0 ? raiz.children : [raiz]));
}

function hojeISO(): string {
  const agora = new Date();
  const mes = String(agora.getMonth() + 1).padStart(2, '0');
  const dia = String(agora.getDate()).padStart(2, '0');
  return `${agora.getFullYear()}-${mes}-${dia}`;
}

function somaDias(iso: string, dias: number): string {
  const d = new Date(`${iso}T12:00:00`);
  d.setDate(d.getDate() + dias);
  return d.toISOString().slice(0, 10);
}

function paraBR(iso: string): string {
  const [a, m, d] = iso.split('-');
  return `${d}/${m}/${a}`;
}

/** Lê "05/08/2026", "5/8/26" e "05/08". Devolve null se não der para entender. */
function deBR(texto: string): string | null {
  const partes = texto.trim().split(/[/.\-\s]+/).filter(Boolean);
  if (partes.length < 2) return null;
  const dia = Number(partes[0]);
  const mes = Number(partes[1]);
  let ano = partes.length > 2 ? Number(partes[2]) : new Date().getFullYear();
  if (ano < 100) ano += 2000;
  if (!dia || !mes || mes > 12 || dia > 31 || ano < 2000 || ano > 2100) return null;
  const d = new Date(ano, mes - 1, dia);
  if (d.getDate() !== dia || d.getMonth() !== mes - 1) return null;
  return `${ano}-${String(mes).padStart(2, '0')}-${String(dia).padStart(2, '0')}`;
}

/** Aceita "35", "35,90" e "1.250,00". */
function paraValor(texto: string): number | null {
  const limpo = texto.trim().replace(/[^\d.,]/g, '').replace(/\./g, '').replace(',', '.');
  if (!limpo) return null;
  const n = Number(limpo);
  return Number.isFinite(n) && n > 0 ? n : null;
}

function novaChave(): string {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

export function EntryScreen(): React.ReactElement {
  const { data: accounts } = useAccounts();
  const { data: members } = useMembers();
  const { data: categories } = useCategories();
  const { data: eu } = useMe();
  const lancar = useLancar();
  const criarConta = useCreateAccount();
  const { data: doadores } = useDonors();
  const criarDoador = useCreateDonor();

  const [direcao, setDirecao] = useState<Direcao>('SAIDA');
  const [valor, setValor] = useState('');
  const [descricao, setDescricao] = useState('');
  const [dataISO, setDataISO] = useState(hojeISO);
  const [dataTexto, setDataTexto] = useState(() => paraBR(hojeISO()));
  const [contaId, setContaId] = useState<string | null>(null);
  const [responsavel, setResponsavel] = useState<string | null>(null);
  const [categoriaId, setCategoriaId] = useState<string | null>(null);
  const [buscaCategoria, setBuscaCategoria] = useState('');
  const [nota, setNota] = useState('');
  const [doadorId, setDoadorId] = useState<string | null>(null);
  const [destinoId, setDestinoId] = useState<string | null>(null);
  const [novoDoador, setNovoDoador] = useState('');
  const [pedindoDoador, setPedindoDoador] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [feito, setFeito] = useState<string | null>(null);

  // A chave acompanha o rascunho, não a tentativa: errar a rede e tocar em
  // "Lançar" de novo tem de continuar sendo o MESMO lançamento.
  const chave = useRef<string>(novaChave());

  const carteira = useMemo(
    () => (accounts ?? []).find((c) => c.type === 'DINHEIRO' && !c.is_business) ?? null,
    [accounts],
  );
  // Dinheiro primeiro: é o motivo de a tela existir.
  const contasOrdenadas = useMemo(
    () =>
      [...(accounts ?? [])].sort((a, b) => {
        const peso = (t: string) => (t === 'DINHEIRO' ? 0 : 1);
        return peso(a.type) - peso(b.type) || a.name.localeCompare(b.name, 'pt-BR');
      }),
    [accounts],
  );

  const contaEscolhida = contaId ?? carteira?.id ?? contasOrdenadas[0]?.id ?? null;
  const quemEscolhido = responsavel ?? eu?.id ?? null;

  const todasFolhas = useMemo(() => folhas(categories ?? []), [categories]);
  const folhasDoLado = useMemo(
    () =>
      todasFolhas.filter((f) =>
        direcao === 'SAIDA'
          ? f.categoria.kind === 'DESPESA' || f.categoria.kind === 'INVESTIMENTO'
          : f.categoria.kind === 'RECEITA',
      ),
    [todasFolhas, direcao],
  );
  const folhasVisiveis = useMemo(() => {
    const termo = buscaCategoria
      .trim()
      .toLowerCase()
      .normalize('NFD')
      .replace(/[̀-ͯ]/g, '');
    if (!termo) return folhasDoLado.slice(0, 12);
    return folhasDoLado
      .filter((f) =>
        f.caminho
          .toLowerCase()
          .normalize('NFD')
          .replace(/[̀-ͯ]/g, '')
          .includes(termo),
      )
      .slice(0, 30);
  }, [folhasDoLado, buscaCategoria]);

  const categoriaEscolhida = useMemo(
    () => folhasDoLado.find((f) => f.categoria.id === categoriaId) ?? null,
    [folhasDoLado, categoriaId],
  );
  const notaExigidaPor = categoriaEscolhida?.exigeNota ?? null;
  const exigeNota = notaExigidaPor !== null;
  const ehDoacao = direcao === 'ENTRADA' && (categoriaEscolhida?.ehDoacao ?? false);
  const destinos = useMemo(() => gruposDeDespesa(categories ?? []), [categories]);

  const quantia = paraValor(valor);
  const podeGravar =
    quantia !== null &&
    Boolean(contaEscolhida) &&
    Boolean(quemEscolhido) &&
    (!exigeNota || nota.trim().length > 0) &&
    !lancar.isPending;

  function escolherData(iso: string): void {
    setDataISO(iso);
    setDataTexto(paraBR(iso));
  }

  function digitarData(texto: string): void {
    setDataTexto(texto);
    const iso = deBR(texto);
    if (iso) setDataISO(iso);
  }

  async function criarCarteira(): Promise<void> {
    setErro(null);
    try {
      const conta = await criarConta.mutateAsync({ name: 'Dinheiro', type: 'DINHEIRO' });
      setContaId(conta.id);
    } catch (err) {
      setErro(err instanceof Error ? err.message : 'Nao consegui criar a carteira.');
    }
  }

  async function gravar(): Promise<void> {
    if (!podeGravar || quantia === null || !contaEscolhida || !quemEscolhido) return;
    setErro(null);
    setFeito(null);
    try {
      const resultado = await lancar.mutateAsync({
        client_key: chave.current,
        account_id: contaEscolhida,
        owner_member_id: quemEscolhido,
        booked_on: dataISO,
        amount: quantia,
        direction: direcao,
        // sem descrição, o nome da categoria já diz mais que um campo vazio
        description: descricao.trim() || categoriaEscolhida?.categoria.name || 'Lançamento manual',
        ...(categoriaId ? { category_id: categoriaId } : {}),
        ...(nota.trim() ? { notes: nota.trim() } : {}),
        // só vão quando a categoria é doação: num salário estes campos não
        // querem dizer nada, e preenchê-los mentiria no relatório do ano
        ...(ehDoacao && doadorId ? { donor_id: doadorId } : {}),
        ...(ehDoacao && destinoId ? { donation_for_category_id: destinoId } : {}),
      });
      const oQueFoi = ehDoacao
        ? `Doação de ${money(quantia)} em ${paraBR(dataISO)}`
        : `${direcao === 'SAIDA' ? 'Gasto' : 'Entrada'} de ${money(quantia)} em ${paraBR(dataISO)}`;
      setFeito(
        resultado.enfileirado
          ? // Sem servidor, o lançamento fica no aparelho. Dizer "gravado" aqui
            // seria mentira pequena com consequência grande: ele ainda não está
            // nas contas do mês, e quem não sabe disso não procura depois.
            `${oQueFoi}, guardado aqui no celular. Sobe sozinho quando o PC voltar.`
          : ehDoacao
            ? `${oQueFoi}. Não entra na renda do mês.`
            : `${oQueFoi}.`,
      );
      // só o que muda de um lançamento para o outro é limpo
      setValor('');
      setDescricao('');
      setNota('');
      chave.current = novaChave();
    } catch (err) {
      setErro(err instanceof Error ? err.message : 'Nao consegui gravar o lançamento.');
    }
  }

  if ((accounts ?? []).length === 0) {
    return (
      <Screen>
        <Card>
          <SectionTitle>Primeiro, uma conta</SectionTitle>
          <Text style={styles.explica}>
            Todo lançamento sai de algum lugar. Para gasto em dinheiro basta uma carteira — crio
            uma agora, chamada “Dinheiro”, e você já começa a lançar.
          </Text>
          {erro ? <Mensagem tom="erro">{erro}</Mensagem> : null}
          <Botao onPress={criarCarteira} disabled={criarConta.isPending}>
            {criarConta.isPending ? 'Criando…' : 'Criar carteira “Dinheiro”'}
          </Botao>
          <Text style={styles.explica}>
            Para cadastrar banco ou cartão, use “Contas” na aba Mais.
          </Text>
        </Card>
      </Screen>
    );
  }

  return (
    <Screen>
      {feito ? <Mensagem tom="ok">{`${feito} Pode lançar o próximo.`}</Mensagem> : null}
      {erro ? <Mensagem tom="erro">{erro}</Mensagem> : null}

      <View style={styles.direcao}>
        <Chip active={direcao === 'SAIDA'} onPress={() => setDirecao('SAIDA')}>
          Gasto
        </Chip>
        <Chip active={direcao === 'ENTRADA'} onPress={() => setDirecao('ENTRADA')}>
          Entrada
        </Chip>
      </View>

      <Card>
        <Text style={styles.rotuloValor}>Quanto</Text>
        <View style={styles.valorLinha}>
          <Text style={styles.moeda}>R$</Text>
          <Field
            label=""
            value={valor}
            onChangeText={setValor}
            placeholder="0,00"
            keyboardType="decimal-pad"
            autoFocus
          />
        </View>

        <Field
          label="O que foi"
          value={descricao}
          onChangeText={setDescricao}
          placeholder="Padaria, estacionamento, feira…"
          opcional
        />

        <Text style={styles.rotulo}>Quando</Text>
        <View style={styles.opcoes}>
          <Chip active={dataISO === hojeISO()} onPress={() => escolherData(hojeISO())}>
            Hoje
          </Chip>
          <Chip
            active={dataISO === somaDias(hojeISO(), -1)}
            onPress={() => escolherData(somaDias(hojeISO(), -1))}
          >
            Ontem
          </Chip>
          <Chip
            active={dataISO === somaDias(hojeISO(), -2)}
            onPress={() => escolherData(somaDias(hojeISO(), -2))}
          >
            Anteontem
          </Chip>
        </View>
        <Field
          label="Ou outra data"
          value={dataTexto}
          onChangeText={digitarData}
          placeholder="dd/mm/aaaa"
          opcional
          ajuda={deBR(dataTexto) ? undefined : 'Não entendi essa data — vou usar a escolhida acima.'}
        />
      </Card>

      <SectionTitle>De onde saiu</SectionTitle>
      <Card>
        <View style={styles.opcoes}>
          {contasOrdenadas.map((conta) => (
            <Chip
              key={conta.id}
              active={conta.id === contaEscolhida}
              onPress={() => setContaId(conta.id)}
            >
              {conta.type === 'DINHEIRO' ? `${conta.name} (carteira)` : conta.name}
            </Chip>
          ))}
          {!carteira ? (
            <Chip active={false} onPress={criarCarteira}>
              {criarConta.isPending ? '＋ criando…' : '＋ Dinheiro'}
            </Chip>
          ) : null}
        </View>

        <Text style={styles.rotulo}>De quem foi</Text>
        <View style={styles.opcoes}>
          {(members ?? []).map((membro) => (
            <Chip
              key={membro.id}
              active={membro.id === quemEscolhido}
              onPress={() => setResponsavel(membro.id)}
            >
              {membro.name}
            </Chip>
          ))}
        </View>
      </Card>

      <SectionTitle>Categoria</SectionTitle>
      <Card>
        {categoriaEscolhida ? (
          <Pressable
            onPress={() => setCategoriaId(null)}
            accessibilityRole="button"
            style={styles.escolhida}
          >
            <Text style={styles.escolhidaTexto}>{categoriaEscolhida.caminho}</Text>
            <Text style={styles.escolhidaTrocar}>trocar</Text>
          </Pressable>
        ) : (
          <>
            <Field
              label=""
              value={buscaCategoria}
              onChangeText={setBuscaCategoria}
              placeholder="Procurar categoria…"
              autoCapitalize="none"
            />
            <ScrollView style={styles.lista} nestedScrollEnabled keyboardShouldPersistTaps="handled">
              {folhasVisiveis.map((f) => (
                <Pressable
                  key={f.categoria.id}
                  onPress={() => {
                    setCategoriaId(f.categoria.id);
                    setBuscaCategoria('');
                  }}
                  accessibilityRole="button"
                  style={styles.itemLista}
                >
                  <Text style={styles.itemTexto}>{f.caminho}</Text>
                </Pressable>
              ))}
              {folhasVisiveis.length === 0 ? (
                <Text style={styles.explica}>Nenhuma categoria com esse nome.</Text>
              ) : null}
            </ScrollView>
            <Text style={styles.explica}>
              Pode deixar em branco: o sistema tenta adivinhar pela descrição e, quando não sabe,
              guarda em “A definir” — que aparece no Resumo cobrando, até você dizer o que foi.
            </Text>
          </>
        )}

        {exigeNota ? (
          <Field
            label={`Explicação (“${notaExigidaPor}” exige)`}
            value={nota}
            onChangeText={setNota}
            placeholder="O que foi esse gasto"
            multiline
            ajuda="Daqui a seis meses ninguém lembra o que foi um gasto avulso de R$ 3.400 — por isso esta categoria pede uma linha."
          />
        ) : null}
      </Card>

      {ehDoacao ? (
        <>
          <SectionTitle>Doação</SectionTitle>
          <Card>
            <Text style={styles.explica}>
              Este dinheiro entra na conta, mas não conta como renda da família — e o gasto que
              ele cobrir sai do consumo da casa. É a diferença entre a casa gastar e a casa
              receber para gastar.
            </Text>

            <Text style={styles.rotulo}>Quem depositou</Text>
            <View style={styles.opcoes}>
              {(doadores ?? []).map((doador) => (
                <Chip
                  key={doador.id}
                  active={doador.id === doadorId}
                  onPress={() => setDoadorId(doador.id === doadorId ? null : doador.id)}
                >
                  {doador.name}
                </Chip>
              ))}
              <Chip active={pedindoDoador} onPress={() => setPedindoDoador(!pedindoDoador)}>
                ＋ Novo
              </Chip>
            </View>
            {pedindoDoador ? (
              <>
                <Field
                  label="Nome de quem doa"
                  value={novoDoador}
                  onChangeText={setNovoDoador}
                  placeholder="Vera, José…"
                />
                <Botao
                  tom="secundario"
                  disabled={!novoDoador.trim() || criarDoador.isPending}
                  onPress={async () => {
                    setErro(null);
                    try {
                      const criado = await criarDoador.mutateAsync({ name: novoDoador.trim() });
                      setDoadorId(criado.id);
                      setNovoDoador('');
                      setPedindoDoador(false);
                    } catch (err) {
                      setErro(err instanceof Error ? err.message : 'Nao consegui cadastrar.');
                    }
                  }}
                >
                  {criarDoador.isPending ? 'Cadastrando…' : 'Cadastrar quem doa'}
                </Botao>
              </>
            ) : null}
            {!doadorId ? (
              <Text style={styles.explica}>
                Sem dizer quem depositou, a doação entra no total do ano, mas fica sem dono — e o
                limite de isenção do ITCMD é contado por doador.
              </Text>
            ) : null}

            <Text style={styles.rotulo}>Para que foi dada</Text>
            <View style={styles.opcoes}>
              {destinos.map((destino) => (
                <Chip
                  key={destino.id}
                  active={destino.id === destinoId}
                  onPress={() => setDestinoId(destino.id === destinoId ? null : destino.id)}
                >
                  {destino.name}
                </Chip>
              ))}
            </View>
            <Text style={styles.explica}>
              {destinoId
                ? 'O gasto desta categoria sai do consumo da casa, até o valor doado no mês.'
                : 'Opcional. Sem destino, a doação só deixa de ser renda — o gasto que ela pagou continua aparecendo como gasto da casa.'}
            </Text>
          </Card>
        </>
      ) : null}

      <Botao onPress={gravar} disabled={!podeGravar}>
        {lancar.isPending
          ? 'Gravando…'
          : quantia !== null
            ? `Lançar ${money(quantia)}`
            : 'Lançar'}
      </Botao>
    </Screen>
  );
}

const styles = StyleSheet.create({
  explica: { ...typography.caption, color: colors.textMuted, marginTop: spacing.sm },
  direcao: { flexDirection: 'row', gap: spacing.sm, marginBottom: spacing.sm },
  rotuloValor: { ...typography.caption, color: colors.textMuted, marginBottom: 6 },
  valorLinha: { flexDirection: 'row', alignItems: 'flex-start', gap: spacing.sm },
  moeda: { ...typography.title, color: colors.textFaint, marginTop: 12 },
  rotulo: { ...typography.caption, color: colors.textMuted, marginBottom: 6 },
  opcoes: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm, marginBottom: spacing.md },
  lista: { maxHeight: 260 },
  itemLista: {
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  itemTexto: { ...typography.body, color: colors.text },
  escolhida: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: colors.surfaceAlt,
    borderRadius: radius.md,
    padding: spacing.md,
  },
  escolhidaTexto: { ...typography.body, color: colors.text, flex: 1 },
  escolhidaTrocar: { ...typography.caption, color: colors.red, fontWeight: '700' },
});
