"""Aritmetica monetaria. Todo dinheiro no sistema e Decimal, nunca float."""

from decimal import ROUND_HALF_UP, Decimal

CENTS = Decimal("0.01")
ZERO = Decimal("0")


def brl(value: Decimal | int | float | str) -> Decimal:
    """Normaliza um valor para 2 casas com arredondamento comercial."""
    return Decimal(str(value)).quantize(CENTS, rounding=ROUND_HALF_UP)


def pct(value: Decimal | int | float | str) -> Decimal:
    """Normaliza uma taxa para 6 casas (0.115000 = 11,5%)."""
    return Decimal(str(value)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def safe_div(numerator: Decimal, denominator: Decimal) -> Decimal:
    return ZERO if denominator == 0 else numerator / denominator
