/** Hooks de dados. Uma chave por recurso, para o cache invalidar certo. */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api } from './client';
import type {
  Account,
  BenchmarkEvolution,
  Forecast,
  Member,
  Scope as ScopeType,
  SpendByCategory,
  Category,
  DashboardData,
  Goal,
  Portfolio,
  Scope,
  TaxAssessment,
  Transaction,
} from './types';

export const queryKeys = {
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
};

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
