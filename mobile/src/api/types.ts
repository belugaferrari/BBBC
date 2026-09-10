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

export interface Account {
  id: string;
  name: string;
  type: string;
  owner_member_id: string;
  current_balance: string;
  is_shared: boolean;
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
