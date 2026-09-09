"""Escolha do leitor pelo conteudo do arquivo, nao so pela extensao."""

from __future__ import annotations

from app.services.importers import csv_statement, ofx, pdf_statement
from app.services.importers.base import ParsedStatement, StatementParseError

SUPPORTED = ("OFX", "CSV", "PDF")
MAX_FILE_BYTES = 10 * 1024 * 1024


def detect_format(filename: str, content: bytes) -> str:
    """A extensao e uma dica; o conteudo decide."""
    if content[:5] == b"%PDF-":
        return "PDF"

    head = content[:2048].lstrip().upper()
    if b"<OFX>" in head or b"OFXHEADER" in head or b"<STMTTRN>" in content[:20000].upper():
        return "OFX"

    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if suffix in {"ofx", "ofc", "qfx"}:
        return "OFX"
    if suffix in {"csv", "tsv", "txt"}:
        return "CSV"
    if suffix == "pdf":
        return "PDF"

    raise StatementParseError(
        f"formato nao reconhecido ({filename or 'arquivo'}). "
        f"Aceitos: {', '.join(SUPPORTED)}."
    )


def parse_statement(filename: str, content: bytes) -> ParsedStatement:
    if not content:
        raise StatementParseError("arquivo vazio")
    if len(content) > MAX_FILE_BYTES:
        raise StatementParseError(
            f"arquivo maior que {MAX_FILE_BYTES // (1024 * 1024)} MB"
        )

    file_format = detect_format(filename, content)
    parser = {"OFX": ofx, "CSV": csv_statement, "PDF": pdf_statement}[file_format]
    return parser.parse(content)
