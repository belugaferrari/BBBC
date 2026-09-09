"""Ponte entre o banco e o motor puro de IR."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.enums import IRDeductionType, IRTreatment
from app.services.queries import ir_year_rows
from app.services.tax import (
    Bracket,
    DeductibleExpense,
    IncomeItem,
    TaxpayerYear,
    TaxTable,
)


class TaxYearNotConfigured(LookupError):
    pass


def load_tax_table(db: Session, year: int) -> TaxTable:
    status = db.execute(
        text("SELECT status FROM tax_years WHERE year = :year"), {"year": year}
    ).scalar_one_or_none()
    if status is None:
        raise TaxYearNotConfigured(
            f"ano-calendario {year} sem parametros cadastrados em tax_years"
        )

    brackets = db.execute(
        text(
            """
            SELECT scope, min_base, max_base, rate, deduction
              FROM tax_brackets
             WHERE year = :year
             ORDER BY scope, min_base
            """
        ),
        {"year": year},
    ).mappings().all()

    parameters = {
        r["key"]: Decimal(r["value"])
        for r in db.execute(
            text("SELECT key, value FROM tax_parameters WHERE year = :year"), {"year": year}
        ).mappings()
    }

    def to_brackets(scope: str) -> tuple[Bracket, ...]:
        return tuple(
            Bracket(
                min_base=Decimal(r["min_base"]),
                max_base=Decimal(r["max_base"]) if r["max_base"] is not None else None,
                rate=Decimal(r["rate"]),
                deduction=Decimal(r["deduction"]),
            )
            for r in brackets
            if r["scope"] == scope
        )

    return TaxTable(
        year=year,
        annual_brackets=to_brackets("ANUAL"),
        monthly_brackets=to_brackets("MENSAL"),
        parameters=parameters,
        status=status,
    )


def load_taxpayer_year(db: Session, family_id: UUID, member_id: UUID, year: int) -> TaxpayerYear:
    raw = ir_year_rows(db, family_id, member_id, year)

    incomes = tuple(
        IncomeItem(treatment=IRTreatment(r["treatment"]), amount=Decimal(r["amount"]))
        for r in raw["incomes"]
        if r["treatment"] != IRTreatment.NAO_APLICAVEL
    )
    expenses = tuple(
        DeductibleExpense(
            deduction_type=IRDeductionType(r["deduction_type"]),
            amount=Decimal(r["amount"]),
            member_id=r["member_id"],
            member_name=r["member_name"] or "",
        )
        for r in raw["deductions"]
    )
    return TaxpayerYear(
        year=year, incomes=incomes, expenses=expenses, dependents=raw["dependents"]
    )
