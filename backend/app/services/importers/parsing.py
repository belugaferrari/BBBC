"""Leitura de numeros e datas no formato brasileiro.

Extrato de banco brasileiro escreve `1.234,56`; planilha exportada em ingles
escreve `1,234.56`; alguns bancos marcam debito com um `D` no fim da linha e
outros com o sinal negativo. Este modulo concentra essa bagunca.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

_MONTHS_PT = {
    "jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
    "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12,
}

# `\b` nao funciona depois de `$` (nao e caractere de palavra), entao o simbolo
# e removido literalmente, junto com espacos e o NBSP que alguns PDFs trazem.
_CURRENCY_RE = re.compile(r"(?i)r\$|brl|[\s\u00a0]")
_AMOUNT_RE = re.compile(r"-?\d[\d.,]*")


class AmountFormatError(ValueError):
    pass


def parse_amount(text: str) -> Decimal:
    """Aceita `1.234,56`, `1,234.56`, `R$ 1.234,56`, `1234,56-`, `(1.234,56)`."""
    cleaned = _CURRENCY_RE.sub("", str(text)).strip()
    if not cleaned:
        raise AmountFormatError("valor vazio")

    negative = False
    if cleaned.startswith("(") and cleaned.endswith(")"):
        negative, cleaned = True, cleaned[1:-1]
    if cleaned.endswith("-"):
        negative, cleaned = True, cleaned[:-1]
    if cleaned.startswith("-"):
        negative, cleaned = True, cleaned[1:]

    has_comma, has_dot = "," in cleaned, "." in cleaned
    if has_comma and has_dot:
        # o separador decimal e o que aparece por ultimo
        decimal_sep = "," if cleaned.rfind(",") > cleaned.rfind(".") else "."
        thousands_sep = "." if decimal_sep == "," else ","
        cleaned = cleaned.replace(thousands_sep, "").replace(decimal_sep, ".")
    elif has_comma:
        # `1,50` e decimal; `1,500` sem centavos tambem costuma ser decimal em
        # extrato brasileiro, mas `1,234,567` so pode ser separador de milhar
        cleaned = (
            cleaned.replace(",", "")
            if cleaned.count(",") > 1
            else cleaned.replace(",", ".")
        )
    elif cleaned.count(".") > 1:
        cleaned = cleaned.replace(".", "")

    try:
        value = Decimal(cleaned)
    except InvalidOperation as exc:
        raise AmountFormatError(f"valor irreconhecivel: {text!r}") from exc
    return -value if negative else value


def find_amounts(text: str) -> list[str]:
    """Todos os trechos que parecem numero, na ordem em que aparecem."""
    return _AMOUNT_RE.findall(text)


class DateFormatError(ValueError):
    pass


def parse_date(text: str, reference_year: int | None = None) -> date:
    """Aceita `05/09/2026`, `05/09/26`, `2026-09-05`, `05092026`, `05/set`."""
    raw = str(text).strip()
    if not raw:
        raise DateFormatError("data vazia")

    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y", "%Y%m%d", "%d%m%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue

    # '05/set' ou '05 set' - extrato de cartao costuma omitir o ano
    match = re.match(r"^(\d{1,2})[\s/-]([a-zA-Zçã]{3})\.?(?:[\s/-](\d{2,4}))?$", raw)
    if match:
        day, month_name, year_text = match.groups()
        month = _MONTHS_PT.get(month_name[:3].lower())
        if month:
            year = int(year_text) if year_text else (reference_year or date.today().year)
            if year < 100:
                year += 2000
            return date(year, month, int(day))

    raise DateFormatError(f"data irreconhecivel: {text!r}")


def looks_like_date(text: str) -> bool:
    try:
        parse_date(text)
        return True
    except DateFormatError:
        return False
