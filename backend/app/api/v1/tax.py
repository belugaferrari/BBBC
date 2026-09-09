"""Imposto de Renda: apuracao, projecao e simulacao de deducoes."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.api.deps import CurrentMember, DbSession, owned_member
from app.models.enums import IRDeductionType
from app.services.tax import (
    DeductibleExpense,
    MissingTaxParameter,
    TaxpayerYear,
    assess_year,
    carne_leao,
    deduction_benefit,
    project_year,
)
from app.services.tax_repository import (
    TaxYearNotConfigured,
    load_tax_table,
    load_taxpayer_year,
)

router = APIRouter(prefix="/tax", tags=["imposto-de-renda"])


def _serialize(result) -> dict:  # noqa: ANN001 - dataclass do motor
    def model(m) -> dict:  # noqa: ANN001
        return {
            "model": m.model,
            "taxable_income": m.taxable_income,
            "total_deductions": m.total_deductions,
            "calculation_base": m.calculation_base,
            "tax_due": m.tax_due,
            "withheld_tax": m.withheld_tax,
            "balance": m.balance,
            "effective_rate": m.effective_rate,
            "deductions_breakdown": m.deductions_breakdown,
            "capped_amounts": m.capped_amounts,
        }

    return {
        "year": result.year,
        "table_status": result.table_status,
        "taxable_income": result.taxable_income,
        "exempt_income": result.exempt_income,
        "exclusive_income": result.exclusive_income,
        "withheld_tax": result.withheld_tax,
        "recommended_model": result.recommended,
        "savings_vs_other": result.savings_vs_other,
        "marginal_rate": result.marginal_rate,
        "completo": model(result.completo),
        "simplificado": model(result.simplificado),
    }


@router.get("/{year}")
def assessment(
    year: int, current: CurrentMember, db: DbSession, member_id: UUID | None = None
) -> dict:
    """Apuracao do ano com base no que ja esta lancado."""
    # sem esta guarda, qualquer usuario autenticado leria a apuracao de IR de
    # outra familia so adivinhando um UUID de membro
    target = owned_member(db, member_id, current).id if member_id else current.id
    try:
        table = load_tax_table(db, year)
    except TaxYearNotConfigured as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc

    try:
        result = assess_year(load_taxpayer_year(db, current.family_id, target, year), table)
    except MissingTaxParameter as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    payload = _serialize(result)
    payload["member_id"] = target
    if table.status == "PROVISORIO":
        payload["aviso"] = (
            "Parametros do ano marcados como PROVISORIO: confira a tabela oficial "
            "antes de usar o resultado para pagar imposto."
        )
    return payload


@router.get("/{year}/projection")
def projection(
    year: int,
    current: CurrentMember,
    db: DbSession,
    monthly_extra_income: Decimal = Decimal("0"),
    monthly_extra_deductible: Decimal = Decimal("0"),
) -> dict:
    """Extrapola o realizado ate dezembro para antecipar o saldo do IR."""
    try:
        table = load_tax_table(db, year)
    except TaxYearNotConfigured as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc

    months_elapsed = date.today().month if date.today().year == year else 12
    realized = load_taxpayer_year(db, current.family_id, current.id, year)
    result = project_year(
        realized, months_elapsed, table, monthly_extra_income, monthly_extra_deductible
    )
    payload = _serialize(result)
    payload["months_elapsed"] = months_elapsed
    return payload


class DeductionSimulationIn(BaseModel):
    deduction_type: IRDeductionType
    amount: Decimal
    member_id: UUID | None = None


@router.post("/{year}/simulate-deduction")
def simulate_deduction(
    year: int, payload: DeductionSimulationIn, current: CurrentMember, db: DbSession
) -> dict:
    """Quanto o casal economiza ao lancar mais uma despesa dedutivel.

    Responde a pergunta pratica do app: 'vale a pena guardar esse recibo?'
    """
    try:
        table = load_tax_table(db, year)
    except TaxYearNotConfigured as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc

    if payload.member_id:
        owned_member(db, payload.member_id, current)

    base = load_taxpayer_year(db, current.family_id, current.id, year)
    before = assess_year(base, table)

    with_extra = TaxpayerYear(
        year=base.year,
        incomes=base.incomes,
        expenses=(
            *base.expenses,
            DeductibleExpense(
                deduction_type=payload.deduction_type,
                amount=payload.amount,
                member_id=payload.member_id,
                description="simulacao",
            ),
        ),
        dependents=base.dependents,
        carne_leao_paid=base.carne_leao_paid,
    )
    after = assess_year(with_extra, table)

    return {
        "tax_before": before.best.tax_due,
        "tax_after": after.best.tax_due,
        "saving": before.best.tax_due - after.best.tax_due,
        "theoretical_saving": deduction_benefit(payload.amount, before),
        "capped_amounts": after.best.capped_amounts,
        "recommended_model": after.recommended,
    }


class CarneLeaoIn(BaseModel):
    month_income: Decimal
    month_deductions: Decimal = Decimal("0")


@router.post("/{year}/carne-leao")
def carne_leao_endpoint(
    year: int, payload: CarneLeaoIn, current: CurrentMember, db: DbSession
) -> dict:
    """DARF mensal sobre receitas recebidas de pessoa fisica (leiloes, alugueis)."""
    try:
        table = load_tax_table(db, year)
    except TaxYearNotConfigured as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc

    dependents = load_taxpayer_year(db, current.family_id, current.id, year).dependents
    return {
        "tax_due": carne_leao(
            payload.month_income, payload.month_deductions, dependents, table
        ),
        "dependents_considered": dependents,
        "table_status": table.status,
    }
