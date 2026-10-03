/** Hooks de dados. Uma chave por recurso, para o cache invalidar certo. */

import { useEffect, useState } from 'react';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { ApiError, api } from './client';
import { assinarFila, descartar, enfileirar, listarFila, subirFila } from './fila';
import type { ItemDaFila, ResultadoDaSubida } from './fila';
import type {
  Account,
  AccountCreate,
  BudgetCapRow,
  CardSummary,
  CategoryAnalysis,
  CategoryOverview,
  Evolucao,
  BenchmarkEvolution,
  CardPrograms,
  Forecast,
  Holding,
  HoldingKind,
  Member,
  NetWorth,
  StatementChecklist,
  Scope as ScopeType,
  SpendByCategory,
  Category,
  DashboardData,
  DonationsSummary,
  Donor,
  Goal,
  Portfolio,
  Scope,
  TaxAssessment,
  Transaction,
  TransactionCreate,
} from './types';

export const queryKeys = {
  me: ['me'] as const,
  dashboard: (month: string, scope: Scope) => ['dashboard', month, scope] as const,
  transactions: (params: object) => ['transactions', params] as const,
  categories: ['categories'] as const,
  goals: ['goals'] as const,
  portfolio: ['portfolio'] as const,
  evolution: (benchmark: string) => ['evolution', benchmark] as const,
  tax: (year: number) => ['tax', year] as const,
  accounts: ['accounts'] as const,
  imports: ['imports'] as const,
  members: ['members'] as const,
  byCategory: (params: object) => ['by-category', params] as const,
  forecast: (months: number, scope: ScopeType) => ['forecast', months, scope] as const,
  netWorth: ['net-worth'] as const,
  holdings: (kind?: HoldingKind) => ['holdings', kind ?? 'todos'] as const,
  cardPrograms: ['card-programs'] as const,
  categoryOverview: (month: string) => ['category-overview', month] as const,
  categoryAnalysis: (id: string, month: string) => ['category-analysis', id, month] as const,
  budgetCaps: (month: string) => ['budget-caps', month] as const,
  cardSummary: (month: string) => ['card-summary', month] as const,
  donors: ['donors'] as const,
  doacoes: (year: number) => ['doacoes', year] as const,
  evolucao: (month: string, scope: string) => ['evolucao', month, scope] as const,
  checklist: (month: string) => ['statement-checklist', month] as const,
};

/** Patrimônio total: contas, carteira, bens e o que se deve. */
export function useNetWorth() {
  return useQuery({
    queryKey: queryKeys.netWorth,
    queryFn: () => api.get<NetWorth>('/net-worth'),
  });
}

export function useHoldings(kind?: HoldingKind) {
  return useQuery({
    queryKey: queryKeys.holdings(kind),
    queryFn: () => api.get<Holding[]>('/holdings', kind ? { kind } : undefined),
  });
}

export function useCardPrograms() {
  return useQuery({
    queryKey: queryKeys.cardPrograms,
    queryFn: () => api.get<CardPrograms>('/card-programs'),
  });
}

/** De quais bancos o extrato do mês já chegou. */
export function useStatementChecklist(month: string) {
  return useQuery({
    queryKey: queryKeys.checklist(month),
    queryFn: () => api.get<StatementChecklist>('/statements/checklist', { month }),
  });
}

/** Quem está logado. Serve de padrão nos seletores de titular e responsável. */
export function useMe() {
  return useQuery({
    queryKey: queryKeys.me,
    queryFn: () => api.get<{ id: string; full_name: string; nickname: string | null }>('/auth/me'),
    staleTime: 1000 * 60 * 60,
  });
}

export function useMembers() {
  return useQuery({
    queryKey: queryKeys.members,
    queryFn: () => api.get<Member[]>('/auth/members'),
    staleTime: 1000 * 60 * 30,
  });
}

/** Gastos somados por categoria. `depth` escolhe o corte da árvore. */
export function useSpendByCategory(params: {
  start: string;
  end: string;
  scope: Scope;
  depth: number;
  member_id?: string;
}) {
  return useQuery({
    queryKey: queryKeys.byCategory(params),
    queryFn: () => api.get<SpendByCategory>('/transactions/by-category', params),
  });
}

/** Evolutivo dos próximos meses. */
export function useForecast(months: number, scope: Scope) {
  return useQuery({
    queryKey: queryKeys.forecast(months, scope),
    queryFn: () => api.get<Forecast>('/forecast', { months, scope }),
  });
}

export function useAccounts() {
  return useQuery({
    queryKey: queryKeys.accounts,
    queryFn: () => api.get<Account[]>('/accounts'),
  });
}

/**
 * Cadastrar conta. Invalida o que depende da lista: a tela de importar escolhe
 * a conta de destino daqui, e o painel soma saldos.
 */
export function useCreateAccount() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: AccountCreate) => api.post<Account>('/accounts', input),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: queryKeys.accounts });
      client.invalidateQueries({ queryKey: ['dashboard'] });
      client.invalidateQueries({ queryKey: queryKeys.netWorth });
      client.invalidateQueries({ queryKey: ['statement-checklist'] });
    },
  });
}

/** O gasto acumulado dia a dia, com o mês passado, o ano passado e a meta. */
export function useEvolucao(month: string, scope: Scope) {
  return useQuery({
    queryKey: queryKeys.evolucao(month, scope),
    queryFn: () => api.get<Evolucao>('/dashboard/evolucao', { month, scope }),
  });
}

export function useDashboard(month: string, scope: Scope) {
  return useQuery({
    queryKey: queryKeys.dashboard(month, scope),
    queryFn: () => api.get<DashboardData>('/dashboard', { month, scope }),
  });
}

export function useCategories() {
  return useQuery({
    queryKey: queryKeys.categories,
    queryFn: () => api.get<Category[]>('/categories'),
    staleTime: 1000 * 60 * 30,
  });
}

export function useTransactions(params: {
  start: string;
  end: string;
  scope: Scope;
  category_id?: string;
  search?: string;
  only_uncategorized?: boolean;
}) {
  return useQuery({
    queryKey: queryKeys.transactions(params),
    queryFn: () => api.get<Transaction[]>('/transactions', params),
  });
}

/**
 * Editar um lançamento. Mudar a categoria alimenta o aprendizado de regras;
 * mudar o responsável só reatribui o gasto, sem criar regra nenhuma.
 */
export function useRecategorize() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      id: string;
      category_id?: string;
      owner_member_id?: string;
      notes?: string;
      learn_rule?: boolean;
    }) =>
      api.patch<Transaction>(`/transactions/${input.id}`, {
        ...(input.category_id ? { category_id: input.category_id } : {}),
        ...(input.owner_member_id ? { owner_member_id: input.owner_member_id } : {}),
        ...(input.notes ? { notes: input.notes } : {}),
        learn_rule: input.learn_rule ?? true,
      }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['transactions'] });
      client.invalidateQueries({ queryKey: ['by-category'] });
      client.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });
}

export function useGoals() {
  return useQuery({ queryKey: queryKeys.goals, queryFn: () => api.get<Goal[]>('/goals') });
}

export function useGoalSimulation(goalId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: { monthly_contribution?: number; expected_annual_rate?: number }) =>
      api.post(`/goals/${goalId}/simulate`, input),
    onSuccess: () => client.invalidateQueries({ queryKey: queryKeys.goals }),
  });
}

export function usePortfolio() {
  return useQuery({
    queryKey: queryKeys.portfolio,
    queryFn: () => api.get<Portfolio>('/investments/portfolio'),
  });
}

export function useEvolution(start: string, end: string, benchmark = 'CDI') {
  return useQuery({
    queryKey: queryKeys.evolution(benchmark),
    queryFn: () =>
      api.get<BenchmarkEvolution>('/investments/evolution', { start, end, benchmark }),
  });
}

export function useTaxAssessment(year: number) {
  return useQuery({
    queryKey: queryKeys.tax(year),
    queryFn: () => api.get<TaxAssessment>(`/tax/${year}`),
  });
}

export function useDeductionSimulation(year: number) {
  return useMutation({
    mutationFn: (input: { deduction_type: string; amount: number; member_id?: string }) =>
      api.post(`/tax/${year}/simulate-deduction`, input),
  });
}

// ------------------------------------------------- categorias e metas ---

/** Tudo o que a tela de categorias mostra, numa chamada. */
export function useCategoryOverview(month: string) {
  return useQuery({
    queryKey: queryKeys.categoryOverview(month),
    queryFn: () => api.get<CategoryOverview>('/categories/resumo', { month, depth: 2 }),
  });
}

/**
 * A leitura de uma categoria no tempo. Serve para qualquer nível: a mesma rota
 * responde por "Transporte" e por "Gasolina".
 */
export function useCategoryAnalysis(categoryId: string | null, month: string) {
  return useQuery({
    queryKey: queryKeys.categoryAnalysis(categoryId ?? '', month),
    queryFn: () => api.get<CategoryAnalysis>(`/categories/${categoryId}/analise`, { month }),
    enabled: Boolean(categoryId),
  });
}

export function useBudgetCaps(month: string) {
  return useQuery({
    queryKey: queryKeys.budgetCaps(month),
    queryFn: () => api.get<BudgetCapRow[]>('/budget-caps', { month }),
  });
}

/** Tudo o que mexe em categoria ou meta invalida as mesmas telas. */
function invalidarCategorias(client: ReturnType<typeof useQueryClient>): void {
  client.invalidateQueries({ queryKey: ['category-overview'] });
  client.invalidateQueries({ queryKey: ['category-analysis'] });
  client.invalidateQueries({ queryKey: ['budget-caps'] });
  client.invalidateQueries({ queryKey: queryKeys.categories });
  client.invalidateQueries({ queryKey: ['dashboard'] });
}

export function useCreateCategory() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      name: string;
      parent_id?: string;
      kind?: 'DESPESA' | 'RECEITA';
      expense_nature?: string;
    }) => api.post<Category>('/categories', { kind: 'DESPESA', ...input }),
    onSuccess: () => invalidarCategorias(client),
  });
}

export function useUpdateCategory() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: { id: string; name?: string; icon?: string }) =>
      api.patch<Category>(`/categories/${input.id}`, {
        ...(input.name !== undefined ? { name: input.name } : {}),
        ...(input.icon !== undefined ? { icon: input.icon } : {}),
      }),
    onSuccess: () => invalidarCategorias(client),
  });
}

/**
 * Excluir categoria. O servidor decide entre apagar e arquivar: com histórico em
 * cima, apagar transformaria gasto classificado em gasto solto. A resposta diz
 * qual dos dois aconteceu, para a tela poder contar a verdade.
 */
export function useDeleteCategory() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      api.del<{
        arquivada: boolean;
        nome: string;
        subcategorias: number;
        lancamentos: number;
        aviso?: string;
      }>(`/categories/${id}`),
    onSuccess: () => invalidarCategorias(client),
  });
}

/**
 * Salvar a meta A PARTIR do mês escolhido.
 *
 * O `starts_on` não é opcional na prática: sem ele o servidor assume o mês de
 * hoje, e quem está olhando setembro acabaria mudando a meta de outubro. A tela
 * manda sempre o mês que está na tela.
 *
 * Mudar o valor não reescreve o passado — a meta anterior é encerrada no fim do
 * mês anterior e uma nova começa. A resposta diz se foi isso (`versionou`) e
 * quanto valia antes, para a tela poder contar.
 */
export function useSaveBudgetCap() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      category_id: string;
      amount: number;
      starts_on: string;
      member_id?: string;
    }) =>
      api.post<{
        id: string;
        substituiu: boolean;
        versionou: boolean;
        valia_antes?: string;
        ate?: string;
      }>('/budget-caps', input),
    onSuccess: () => invalidarCategorias(client),
  });
}

/** Tirar a meta a partir do mês escolhido — os meses anteriores ficam com ela. */
export function useDeleteBudgetCap() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: { id: string; month: string }) =>
      api.del<{ apagada: boolean; encerrada: boolean; valeu_ate?: string }>(
        `/budget-caps/${input.id}?month=${input.month}`,
      ),
    onSuccess: () => invalidarCategorias(client),
  });
}

// ------------------------------------------------------------ cartoes ---

/** Gasto no cartão e as linhas que podem estar contadas em dobro. */
export function useCardSummary(month: string) {
  return useQuery({
    queryKey: queryKeys.cardSummary(month),
    queryFn: () => api.get<CardSummary>('/cards/summary', { month }),
  });
}

// ------------------------------------------------------------ doacoes ---
// Dinheiro que entra e não é renda. Os avós depositam para a escola das meninas:
// o dinheiro passa pela conta, mas não é da família, e tratar como renda estraga
// o mês, a taxa de poupança e a projeção — esta última é a pior, porque passaria
// a contar com dinheiro que depende da vontade de outra pessoa.

/** Quem doa. Serve para o seletor do lançamento e para a soma do ano. */
export function useDonors() {
  return useQuery({
    queryKey: queryKeys.donors,
    queryFn: () => api.get<Donor[]>('/donors'),
    staleTime: 1000 * 60 * 30,
  });
}

function invalidarDoacoes(client: ReturnType<typeof useQueryClient>): void {
  client.invalidateQueries({ queryKey: queryKeys.donors });
  client.invalidateQueries({ queryKey: ['doacoes'] });
  client.invalidateQueries({ queryKey: ['dashboard'] });
}

export function useCreateDonor() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: { name: string; relationship?: string; notes?: string }) =>
      api.post<Donor>('/donors', input),
    onSuccess: () => invalidarDoacoes(client),
  });
}

export function useUpdateDonor() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: { id: string; name: string; relationship?: string }) =>
      api.patch<Donor>(`/donors/${input.id}`, {
        name: input.name,
        relationship: input.relationship,
      }),
    onSuccess: () => invalidarDoacoes(client),
  });
}

/**
 * Arquiva o doador — não apaga. As doações dele continuam no histórico: apagar
 * deixaria soma sem dono no ano que já passou.
 */
export function useArchiveDonor() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.del<{ arquivado: boolean; nome: string }>(`/donors/${id}`),
    onSuccess: () => invalidarDoacoes(client),
  });
}

/** Quanto cada um doou no ano, contra o limite de isenção do ITCMD. */
export function useDonationsSummary(year: number) {
  return useQuery({
    queryKey: queryKeys.doacoes(year),
    queryFn: () => api.get<DonationsSummary>('/doacoes/resumo', { year }),
  });
}

/**
 * O limite de isenção do ITCMD, que é ESTADUAL: muda de estado para estado e é
 * corrigido todo ano. Por isso é digitado, e não embutido no sistema — um número
 * chutado tranquilizaria sobre um limite que pode não ser o deste estado.
 */
export function useSaveItcmdLimit() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: { itcmd_state?: string; itcmd_annual_exemption?: number | null }) =>
      api.put<{ itcmd_state: string | null; itcmd_annual_exemption: string | null }>(
        '/doacoes/limite',
        input,
      ),
    onSuccess: () => invalidarDoacoes(client),
  });
}

/**
 * Aponta quem depositou num lançamento que entrou sem doador — é como chega o
 * depósito vindo do extrato, porque o banco não sabe quem depositou.
 *
 * `learn_rule` fica de fora: o que se está corrigindo é o doador, não a
 * categoria, e não há regra de fornecedor a aprender com isso.
 */
export function useSetDonor() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: { transaction_id: string; donor_id: string }) =>
      api.patch<Transaction>(`/transactions/${input.transaction_id}`, {
        donor_id: input.donor_id,
      }),
    onSuccess: () => {
      invalidarDoacoes(client);
      client.invalidateQueries({ queryKey: ['transactions'] });
    },
  });
}

// ------------------------------------------------------- fila offline ---
// O gasto em dinheiro só existe se for lançado na hora. "Lanço quando chegar em
// casa" é o mesmo que não lançar — então, sem servidor, o lançamento é guardado
// no aparelho e sobe depois, com a mesma `client_key`, que é o que impede o gasto
// de ser contado duas vezes.

export interface ResultadoDoLancamento {
  /** ficou guardado no aparelho em vez de ir para o servidor */
  enfileirado: boolean;
  transacao?: Transaction;
}

/**
 * Lançar à mão — é por aqui que entra o gasto pago em dinheiro, que não aparece
 * em extrato nenhum. É o único caminho de lançamento do aplicativo, e de
 * propósito: um atalho que falasse direto com o servidor perderia o que foi
 * digitado justamente nas horas em que ele não responde.
 *
 * `client_key` vai sempre preenchida, e nasce com o rascunho na tela: se a
 * resposta se perder no caminho — ou se o lançamento subir pela fila depois — o
 * servidor devolve o que já gravou em vez de cobrar o gasto duas vezes.
 *
 * Só cai na fila o que falhou por falta de servidor (status 0). Recusa do
 * servidor — categoria que exige comentário, valor inválido — volta como erro
 * para a tela, porque guardar na fila um lançamento que já se sabe que não
 * entra seria empurrar o problema para depois, longe de quem pode resolver.
 */
export function useLancar() {
  const client = useQueryClient();
  return useMutation<ResultadoDoLancamento, Error, TransactionCreate>({
    mutationFn: async (input) => {
      if (!input.client_key) throw new Error('Lancamento sem chave de idempotencia.');
      try {
        const transacao = await api.post<Transaction>('/transactions', input);
        return { enfileirado: false, transacao };
      } catch (erro) {
        if (erro instanceof ApiError && erro.status === 0) {
          await enfileirar(input);
          return { enfileirado: true };
        }
        throw erro;
      }
    },
    onSuccess: (resultado) => {
      if (resultado.enfileirado) return;
      client.invalidateQueries({ queryKey: ['transactions'] });
      client.invalidateQueries({ queryKey: ['by-category'] });
      client.invalidateQueries({ queryKey: ['dashboard'] });
      client.invalidateQueries({ queryKey: ['forecast'] });
      client.invalidateQueries({ queryKey: ['category-overview'] });
    },
  });
}

/** O que está esperando para subir, e o botão de tentar agora. */
export function useFila() {
  const client = useQueryClient();
  const [itens, setItens] = useState<ItemDaFila[]>([]);
  const [subindo, setSubindo] = useState(false);

  useEffect(() => assinarFila(setItens), []);

  async function subir(): Promise<ResultadoDaSubida> {
    setSubindo(true);
    try {
      const resultado = await subirFila();
      if (resultado.enviados > 0) {
        client.invalidateQueries({ queryKey: ['transactions'] });
        client.invalidateQueries({ queryKey: ['by-category'] });
        client.invalidateQueries({ queryKey: ['dashboard'] });
        client.invalidateQueries({ queryKey: ['forecast'] });
        client.invalidateQueries({ queryKey: ['category-overview'] });
      }
      setItens(await listarFila());
      return resultado;
    } finally {
      setSubindo(false);
    }
  }

  return {
    itens,
    subindo,
    subir,
    descartar: async (id: string) => {
      await descartar(id);
      setItens(await listarFila());
    },
  };
}
