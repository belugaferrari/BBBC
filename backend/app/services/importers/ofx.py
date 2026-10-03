"""Leitor de OFX / OFC.

E o melhor formato de importacao: o proprio banco gera, os campos sao
delimitados e cada lancamento traz um identificador unico (FITID), o que torna a
deduplicacao exata em vez de heuristica. Quando o banco oferecer OFX, e o que
deve ser usado.

O OFX 1.x e SGML e o 2.x e XML. Em vez de exigir um parser de SGML, os blocos
<STMTTRN> sao recortados na mao, o que atende aos dois - e, principalmente, a
banco brasileiro, que respeita o formato pela metade. Duas liberdades que eles
tomam e que este modulo tem de aguentar:

  * ETIQUETA DE AGREGADO SEM FECHAMENTO. O padrao pede </STMTTRN> no fim de cada
    lancamento. Banco do Brasil e Caixa simplesmente nao escrevem, e abrem o
    <STMTTRN> seguinte em cima do anterior. Procurar pelo fechamento nao acha
    lancamento nenhum, e o arquivo inteiro e recusado.

  * ENCODING DECLARADO QUE NAO E O USADO. O cabecalho quase sempre diz
    `ENCODING:USASCII` e `CHARSET:1252`, e boa parte dos bancos grava UTF-8 do
    mesmo jeito. Ler como o cabecalho manda devolve "FarmÃ¡cia" em vez de
    "Farmácia" - e aquele texto e o que alimenta a sugestao de categoria.
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

_ABRE_LANCAMENTO = re.compile(r"<STMTTRN>", re.IGNORECASE)
# O que encerra um lancamento: o fechamento dele, o proximo lancamento, ou o fim
# da lista. Os tres existem em arquivo de verdade; o primeiro que aparecer vale.
_FECHA_LANCAMENTO = re.compile(
    r"</STMTTRN>|<STMTTRN>|</BANKTRANLIST>|</CCSTMTRS>|</STMTRS>", re.IGNORECASE
)
_ACCOUNT_RE = re.compile(r"<ACCTID>\s*([^\r\n<]+)", re.IGNORECASE)

# `ENCODING:` e `CHARSET:` do cabecalho OFX 1.x, e o encoding da declaracao XML
# do OFX 2.x. Lidos sobre os bytes, em ASCII, antes de saber o encoding real -
# o que funciona porque essas linhas sao sempre ASCII.
_CABECALHO_ENCODING = re.compile(rb"ENCODING:\s*([\w-]+)", re.IGNORECASE)
_CABECALHO_CHARSET = re.compile(rb"CHARSET:\s*([\w-]+)", re.IGNORECASE)
_XML_ENCODING = re.compile(rb'encoding\s*=\s*["\']([\w-]+)["\']', re.IGNORECASE)

# Como o banco escreve o charset -> como o Python chama.
_APELIDOS = {
    "1252": "cp1252",
    "WINDOWS-1252": "cp1252",
    "CP1252": "cp1252",
    "ISO-8859-1": "latin-1",
    "LATIN1": "latin-1",
    "LATIN-1": "latin-1",
    "8859-1": "latin-1",
    "UTF-8": "utf-8",
    "UTF8": "utf-8",
    "USASCII": "cp1252",  # ASCII puro le igual; e a dica mais mentirosa que existe
    "ASCII": "cp1252",
    "NONE": "cp1252",
}


def _decodificar(content: bytes) -> str:
    """Transforma os bytes em texto, confiando na ordem certa de pistas.

    A BOM vem primeiro porque e um fato, nao uma declaracao. Depois o teste de
    UTF-8: se os bytes formam UTF-8 valido, e UTF-8 - acento em cp1252 e byte
    solto que nao fecha sequencia multibyte, entao um arquivo cp1252 com acento
    nao passa por aqui por acidente. So no fim o cabecalho e consultado, porque
    e justamente ele que mente.
    """
    if content[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return content.decode("utf-16", errors="replace")
    if content[:3] == b"\xef\xbb\xbf":
        return content.decode("utf-8-sig", errors="replace")

    # UTF-16 sem BOM: byte zero intercalado em texto que e todo ASCII. Um OFX de
    # verdade nao tem byte zero nenhum.
    amostra = content[:2000]
    if amostra.count(b"\x00") > len(amostra) // 4:
        for codec in ("utf-16-le", "utf-16-be"):
            try:
                texto = content.decode(codec)
            except UnicodeDecodeError:
                continue
            if "<" in texto:
                return texto

    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        pass

    for regex in (_XML_ENCODING, _CABECALHO_ENCODING, _CABECALHO_CHARSET):
        achado = regex.search(content[:1000])
        if not achado:
            continue
        nome = achado.group(1).decode("ascii", errors="ignore").upper()
        codec = _APELIDOS.get(nome)
        if not codec:
            continue
        try:
            return content.decode(codec)
        except (UnicodeDecodeError, LookupError):
            continue

    # Ultimo recurso: cp1252 aceita qualquer byte e e o que os bancos usam de
    # fato quando nao e UTF-8.
    return content.decode("cp1252", errors="replace")


def _blocos(texto: str) -> list[str]:
    """Recorta cada <STMTTRN>, com ou sem etiqueta de fechamento."""
    blocos: list[str] = []
    for abre in _ABRE_LANCAMENTO.finditer(texto):
        inicio = abre.end()
        fecha = _FECHA_LANCAMENTO.search(texto, inicio)
        blocos.append(texto[inicio : fecha.start() if fecha else len(texto)])
    return blocos


def _tag(block: str, tag: str) -> str | None:
    """Valor de uma etiqueta, com ou sem fechamento (SGML ou XML)."""
    match = re.search(rf"<{tag}>\s*([^\r\n<]*)", block, re.IGNORECASE)
    if not match:
        return None
    value = match.group(1).strip()
    return value or None


def parse(content: bytes) -> ParsedStatement:
    text = _decodificar(content)
    blocks = _blocos(text)
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
