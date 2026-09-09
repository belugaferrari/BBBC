"""Motor de Imposto de Renda Pessoa Fisica.

Principios:
  * Nenhuma aliquota, faixa ou limite fica no codigo - tudo vem das tabelas
    `tax_brackets` / `tax_parameters`, carregadas em `TaxTable`.
  * O modulo e puro (sem I/O): recebe dados ja materializados e devolve o
    memorial de calculo completo, o que o torna testavel e auditavel.
  * A classificacao tributavel / isenta / exclusiva vem da taxonomia de
    categorias (`ir_treatment`), com override por transacao.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID

from app.models.enums import IRDeductionType, IRTreatment, TaxModel
from app.services.money import ZERO, brl, safe_div

# Tratamentos que compoem a base tributavel sujeita a tabela progressiva anual.
TAXABLE_TREATMENTS = frozenset(
    {IRTreatment.TRIBUTAVEL_TABELA, IRTreatment.TRIBUTAVEL_CARNE_LEAO}
)


class MissingTaxParameter(KeyError):
    """Parametro fiscal ausente para o ano-calendario pedido."""


@dataclass(frozen=True)
class Bracket:
    min_base: Decimal
    max_base: Decimal | None
    rate: Decimal
    deduction: Decimal

    def contains(self, base: Decimal) -> bool:
        return base >= self.min_base and (self.max_base is None or base <= self.max_base)


@dataclass(frozen=True)
class TaxTable:
    """Retrato dos parametros de um ano-calendario."""

    year: int
    annual_brackets: tuple[Bracket, ...]
    monthly_brackets: tuple[Bracket, ...] = ()
    parameters: dict[str, Decimal] = field(default_factory=dict)
    status: str = "PROVISORIO"

    def param(self, key: str, default: Decimal | None = None) -> Decimal:
        if key in self.parameters:
            return self.parameters[key]
        if default is not None:
            return default
        raise MissingTaxParameter(f"parametro {key!r} nao cadastrado para {self.year}")


@dataclass(frozen=True)
class IncomeItem:
    """Um rendimento ja classificado pela taxonomia."""

    treatment: IRTreatment
    amount: Decimal
    withheld_tax: Decimal = ZERO
    source: str = ""


@dataclass(frozen=True)
class DeductibleExpense:
    """Despesa dedutivel. `member_id` e quem consumiu o servico - e o que
    permite aplicar o teto de instrucao por pessoa (cada filha tem o seu)."""

    deduction_type: IRDeductionType
    amount: Decimal
    member_id: UUID | None = None
    member_name: str = ""
    description: str = ""


@dataclass(frozen=True)
class TaxpayerYear:
    year: int
    incomes: tuple[IncomeItem, ...] = ()
    expenses: tuple[DeductibleExpense, ...] = ()
    dependents: int = 0
    # imposto ja pago por carne-leao ao longo do ano
    carne_leao_paid: Decimal = ZERO


@dataclass
class ModelResult:
    model: TaxModel
    taxable_income: Decimal
    total_deductions: Decimal
    calculation_base: Decimal
    tax_due: Decimal
    withheld_tax: Decimal
    balance: Decimal          # > 0 a pagar, < 0 a restituir
    effective_rate: Decimal
    deductions_breakdown: dict[str, Decimal]
    capped_amounts: dict[str, Decimal]  # quanto foi perdido por teto


@dataclass
class IRResult:
    year: int
    taxable_income: Decimal
    exempt_income: Decimal
    exclusive_income: Decimal
    withheld_tax: Decimal
    completo: ModelResult
    simplificado: ModelResult
    recommended: TaxModel
    savings_vs_other: Decimal
    marginal_rate: Decimal
    table_status: str

    @property
    def best(self) -> ModelResult:
        return self.completo if self.recommended == TaxModel.COMPLETO else self.simplificado


# ---------------------------------------------------------------------------
# Tabela progressiva
# ---------------------------------------------------------------------------
def progressive_tax(base: Decimal, brackets: tuple[Bracket, ...]) -> Decimal:
    """Imposto pelo metodo 'aliquota x base - parcela a deduzir'."""
    if base <= 0 or not brackets:
        return ZERO
    for bracket in sorted(brackets, key=lambda b: b.min_base):
        if bracket.contains(base):
            return max(ZERO, brl(base * bracket.rate - bracket.deduction))
    # base acima da ultima faixa fechada
    last = max(brackets, key=lambda b: b.min_base)
    return max(ZERO, brl(base * last.rate - last.deduction))


def marginal_rate(base: Decimal, brackets: tuple[Bracket, ...]) -> Decimal:
    for bracket in sorted(brackets, key=lambda b: b.min_base):
        if bracket.contains(base):
            return bracket.rate
    return max(brackets, key=lambda b: b.min_base).rate if brackets else ZERO


# ---------------------------------------------------------------------------
# Classificacao dos rendimentos
# ---------------------------------------------------------------------------
def classify_incomes(incomes: tuple[IncomeItem, ...]) -> dict[str, Decimal]:
    """Separa a base tributavel da isenta e da tributada exclusivamente na fonte."""
    totals = {
        "tributavel": ZERO,
        "isento": ZERO,
        "exclusiva_fonte": ZERO,
        "retido": ZERO,
    }
    for item in incomes:
        totals["retido"] += item.withheld_tax
        if item.treatment in TAXABLE_TREATMENTS:
            totals["tributavel"] += item.amount
        elif item.treatment == IRTreatment.ISENTO_NAO_TRIBUTAVEL:
            totals["isento"] += item.amount
        elif item.treatment == IRTreatment.EXCLUSIVA_FONTE:
            totals["exclusiva_fonte"] += item.amount
    return {k: brl(v) for k, v in totals.items()}


# ---------------------------------------------------------------------------
# Deducoes (modelo completo)
# ---------------------------------------------------------------------------
def compute_deductions(
    expenses: tuple[DeductibleExpense, ...],
    dependents: int,
    taxable_income: Decimal,
    table: TaxTable,
) -> tuple[dict[str, Decimal], dict[str, Decimal]]:
    """Devolve (deducoes aplicadas, valores perdidos por teto).

    Regras aplicadas:
      * saude, previdencia oficial, pensao judicial e livro-caixa: sem teto;
      * instrucao: teto anual POR pessoa (titular e cada dependente);
      * PGBL: limitado a um percentual da renda bruta tributavel;
      * dependentes: valor fixo por dependente.
    """
    applied: dict[str, Decimal] = defaultdict(lambda: ZERO)
    capped: dict[str, Decimal] = defaultdict(lambda: ZERO)

    education_by_person: dict[str, Decimal] = defaultdict(lambda: ZERO)
    pgbl_total = ZERO

    for exp in expenses:
        if exp.amount <= 0:
            continue
        match exp.deduction_type:
            case IRDeductionType.SAUDE:
                applied["saude"] += exp.amount
            case IRDeductionType.EDUCACAO:
                key = str(exp.member_id) if exp.member_id else "titular"
                education_by_person[key] += exp.amount
            case IRDeductionType.PREVIDENCIA_OFICIAL:
                applied["previdencia_oficial"] += exp.amount
            case IRDeductionType.PREVIDENCIA_PRIVADA_PGBL:
                pgbl_total += exp.amount
            case IRDeductionType.PENSAO_ALIMENTICIA:
                applied["pensao_alimenticia"] += exp.amount
            case IRDeductionType.LIVRO_CAIXA:
                applied["livro_caixa"] += exp.amount
            case _:
                continue

    # Instrucao: o teto vale por pessoa, entao o excedente de uma filha nao
    # pode ser aproveitado pela outra.
    education_cap = table.param("LIMITE_EDUCACAO_ANUAL")
    education_applied = ZERO
    education_lost = ZERO
    for _person, amount in education_by_person.items():
        allowed = min(amount, education_cap)
        education_applied += allowed
        education_lost += amount - allowed
    if education_applied:
        applied["educacao"] = education_applied
    if education_lost:
        capped["educacao"] = education_lost

    # PGBL: limitado a um percentual da renda bruta tributavel do ano.
    if pgbl_total:
        pgbl_cap = brl(taxable_income * table.param("LIMITE_PGBL_PCT", Decimal("0.12")))
        applied["previdencia_privada_pgbl"] = min(pgbl_total, pgbl_cap)
        if pgbl_total > pgbl_cap:
            capped["previdencia_privada_pgbl"] = pgbl_total - pgbl_cap

    if dependents:
        applied["dependentes"] = brl(dependents * table.param("DEDUCAO_DEPENDENTE_ANUAL"))

    return ({k: brl(v) for k, v in applied.items()}, {k: brl(v) for k, v in capped.items()})


# ---------------------------------------------------------------------------
# Apuracao anual
# ---------------------------------------------------------------------------
def _model_result(
    model: TaxModel,
    taxable: Decimal,
    deductions: dict[str, Decimal],
    capped: dict[str, Decimal],
    withheld: Decimal,
    table: TaxTable,
) -> ModelResult:
    total_deductions = brl(sum(deductions.values(), ZERO))
    base = max(ZERO, brl(taxable - total_deductions))
    tax_due = progressive_tax(base, table.annual_brackets)
    return ModelResult(
        model=model,
        taxable_income=brl(taxable),
        total_deductions=total_deductions,
        calculation_base=base,
        tax_due=tax_due,
        withheld_tax=brl(withheld),
        balance=brl(tax_due - withheld),
        effective_rate=safe_div(tax_due, taxable).quantize(Decimal("0.0001")) if taxable else ZERO,
        deductions_breakdown=deductions,
        capped_amounts=capped,
    )


def assess_year(taxpayer: TaxpayerYear, table: TaxTable) -> IRResult:
    """Apura os dois modelos e recomenda o mais vantajoso."""
    if not table.annual_brackets:
        # Sem faixas cadastradas o calculo devolveria zero em silencio, que e a
        # pior resposta possivel para um modulo de imposto.
        raise MissingTaxParameter(
            f"tabela progressiva ANUAL nao cadastrada para {table.year}"
        )
    totals = classify_incomes(taxpayer.incomes)
    taxable = totals["tributavel"]
    withheld = brl(totals["retido"] + taxpayer.carne_leao_paid)

    complete_deductions, capped = compute_deductions(
        taxpayer.expenses, taxpayer.dependents, taxable, table
    )
    completo = _model_result(
        TaxModel.COMPLETO, taxable, complete_deductions, capped, withheld, table
    )

    simplified_discount = min(
        brl(taxable * table.param("DESCONTO_SIMPLIFICADO_PCT")),
        table.param("DESCONTO_SIMPLIFICADO_TETO"),
    )
    simplificado = _model_result(
        TaxModel.SIMPLIFICADO,
        taxable,
        {"desconto_simplificado": brl(simplified_discount)},
        {},
        withheld,
        table,
    )

    recommended = (
        TaxModel.COMPLETO if completo.tax_due <= simplificado.tax_due else TaxModel.SIMPLIFICADO
    )
    savings = brl(abs(completo.tax_due - simplificado.tax_due))

    return IRResult(
        year=taxpayer.year,
        taxable_income=taxable,
        exempt_income=totals["isento"],
        exclusive_income=totals["exclusiva_fonte"],
        withheld_tax=withheld,
        completo=completo,
        simplificado=simplificado,
        recommended=recommended,
        savings_vs_other=savings,
        marginal_rate=marginal_rate(
            completo.calculation_base if recommended == TaxModel.COMPLETO
            else simplificado.calculation_base,
            table.annual_brackets,
        ),
        table_status=table.status,
    )


def deduction_benefit(extra_amount: Decimal, result: IRResult) -> Decimal:
    """Quanto o casal economiza de imposto para cada real a mais de despesa
    dedutivel. Usado no app para mostrar o impacto de marcar uma nota de saude."""
    if result.recommended != TaxModel.COMPLETO:
        return ZERO
    return brl(extra_amount * result.marginal_rate)


# ---------------------------------------------------------------------------
# Carne-leao mensal (receita de leiloes, alugueis, servicos a PF)
# ---------------------------------------------------------------------------
def carne_leao(
    month_income: Decimal,
    month_deductions: Decimal,
    dependents: int,
    table: TaxTable,
) -> Decimal:
    """Imposto mensal devido sobre rendimento recebido de pessoa fisica."""
    if not table.monthly_brackets:
        raise MissingTaxParameter(f"tabela MENSAL nao cadastrada para {table.year}")
    dependent_deduction = brl(
        dependents * table.param("DEDUCAO_DEPENDENTE_ANUAL") / Decimal("12")
    )
    base = max(ZERO, brl(month_income - month_deductions - dependent_deduction))
    tax = progressive_tax(base, table.monthly_brackets)

    # Regra 2026+: faixa de isencao ampliada com redutor progressivo entre a
    # isencao e o limite superior. Parametrizada; ausente, nada muda.
    isencao = table.parameters.get("ISENCAO_MENSAL")
    limite = table.parameters.get("REDUTOR_LIMITE_SUPERIOR")
    if isencao and limite and limite > isencao:
        if month_income <= isencao:
            return ZERO
        if month_income < limite:
            faixa = limite - isencao
            redutor = tax * (limite - month_income) / faixa
            return max(ZERO, brl(tax - redutor))
    return tax


# ---------------------------------------------------------------------------
# Projecao do ano corrente
# ---------------------------------------------------------------------------
def project_year(
    realized: TaxpayerYear,
    months_elapsed: int,
    table: TaxTable,
    monthly_extra_income: Decimal = ZERO,
    monthly_extra_deductible: Decimal = ZERO,
) -> IRResult:
    """Extrapola o realizado ate dezembro para antecipar o saldo do IR.

    O realizado e mantido; os meses restantes sao projetados pela media mensal
    observada, mais os ajustes informados pelo usuario.
    """
    months_elapsed = max(1, min(12, months_elapsed))
    remaining = 12 - months_elapsed
    if remaining == 0:
        return assess_year(realized, table)

    incomes = list(realized.incomes)
    expenses = list(realized.expenses)

    by_treatment: dict[IRTreatment, Decimal] = defaultdict(lambda: ZERO)
    withheld_by_treatment: dict[IRTreatment, Decimal] = defaultdict(lambda: ZERO)
    for item in realized.incomes:
        by_treatment[item.treatment] += item.amount
        withheld_by_treatment[item.treatment] += item.withheld_tax

    for treatment, total in by_treatment.items():
        monthly = total / months_elapsed
        withheld_monthly = withheld_by_treatment[treatment] / months_elapsed
        incomes.append(
            IncomeItem(
                treatment=treatment,
                amount=brl(monthly * remaining),
                withheld_tax=brl(withheld_monthly * remaining),
                source="projecao",
            )
        )
    if monthly_extra_income:
        incomes.append(
            IncomeItem(
                treatment=IRTreatment.TRIBUTAVEL_TABELA,
                amount=brl(monthly_extra_income * remaining),
                source="projecao_manual",
            )
        )

    by_deduction: dict[tuple[IRDeductionType, str | None], Decimal] = defaultdict(lambda: ZERO)
    for exp in realized.expenses:
        by_deduction[(exp.deduction_type, str(exp.member_id) if exp.member_id else None)] += (
            exp.amount
        )
    for (deduction_type, member), total in by_deduction.items():
        expenses.append(
            DeductibleExpense(
                deduction_type=deduction_type,
                amount=brl(total / months_elapsed * remaining),
                member_id=UUID(member) if member else None,
                description="projecao",
            )
        )
    if monthly_extra_deductible:
        expenses.append(
            DeductibleExpense(
                deduction_type=IRDeductionType.SAUDE,
                amount=brl(monthly_extra_deductible * remaining),
                description="projecao_manual",
            )
        )

    projected = TaxpayerYear(
        year=realized.year,
        incomes=tuple(incomes),
        expenses=tuple(expenses),
        dependents=realized.dependents,
        carne_leao_paid=realized.carne_leao_paid,
    )
    return assess_year(projected, table)
