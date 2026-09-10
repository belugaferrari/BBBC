"""Pontos de cartao de credito.

Duas contas que o extrato do banco nao faz por voce:
  * quantos pontos uma compra rendeu (a maioria dos cartoes pontua por DOLAR
    gasto, e nao por real - por isso a cotacao entra na conta);
  * quanto o saldo parado vale, e quanto dele esta prestes a virar pó.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.services.money import ZERO, brl


@dataclass(frozen=True)
class EarningRule:
    points_per_currency: Decimal
    currency_basis: str = "USD"


def points_for_spend(
    amount_brl: Decimal, rule: EarningRule, usd_rate: Decimal | None = None
) -> Decimal:
    """Pontos gerados por uma compra em reais.

    Com base em dolar, a compra e convertida pela cotacao antes de pontuar -
    e por isso a cotacao e obrigatoria nesse caso: chutar 1:1 inflaria o saldo
    em cinco vezes.
    """
    if amount_brl <= 0 or rule.points_per_currency <= 0:
        return ZERO

    if rule.currency_basis.upper() == "BRL":
        base = amount_brl
    else:
        if not usd_rate or usd_rate <= 0:
            raise ValueError(
                "programa pontua por dolar: informe a cotacao para estimar os pontos"
            )
        base = amount_brl / usd_rate

    return (base * rule.points_per_currency).quantize(Decimal("0.01"))


@dataclass
class ProgramSummary:
    name: str
    balance: Decimal
    value_brl: Decimal | None
    expiring_points: Decimal | None
    expires_on: date | None
    days_to_expire: int | None
    should_alert: bool


def summarize_program(
    *,
    name: str,
    balance: Decimal,
    point_value_brl: Decimal | None,
    expires_next_on: date | None,
    expires_next_points: Decimal | None,
    today: date | None = None,
    alert_within_days: int = 60,
) -> ProgramSummary:
    """Ponto que expira sem ser usado e dinheiro jogado fora - o aviso precisa
    chegar com folga para dar tempo de resgatar."""
    today = today or date.today()
    dias = (expires_next_on - today).days if expires_next_on else None

    return ProgramSummary(
        name=name,
        balance=brl(balance),
        value_brl=(
            (balance * point_value_brl).quantize(Decimal("0.01"))
            if point_value_brl is not None
            else None
        ),
        expiring_points=(
            brl(expires_next_points) if expires_next_points is not None else None
        ),
        expires_on=expires_next_on,
        days_to_expire=dias,
        should_alert=(
            dias is not None
            and dias <= alert_within_days
            and (expires_next_points or ZERO) > 0
        ),
    )


def apply_movements(opening_balance: Decimal, movements: list[Decimal]) -> Decimal:
    """Saldo depois dos movimentos. Positivo entra, negativo sai."""
    return brl(opening_balance + sum(movements, ZERO))
