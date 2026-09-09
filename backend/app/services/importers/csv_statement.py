"""Leitor de CSV / TSV exportado de banco ou planilha.

Nao existe um formato padrao: cada banco nomeia as colunas de um jeito e alguns
separam debito e credito em colunas diferentes. O leitor identifica as colunas
pelo nome (sem acento, em minusculo) e cai para deteccao posicional quando o
arquivo nao tem cabecalho reconhecivel.
"""

from __future__ import annotations

import csv
import io
import unicodedata
from decimal import Decimal

from app.models.enums import TxDirection
from app.services.importers.base import (
    ParsedStatement,
    ParsedTransaction,
    StatementParseError,
)
from app.services.importers.parsing import looks_like_date, parse_amount, parse_date

_DATE_HEADERS = {"data", "data lancamento", "data do lancamento", "date",
                 "data movimento", "data da compra", "dt"}
_DESCRIPTION_HEADERS = {"descricao", "historico", "lancamento", "description",
                        "memo", "detalhe", "estabelecimento", "titulo"}
_AMOUNT_HEADERS = {"valor", "amount", "montante", "valor (r$)", "valor rs", "vlr"}
_DEBIT_HEADERS = {"debito", "saida", "debit", "pagamento"}
_CREDIT_HEADERS = {"credito", "entrada", "credit", "recebimento"}
_BALANCE_HEADERS = {"saldo", "balance"}
_DOCUMENT_HEADERS = {"documento", "doc", "numero do documento", "identificador", "id"}


def _slug(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(text).strip().lower())
    return "".join(c for c in normalized if not unicodedata.combining(c))


def _detect_columns(header: list[str]) -> dict[str, int]:
    found: dict[str, int] = {}
    for index, raw in enumerate(header):
        name = _slug(raw)
        if name in _DATE_HEADERS and "date" not in found:
            found["date"] = index
        elif name in _DESCRIPTION_HEADERS and "description" not in found:
            found["description"] = index
        elif name in _AMOUNT_HEADERS and "amount" not in found:
            found["amount"] = index
        elif name in _DEBIT_HEADERS:
            found["debit"] = index
        elif name in _CREDIT_HEADERS:
            found["credit"] = index
        elif name in _BALANCE_HEADERS:
            found["balance"] = index
        elif name in _DOCUMENT_HEADERS and "document" not in found:
            found["document"] = index
    return found


def _sniff(text: str) -> str:
    """Escolhe o separador que produz as colunas mais consistentes.

    O `csv.Sniffer` erra em extrato brasileiro: numeros como `28.000,00` fazem
    a virgula parecer separador de coluna. Aqui cada candidato e testado e vence
    o que divide as linhas em mais colunas, do mesmo tamanho.
    """
    lines = [line for line in text.splitlines()[:40] if line.strip()]
    if not lines:
        return ";"

    best, best_score = ";", (0, 0)
    for candidate in (";", ",", "\t", "|"):
        widths = [len(row) for row in csv.reader(lines, delimiter=candidate)]
        if not widths:
            continue
        common = max(set(widths), key=widths.count)
        if common < 2:
            continue
        # consistencia primeiro, numero de colunas como desempate
        score = (widths.count(common), common)
        if score > best_score:
            best, best_score = candidate, score
    return best


def parse(content: bytes) -> ParsedStatement:
    text = content.decode("utf-8-sig", errors="replace")
    if not text.strip():
        raise StatementParseError("arquivo vazio")

    rows = list(csv.reader(io.StringIO(text), delimiter=_sniff(text)))
    rows = [r for r in rows if any(cell.strip() for cell in r)]
    if not rows:
        raise StatementParseError("arquivo sem linhas")

    statement = ParsedStatement(file_format="CSV")

    columns: dict[str, int] = {}
    start = 0
    # o cabecalho nem sempre e a primeira linha: bancos escrevem nome, agencia e
    # periodo antes dele
    for index, row in enumerate(rows[:15]):
        detected = _detect_columns(row)
        if "date" in detected and ("amount" in detected or "debit" in detected
                                   or "credit" in detected):
            columns, start = detected, index + 1
            break

    if not columns:
        columns, start = _detect_positional(rows), 0
        statement.warnings.append(
            "cabecalho nao reconhecido; as colunas foram deduzidas pelo conteudo"
        )

    for row in rows[start:]:
        parsed = _parse_row(row, columns, statement)
        if parsed:
            statement.transactions.append(parsed)

    if not statement.transactions:
        raise StatementParseError(
            "nenhuma linha com data e valor reconheciveis - confira o separador e o formato"
        )
    return statement


def _detect_positional(rows: list[list[str]]) -> dict[str, int]:
    """Sem cabecalho: a primeira coluna que parece data e a data; a ultima que
    parece numero com centavos e o valor; a mais longa e a descricao."""
    sample = [r for r in rows[:40] if len(r) >= 2]
    if not sample:
        raise StatementParseError("nao consegui identificar as colunas do arquivo")

    width = max(len(r) for r in sample)
    columns: dict[str, int] = {}

    for index in range(width):
        values = [r[index] for r in sample if len(r) > index and r[index].strip()]
        if not values:
            continue
        if "date" not in columns and sum(looks_like_date(v) for v in values) > len(values) * 0.6:
            columns["date"] = index
            continue
        numeric = sum(1 for v in values if _is_amount(v))
        if numeric > len(values) * 0.6:
            columns["amount"] = index  # a ultima coluna numerica vence
        elif "description" not in columns:
            columns["description"] = index

    if "date" not in columns or "amount" not in columns:
        raise StatementParseError("nao encontrei colunas de data e valor")
    return columns


def _is_amount(value: str) -> bool:
    try:
        parse_amount(value)
        return any(ch.isdigit() for ch in value)
    except ValueError:
        return False


def _parse_row(
    row: list[str], columns: dict[str, int], statement: ParsedStatement
) -> ParsedTransaction | None:
    def cell(key: str) -> str:
        index = columns.get(key)
        return row[index].strip() if index is not None and len(row) > index else ""

    raw_date = cell("date")
    if not raw_date:
        return None
    try:
        booked_on = parse_date(raw_date)
    except ValueError:
        return None  # linha de rodape ou de saldo, nao e lancamento

    amount: Decimal | None = None
    direction: TxDirection | None = None

    if "amount" in columns and cell("amount"):
        try:
            value = parse_amount(cell("amount"))
        except ValueError as exc:
            statement.warnings.append(f"linha ignorada: {exc}")
            return None
        amount = abs(value)
        direction = TxDirection.ENTRADA if value >= 0 else TxDirection.SAIDA
    else:
        debit, credit = cell("debit"), cell("credit")
        for text, kind in ((credit, TxDirection.ENTRADA), (debit, TxDirection.SAIDA)):
            if text and _is_amount(text) and parse_amount(text) != 0:
                amount, direction = abs(parse_amount(text)), kind
                break

    if amount is None or direction is None or amount == 0:
        return None

    balance = None
    if cell("balance") and _is_amount(cell("balance")):
        balance = parse_amount(cell("balance"))

    return ParsedTransaction(
        booked_on=booked_on,
        amount=amount,
        direction=direction,
        description=cell("description") or "Lancamento importado",
        document=cell("document") or None,
        balance_after=balance,
        raw_line=";".join(row)[:500],
    )
