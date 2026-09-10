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


def format_brl(value: Decimal | int | float | str) -> str:
    """Formata para leitura humana: R$ 1.234,56.

    Existe separado de `brl()` porque aquele devolve Decimal para continuar
    somando; este e o que vai para a tela e para a notificacao no celular, onde
    "450.00" parece defeito.
    """
    numero = f"{brl(value):,.2f}".replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return f"R$ {numero}"
