"""Contrato comum dos leitores de extrato."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from uuid import UUID

from app.models.enums import TxDirection
from app.services.categorization import normalize


@dataclass(frozen=True)
class ParsedTransaction:
    """Um lancamento extraido do arquivo, antes de virar registro no banco."""

    booked_on: date
    amount: Decimal            # sempre positivo; o sinal vive em `direction`
    direction: TxDirection
    description: str
    document: str | None = None       # FITID do OFX, numero do documento no CSV
    balance_after: Decimal | None = None
    raw_line: str = ""


@dataclass
class ParsedStatement:
    file_format: str
    transactions: list[ParsedTransaction] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    account_hint: str | None = None    # agencia/conta encontrada no arquivo

    @property
    def period_start(self) -> date | None:
        return min((t.booked_on for t in self.transactions), default=None)

    @property
    def period_end(self) -> date | None:
        return max((t.booked_on for t in self.transactions), default=None)


class StatementParseError(ValueError):
    """Arquivo ilegivel ou sem nenhum lancamento reconhecivel."""


def fingerprint(account_id: UUID, tx: ParsedTransaction) -> str:
    """Impressao digital estavel de um lancamento importado.

    Usa data, valor, direcao e a descricao normalizada. E o que impede a mesma
    linha de entrar duas vezes quando os extratos de dois meses se sobrepoem,
    ou quando o mesmo arquivo e enviado de novo.

    Nao entra no calculo: o texto original (que muda de acordo com o formato
    exportado) nem o saldo (que depende do que veio antes no extrato).
    """
    if tx.document:
        # quando o banco fornece um id proprio (FITID do OFX), ele e soberano
        base = f"{account_id}|doc|{tx.document}"
    else:
        base = "|".join(
            [
                str(account_id),
                tx.booked_on.isoformat(),
                f"{tx.amount:.2f}",
                tx.direction.value,
                normalize(tx.description),
            ]
        )
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:40]
