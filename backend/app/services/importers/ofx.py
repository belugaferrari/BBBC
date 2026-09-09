"""Leitor de OFX / OFC.

E o melhor formato de importacao: o proprio banco gera, os campos sao
delimitados e cada lancamento traz um identificador unico (FITID), o que torna
a deduplicacao exata em vez de heuristica. Quando o banco oferecer OFX, e o que
deve ser usado.

O OFX 1.x e SGML (etiquetas sem fechamento) e o 2.x e XML. Em vez de exigir um
parser de SGML, extraimos os blocos <STMTTRN> por expressao regular, que atende
aos dois.
"""

from __future__ import annotations

import re
from decimal import Decimal

from app.models.enums import TxDirection
from app.services.importers.base import (
    ParsedStatement,
    ParsedTransaction,
    StatementParseError,
)
from app.services.importers.parsing import parse_amount, parse_date

_TRANSACTION_RE = re.compile(r"<STMTTRN>(.*?)</STMTTRN>", re.IGNORECASE | re.DOTALL)
_ACCOUNT_RE = re.compile(r"<ACCTID>\s*([^\r\n<]+)", re.IGNORECASE)


def _tag(block: str, tag: str) -> str | None:
    """Valor de uma etiqueta, com ou sem fechamento (SGML ou XML)."""
    match = re.search(rf"<{tag}>\s*([^\r\n<]*)", block, re.IGNORECASE)
    if not match:
        return None
    value = match.group(1).strip()
    return value or None


def parse(content: bytes) -> ParsedStatement:
    text = content.decode("latin-1", errors="replace")
    blocks = _TRANSACTION_RE.findall(text)
    if not blocks:
        raise StatementParseError(
            "nenhum lancamento <STMTTRN> encontrado - o arquivo e mesmo um OFX?"
        )

    statement = ParsedStatement(file_format="OFX")
    account = _ACCOUNT_RE.search(text)
    if account:
        statement.account_hint = account.group(1).strip()

    for block in blocks:
        raw_date = _tag(block, "DTPOSTED") or _tag(block, "DTUSER")
        raw_amount = _tag(block, "TRNAMT")
        if not raw_date or raw_amount is None:
            statement.warnings.append("lancamento sem data ou valor foi ignorado")
            continue

        try:
            # DTPOSTED vem como 20260905 ou 20260905120000[-3:GMT]
            booked_on = parse_date(raw_date[:8])
            amount = parse_amount(raw_amount)
        except ValueError as exc:
            statement.warnings.append(str(exc))
            continue

        # NAME costuma trazer o fornecedor; MEMO, o texto completo
        description = _tag(block, "NAME") or _tag(block, "MEMO") or "Lancamento"
        memo = _tag(block, "MEMO")
        if memo and memo != description:
            description = f"{description} - {memo}"

        statement.transactions.append(
            ParsedTransaction(
                booked_on=booked_on,
                amount=abs(amount),
                direction=TxDirection.ENTRADA if amount > 0 else TxDirection.SAIDA,
                description=description.strip(),
                document=_tag(block, "FITID"),
                raw_line=block.strip()[:500],
            )
        )

    if not statement.transactions:
        raise StatementParseError("o arquivo nao trouxe nenhum lancamento valido")
    if any(t.amount == Decimal("0") for t in statement.transactions):
        statement.warnings.append("ha lancamentos com valor zero no arquivo")
    return statement
