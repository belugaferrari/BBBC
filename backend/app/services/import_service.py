"""Importacao de extrato: pre-visualizar, conferir, so entao gravar.

O fluxo tem dois passos de proposito. Um arquivo de banco pode vir com leiaute
inesperado, com o mesmo periodo que voce ja importou, ou com lancamentos que
voce ja digitou a mao. Gravar direto seria a maneira mais rapida de sujar a
base - e sujeira em base financeira custa horas de conferencia depois.

Passo 1 (`build_preview`): le o arquivo, marca o que ja existe e sugere
categoria. Nao grava nenhum lancamento.
Passo 2 (`confirm_import`): grava o que o usuario escolheu.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, Category, StatementImport, Transaction
from app.models.enums import TxDirection, TxSource, TxStatus
from app.services.categorization import (
    Rule,
    TransactionFacts,
    categorize,
    normalize,
)
from app.services.categorization_repository import load_rules
from app.services.importers.base import ParsedTransaction, fingerprint
from app.services.importers.detect import parse_statement

# Mesma janela da conciliacao do Open Finance: o banco publica alguns dias
# depois da compra, entao o lancamento manual pode estar deslocado.
MANUAL_MATCH_WINDOW_DAYS = 3

_SOURCE_BY_FORMAT = {
    "OFX": TxSource.IMPORT_OFX,
    "CSV": TxSource.IMPORT_CSV,
    "PDF": TxSource.IMPORT_PDF,
}


def _find_equivalent(db: Session, account_id: UUID, tx: ParsedTransaction) -> Transaction | None:
    """Lancamento que ja existe e corresponde a esta linha, venha de onde vier.

    Cobre os dois casos que acontecem de verdade: voce digitou a compra a mao, e
    voce ja importou o mesmo periodo em outro formato (o OFX traz FITID e o CSV
    nao, entao a impressao digital muda e so a equivalencia salva).
    """
    return db.scalar(
        select(Transaction).where(
            Transaction.account_id == account_id,
            Transaction.amount == tx.amount,
            Transaction.direction == tx.direction,
            Transaction.booked_on.between(
                tx.booked_on - timedelta(days=MANUAL_MATCH_WINDOW_DAYS),
                tx.booked_on + timedelta(days=MANUAL_MATCH_WINDOW_DAYS),
            ),
        )
    )


def build_preview(
    db: Session,
    *,
    family_id: UUID,
    account: Account,
    member_id: UUID,
    filename: str,
    content: bytes,
) -> StatementImport:
    """Le o arquivo e monta a tela de conferencia. Nao grava lancamento algum."""
    statement = parse_statement(filename, content)
    file_hash = hashlib.sha256(content).hexdigest()

    already = db.scalar(
        select(StatementImport).where(
            StatementImport.account_id == account.id,
            StatementImport.file_hash == file_hash,
            StatementImport.status == "CONFIRMADO",
        )
    )

    rules: list[Rule] = load_rules(db, family_id)
    category_names = {
        row.id: row.name
        for row in db.scalars(
            select(Category).where(Category.family_id.in_([family_id, None]))
        ).all()
    }

    preview: list[dict] = []
    duplicates = 0

    for index, tx in enumerate(statement.transactions):
        digital = fingerprint(account.id, tx)

        existing = db.scalar(
            select(Transaction).where(
                Transaction.account_id == account.id,
                Transaction.import_fingerprint == digital,
            )
        )
        equivalent = None if existing else _find_equivalent(db, account.id, tx)
        duplicate_reason = None
        if existing:
            duplicate_reason = "ja importado antes"
        elif equivalent is not None:
            duplicate_reason = (
                "ja importado em outro formato"
                if equivalent.import_id is not None
                else "voce ja lancou este valor a mao"
            )
        if duplicate_reason:
            duplicates += 1

        match = categorize(
            TransactionFacts(
                description=tx.description,
                amount=tx.amount,
                direction=tx.direction,
                account_id=account.id,
            ),
            rules,
        )

        preview.append(
            {
                "index": index,
                "booked_on": tx.booked_on.isoformat(),
                "amount": str(tx.amount),
                "direction": tx.direction.value,
                "description": tx.description,
                "document": tx.document,
                "fingerprint": digital,
                "duplicate": duplicate_reason is not None,
                "duplicate_reason": duplicate_reason,
                "matched_transaction_id": str(equivalent.id) if equivalent else None,
                "suggested_category_id": str(match.category_id) if match else None,
                "suggested_category_name": (
                    category_names.get(match.category_id) if match else None
                ),
                "confidence": str(match.confidence) if match else None,
                # marcado por padrao: o que nao e duplicado entra
                "selected": duplicate_reason is None,
            }
        )

    warnings = list(statement.warnings)
    if already:
        warnings.insert(
            0,
            f"Este mesmo arquivo ja foi importado em "
            f"{already.confirmed_at:%d/%m/%Y}. Os lancamentos repetidos estao desmarcados.",
        )

    row = StatementImport(
        family_id=family_id,
        account_id=account.id,
        uploaded_by=member_id,
        filename=filename or "extrato",
        file_format=statement.file_format,
        file_hash=file_hash,
        file_size=len(content),
        status="CRIADO",
        period_start=statement.period_start,
        period_end=statement.period_end,
        rows_detected=len(statement.transactions),
        rows_duplicated=duplicates,
        preview=preview,
        warnings=warnings,
        created_at=datetime.now(UTC),
    )
    db.add(row)
    db.flush()
    return row


def confirm_import(
    db: Session,
    row: StatementImport,
    *,
    selected_indexes: list[int] | None = None,
    category_overrides: dict[int, UUID] | None = None,
) -> StatementImport:
    """Grava os lancamentos escolhidos na tela de conferencia."""
    if row.status == "CONFIRMADO":
        raise ValueError("esta importacao ja foi confirmada")

    account = db.get(Account, row.account_id)
    overrides = category_overrides or {}
    chosen = (
        set(selected_indexes)
        if selected_indexes is not None
        else {item["index"] for item in row.preview if item["selected"]}
    )

    created = 0
    for item in row.preview:
        index = item["index"]
        if index not in chosen:
            continue

        # A guarda final e o indice unico em (account_id, import_fingerprint):
        # mesmo com duas confirmacoes simultaneas, a linha nao duplica.
        if db.scalar(
            select(Transaction).where(
                Transaction.account_id == account.id,
                Transaction.import_fingerprint == item["fingerprint"],
            )
        ):
            continue

        category_id = overrides.get(index) or (
            UUID(item["suggested_category_id"]) if item["suggested_category_id"] else None
        )
        description = item["description"]

        db.add(
            Transaction(
                family_id=row.family_id,
                account_id=account.id,
                owner_member_id=account.owner_member_id,
                category_id=category_id,
                booked_on=datetime.fromisoformat(item["booked_on"]).date(),
                amount=Decimal(item["amount"]),
                direction=TxDirection(item["direction"]),
                description=description,
                description_norm=normalize(description),
                status=TxStatus.EFETIVADA,
                source=_SOURCE_BY_FORMAT[row.file_format],
                import_id=row.id,
                import_fingerprint=item["fingerprint"],
                ir_year=datetime.fromisoformat(item["booked_on"]).year,
                auto_confidence=Decimal(item["confidence"]) if item["confidence"] else None,
            )
        )
        created += 1

    row.rows_imported = created
    row.status = "CONFIRMADO"
    row.confirmed_at = datetime.now(UTC)
    db.flush()

    recompute_account_balance(db, account)
    return row


def recompute_account_balance(db: Session, account: Account) -> Decimal:
    """Recalcula o saldo materializado a partir do razao da conta."""
    rows = db.scalars(
        select(Transaction).where(
            Transaction.account_id == account.id,
            Transaction.status.in_([TxStatus.EFETIVADA, TxStatus.CONCILIADA]),
        )
    ).all()
    balance = sum((tx.signed_amount for tx in rows), Decimal("0"))
    account.current_balance = balance
    db.flush()
    return balance
