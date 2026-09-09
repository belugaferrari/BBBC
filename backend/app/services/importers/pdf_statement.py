"""Leitor de extrato em PDF.

Aviso honesto: PDF nao e formato de dados, e formato de impressao. Nao ha
estrutura garantida - cada banco diagrama do seu jeito, e o mesmo banco muda o
leiaute sem avisar. O que este leitor faz e reconhecer linhas com o formato
`data ... descricao ... valor`, que cobre a maioria dos extratos brasileiros.

Por isso a importacao SEMPRE passa pela tela de conferencia antes de gravar, e
o que vem de PDF entra marcado com origem propria (IMPORT_PDF): sao os
lancamentos que merecem um olhar antes de virarem verdade.

Se o seu banco oferecer OFX ou CSV, prefira - a leitura e exata.
"""

from __future__ import annotations

import io
import re
from decimal import Decimal

from app.models.enums import TxDirection
from app.services.importers.base import (
    ParsedStatement,
    ParsedTransaction,
    StatementParseError,
)
from app.services.importers.parsing import parse_amount, parse_date

# data no inicio, descricao no meio, valor (com centavos) no fim.
_LINE_RE = re.compile(
    r"""^\s*
    (?P<date>\d{1,2}[/.-]\d{1,2}(?:[/.-]\d{2,4})?|\d{1,2}\s+[a-zA-Zçã]{3}\.?)
    \s+
    (?P<description>.+?)
    \s+
    (?P<amount>-?\(?\s*(?:R\$\s*)?\d{1,3}(?:\.\d{3})*,\d{2}\)?-?)
    \s*
    (?P<marker>[CD])?
    \s*$""",
    re.VERBOSE,
)

# linhas que existem em todo extrato mas nao sao lancamento
_NOISE_RE = re.compile(
    r"(?i)\b(saldo\s+(anterior|do\s+dia|final|em)|total\s+(geral|do)|extrato|"
    r"pagina\s+\d|s a l d o)\b"
)


def extract_text(content: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover
        raise StatementParseError(
            "leitura de PDF exige a biblioteca pypdf instalada no servidor"
        ) from exc

    try:
        reader = PdfReader(io.BytesIO(content))
    except Exception as exc:
        raise StatementParseError(f"nao consegui abrir o PDF: {exc}") from exc

    if reader.is_encrypted:
        # extrato de banco costuma vir protegido pelo CPF do titular
        try:
            reader.decrypt("")
        except Exception as exc:
            raise StatementParseError(
                "PDF protegido por senha; remova a protecao e envie de novo"
            ) from exc

    return "\n".join(page.extract_text() or "" for page in reader.pages)


def parse(content: bytes) -> ParsedStatement:
    text = extract_text(content)
    if not text.strip():
        raise StatementParseError(
            "o PDF nao tem texto extraivel (provavelmente e imagem escaneada); "
            "peça ao banco o extrato em OFX ou CSV"
        )

    statement = ParsedStatement(file_format="PDF")
    statement.warnings.append(
        "Leitura de PDF e por aproximacao: confira os lancamentos antes de confirmar."
    )

    reference_year = _guess_year(text)
    ignored = 0

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or _NOISE_RE.search(stripped):
            continue

        match = _LINE_RE.match(stripped)
        if not match:
            if re.search(r"\d,\d{2}", stripped):
                ignored += 1  # tinha cara de lancamento e nao casou
            continue

        try:
            booked_on = parse_date(match.group("date"), reference_year)
            amount = parse_amount(match.group("amount"))
        except ValueError:
            ignored += 1
            continue

        marker = (match.group("marker") or "").upper()
        if marker == "D":
            direction = TxDirection.SAIDA
        elif marker == "C":
            direction = TxDirection.ENTRADA
        else:
            direction = TxDirection.ENTRADA if amount > 0 else TxDirection.SAIDA

        description = re.sub(r"\s{2,}", " ", match.group("description")).strip(" .-")
        if not description or amount == Decimal("0"):
            continue

        statement.transactions.append(
            ParsedTransaction(
                booked_on=booked_on,
                amount=abs(amount),
                direction=direction,
                description=description,
                raw_line=stripped[:500],
            )
        )

    if not statement.transactions:
        raise StatementParseError(
            "nao reconheci nenhum lancamento neste PDF. Se o banco oferecer OFX ou "
            "CSV, prefira - a leitura e exata."
        )
    if ignored:
        statement.warnings.append(
            f"{ignored} linhas com cara de lancamento nao foram reconhecidas; "
            "confira se falta algo."
        )
    return statement


def _guess_year(text: str) -> int | None:
    """Extrato de cartao costuma omitir o ano nas linhas, mas traz no cabecalho."""
    years = re.findall(r"\b(20\d{2})\b", text)
    return int(max(years)) if years else None
