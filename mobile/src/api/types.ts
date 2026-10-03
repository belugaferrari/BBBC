/** Contratos devolvidos pela API (espelho dos schemas do backend). */

export type Scope = 'familia' | 'individual';

export interface AuthToken {
  access_token: string;
  token_type: string;
  member_id: string;
  family_id: string;
  full_name: string;
}

export interface Cashflow {
  month: string;
  inflow: string;
  /** tudo que saiu da conta */
  outflow: string;
  /** o que foi consumido de verdade */
  consumo: string;
  /** amortização e aporte: saiu da conta, mas virou patrimônio */
  patrimonio: string;
  net: string;
  savings_rate: string;
}

export interface Balances {
  by_type: Record<string, string>;
  liquid: string;
  credit_card_debt: string;
  invested: string;
  net_worth: string;
}

export interface SankeyNode {
  id: string;
  label: string;
  stage: number;
  value: string;
}

export interface SankeyLink {
  source: string;
  target: string;
  value: string;
}

export interface SankeyData {
  total_income: string;
  total_expense: string;
  balance: string;
  nodes: SankeyNode[];
  links: SankeyLink[];
}

export interface BudgetCapStatus {
  category_id: string;
  category_name: string;
  cap: string;
  spent: string;
  remaining: string;
  used_pct: string;
  projected_spend: string;
  projected_overflow: string;
  should_alert: boolean;
  severity: 'INFO' | 'ATENCAO' | 'CRITICO';
}

export interface AlertItem {
  id: string;
  kind: string;
  severity: 'INFO' | 'ATENCAO' | 'CRITICO';
  title: string;
  body: string | null;
}

export interface DashboardData {
  reference_month: string;
  scope: Scope;
  cashflow: Cashflow;
  balances: Balances;
  sankey: SankeyData;
  budget_caps: BudgetCapStatus[];
  alerts: AlertItem[];
}

export interface Category {
  id: string;
  parent_id: string | null;
  name: string;
  slug: string;
  path: string;
  depth: number;
  kind: 'RECEITA' | 'DESPESA' | 'TRANSFERENCIA' | 'INVESTIMENTO';
  ir_treatment: string;
  ir_deduction_type: string;
  icon: string | null;
  /** 'Únicos (com comentários)': o lançamento só fecha com uma explicação. */
  requires_note: boolean;
  /** false em amortização e aporte: sai da conta, mas não é consumo */
  counts_as_expense: boolean;
  children: Category[];
}

export interface Transaction {
  id: string;
  account_id: string;
  owner_member_id: string;
  category_id: string | null;
  booked_on: string;
  amount: string;
  direction: 'ENTRADA' | 'SAIDA' | 'TRANSFERENCIA';
  description: string;
  status: string;
  source: string;
  auto_confidence: string | null;
  ir_deduction_member_id: string | null;
}

export interface GoalProjection {
  name: string;
  months_remaining: number;
  adjusted_target: string;
  projected_amount: string;
  gap: string;
  required_monthly: string;
  contribution_delta: string;
  on_track: boolean;
  series: { month: number; balance: string; target: string }[];
}

export interface Goal {
  id: string;
  name: string;
  target_amount: string;
  target_date: string;
  current_amount: string;
  monthly_contribution: string;
  status: string;
  projection: GoalProjection;
}

export interface Portfolio {
  total_invested: string;
  total_market_value: string;
  total_profit: string;
  total_profit_pct: string;
  exempt_share: string;
  by_class: {
    asset_class: string;
    market_value: string;
    invested_amount: string;
    profit: string;
    profit_pct: string;
    weight: string;
  }[];
  by_owner: Record<string, string>;
}

export interface BenchmarkEvolution {
  benchmark: string;
  portfolio_return: string;
  benchmark_return: string;
  excess_return: string;
  pct_of_benchmark: string;
  real_return_vs_ipca: string;
  portfolio_curve: { reference: string; value: string }[];
  benchmark_curve: { reference: string; value: string }[];
}

export interface TaxModelResult {
  model: 'COMPLETO' | 'SIMPLIFICADO';
  taxable_income: string;
  total_deductions: string;
  calculation_base: string;
  tax_due: string;
  withheld_tax: string;
  balance: string;
  effective_rate: string;
  deductions_breakdown: Record<string, string>;
  capped_amounts: Record<string, string>;
}

export interface TaxAssessment {
  year: number;
  table_status: 'PROVISORIO' | 'VIGENTE' | 'ENCERRADO';
  taxable_income: string;
  exempt_income: string;
  exclusive_income: string;
  withheld_tax: string;
  recommended_model: 'COMPLETO' | 'SIMPLIFICADO';
  savings_vs_other: string;
  marginal_rate: string;
  completo: TaxModelResult;
  simplificado: TaxModelResult;
  aviso?: string;
}

export interface ImportPreviewRow {
  index: number;
  booked_on: string;
  amount: string;
  direction: 'ENTRADA' | 'SAIDA';
  description: string;
  document: string | null;
  duplicate: boolean;
  duplicate_reason: string | null;
  suggested_category_id: string | null;
  suggested_category_name: string | null;
  confidence: string | null;
  selected: boolean;
}

export interface StatementImport {
  id: string;
  account_id: string;
  filename: string;
  file_format: 'OFX' | 'CSV' | 'PDF';
  status: 'CRIADO' | 'CONFIRMADO' | 'DESCARTADO' | 'ERRO';
  period_start: string | null;
  period_end: string | null;
  rows_detected: number;
  rows_duplicated: number;
  rows_imported: number;
  warnings: string[];
  preview: ImportPreviewRow[];
  created_at: string;
}

export type AccountType =
  | 'CONTA_CORRENTE'
  | 'POUPANCA'
  | 'CARTAO_CREDITO'
  | 'INVESTIMENTO'
  | 'DINHEIRO'
  | 'PJ'
  | 'OUTRO';

export interface Account {
  id: string;
  name: string;
  type: AccountType;
  owner_member_id: string;
  current_balance: string;
  credit_limit: string | null;
  is_shared: boolean;
  /** conta da empresa: o saldo nao entra no patrimonio da familia */
  is_business: boolean;
  is_archived: boolean;
}

/**
 * Cadastro de conta. Só `name` é exigido - o resto o servidor completa.
 *
 * Enquanto o sistema não puxa dados de banco nenhum sozinho, preencher agência,
 * conta e saldo seria expor informação sem ganhar nada em troca.
 */
export interface AccountCreate {
  name: string;
  type?: AccountType;
  owner_member_id?: string;
  current_balance?: number;
  credit_limit?: number;
  statement_close_day?: number;
  statement_due_day?: number;
  is_shared?: boolean;
  is_business?: boolean;
}

export interface TransactionCreate {
  /** nasce no aparelho: reenviar a mesma chave não cria lançamento repetido */
  client_key?: string;
  account_id: string;
  owner_member_id?: string;
  booked_on: string;
  amount: number;
  direction: 'ENTRADA' | 'SAIDA';
  description: string;
  category_id?: string;
  notes?: string;
}

export interface Member {
  id: string;
  name: string;
  role: 'TITULAR' | 'CONJUGE' | 'DEPENDENTE' | 'CONTADOR';
  is_ir_dependent: boolean;
  can_login: boolean;
}

export interface CategorySlice {
  path: string;
  name: string;
  icon: string | null;
  total: string;
  transactions: number;
  share: string;
}

export interface MemberSlice {
  member_id: string;
  name: string;
  total: string;
  transactions: number;
  share: string;
}

export interface SpendByCategory {
  start: string;
  end: string;
  depth: number;
  total: string;
  categories: CategorySlice[];
  by_member: MemberSlice[];
}

/** FIXO = recorrente cadastrado, ESPERADO = já lançado, ESTIMADO = média. */
export type FlowKind = 'FIXO' | 'ESPERADO' | 'ESTIMADO';

export interface MonthProjection {
  month: string;
  opening_balance: string;
  inflow: string;
  outflow: string;
  net: string;
  closing_balance: string;
  inflow_by_kind: Partial<Record<FlowKind, string>>;
  outflow_by_kind: Partial<Record<FlowKind, string>>;
  items: {
    kind: FlowKind;
    direction: 'ENTRADA' | 'SAIDA';
    amount: string;
    label: string;
    category_name: string | null;
  }[];
}

export interface Forecast {
  start: string;
  months: number;
  scope: Scope;
  sources: {
    recurring_rules: number;
    scheduled_transactions: number;
    estimated_categories: number;
    history_months: number;
  };
  summary: {
    months: number;
    total_inflow: string;
    total_outflow: string;
    net: string;
    closing_balance: string;
    first_negative_month: string | null;
    average_monthly_outflow: string;
  };
  projection: MonthProjection[];
}

export type HoldingKind = 'IMOVEL' | 'TERRENO' | 'VEICULO' | 'PARTICIPACAO' | 'OUTRO';

export interface Holding {
  id: string;
  kind: HoldingKind;
  name: string;
  description: string | null;
  acquired_on: string | null;
  acquisition_value: string | null;
  current_value: string;
  /** a Receita declara pelo custo de aquisição, não pelo valor de mercado */
  ir_declared_value: string | null;
  unrealized_gain: string | null;
  company_cnpj: string | null;
  ownership_percentage: string | null;
  address: string | null;
  is_active: boolean;
}

export interface NetWorth {
  liquid: string;
  invested: string;
  holdings: string;
  debts: string;
  total: string;
  /** quanto do patrimônio não vira dinheiro rápido */
  illiquid_share: string;
  by_kind: Record<string, string>;
  by_owner: Record<string, string>;
}

export interface CardProgram {
  id: string;
  name: string;
  card_name: string | null;
  points_per_currency: string;
  currency_basis: string;
  balance: string;
  balance_value_brl: string | null;
  expires_next_on: string | null;
  expires_next_points: string | null;
  days_to_expire: number | null;
  should_alert: boolean;
}

export interface CardPrograms {
  programs: CardProgram[];
  total_points: string;
  total_value_brl: string;
}

export interface StatementChecklist {
  month: string;
  expected: number;
  received: number;
  missing: number;
  complete: boolean;
  received_list: { account_id: string; name: string; received_at: string | null }[];
  pending_list: { account_id: string; name: string; expected_day: number | null }[];
  late_list: { account_id: string; name: string; days_late: number | null }[];
}

// ---------------------------------------------------------------- categorias ---

/**
 * Uma linha da tela de categorias.
 *
 * `spent` já inclui a subárvore — "Transporte" traz "Gasolina" dentro. Por isso
 * as linhas NÃO podem ser somadas entre si: somar contaria Gasolina duas vezes.
 * O total que fecha é o `total_spent` que vem junto.
 */
export interface CategoryOverviewRow {
  id: string;
  parent_id: string | null;
  name: string;
  path: string;
  /** 0 = raiz ("Despesas"), 1 = as quinze, 2 = as subcategorias */
  depth: number;
  kind: 'RECEITA' | 'DESPESA' | 'TRANSFERENCIA' | 'INVESTIMENTO';
  icon: string | null;
  counts_as_expense: boolean;
  spent: string;
  transactions: number;
  cap_id: string | null;
  cap: string | null;
}

export interface CategoryOverview {
  month: string;
  total_spent: string;
  total_cap: string;
  categories: CategoryOverviewRow[];
}

export interface BudgetCap {
  id: string;
  amount: string;
  alert_at_pct: string;
  includes_descendants: boolean;
  member_id: string | null;
  period: string;
  starts_on: string;
  ends_on: string | null;
}

export interface MonthPoint {
  month: string;
  total: string;
  transactions: number;
}

/** O mesmo recorte serve para a categoria e para a subcategoria. */
export interface CategoryAnalysis {
  category: {
    id: string;
    name: string;
    path: string;
    depth: number;
    kind: string;
    icon: string | null;
    requires_note: boolean;
    counts_as_expense: boolean;
  };
  month: string;
  spent: string;
  transactions: number;
  cap: BudgetCap | null;
  remaining: string | null;
  used_pct: string | null;
  previous_month: string;
  same_month_last_year: string;
  /** null quando não havia base de comparação: variação contra zero não é número */
  vs_last_year_pct: string | null;
  last_12_months: string;
  monthly_average: string;
  vs_average_pct: string | null;
  /** treze pontos: o mês escolhido e os doze que o antecedem */
  series: MonthPoint[];
  children: {
    id: string;
    name: string;
    icon: string | null;
    spent: string;
    transactions: number;
    cap: BudgetCap | null;
    used_pct: string | null;
    same_month_last_year: string;
    monthly_average: string;
  }[];
}

export interface BudgetCapRow {
  cap_id: string;
  category_id: string;
  category_name: string;
  member_id: string | null;
  cap: string;
  spent: string;
  remaining: string;
  used_pct: string | null;
  path: string;
}

// ------------------------------------------------------------------ cartoes ---

export interface CardSummary {
  month: string;
  total_spent: string;
  cards: {
    id: string;
    name: string;
    credit_limit: string | null;
    statement_close_day: number | null;
    statement_due_day: number | null;
    spent: string;
    transactions: number;
    points_base: string;
  }[];
  /** quanto saiu da conta para pagar fatura — não é gasto, é bolso trocando */
  bill_paid: string;
  /** linhas que parecem fatura e estão contando como gasto */
  possible_duplicates: {
    id: string;
    booked_on: string;
    amount: string;
    description: string;
    account_name: string;
    category_name: string | null;
  }[];
  aviso: string | null;
}

// ------------------------------------------------- evolucao do mes ---

export interface DiaAcumulado {
  day: number;
  /** o acumulado do mês até aquele dia, não o gasto do dia */
  total: string;
}

export interface MesDaEvolucao {
  month: string;
  total: string;
  series: DiaAcumulado[];
  /**
   * A meta que valia NAQUELE mês, pela vigência — não a de hoje.
   *
   * É o que impede o gráfico de setembro de mudar quando a meta de outubro
   * muda. `null` quando não havia meta naquela época.
   */
  cap: string | null;
}

export interface Evolucao {
  month: string;
  days_in_month: number;
  /** até que dia a curva deste mês é real; null em mês já fechado */
  today: number | null;
  current: MesDaEvolucao;
  previous_month: MesDaEvolucao;
  same_month_last_year: MesDaEvolucao;
}
