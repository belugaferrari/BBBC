"""Conciliacao: traz o extrato do provedor e concilia com o que ja existe.

Duas garantias:
  * idempotencia - `provider_tx_id` tem indice unico por conta, entao reprocessar
    o mesmo periodo nao duplica lancamento;
  * o lancamento manual vence - se o usuario ja digitou a compra, a transacao do
    banco e casada com ela em vez de criar uma segunda linha.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.openfinance.base import OpenFinanceProvider, ProviderTransaction
from app.models import Account, BankConnection, SyncLog, Transaction
from app.models.enums import TxSource, TxStatus
from app.services.categorization import normalize
from app.services.categorization_repository import autocategorize

# Janela de tolerancia para casar um lancamento manual com o do banco.
MATCH_WINDOW_DAYS = 3


def _find_manual_match(
    db: Session, account_id: UUID, tx: ProviderTransaction
) -> Transaction | None:
    window_start = tx.booked_on - timedelta(days=MATCH_WINDOW_DAYS)
    window_end = tx.booked_on + timedelta(days=MATCH_WINDOW_DAYS)
    return db.scalar(
        select(Transaction).where(
            Transaction.account_id == account_id,
            Transaction.provider_tx_id.is_(None),
            Transaction.source == TxSource.MANUAL,
            Transaction.amount == tx.amount,
            Transaction.direction == tx.direction,
            Transaction.booked_on.between(window_start, window_end),
        )
    )


def sync_connection(
    db: Session,
    connection: BankConnection,
    provider: OpenFinanceProvider,
    transactions: list[ProviderTransaction],
    accounts_synced: int = 0,
) -> SyncLog:
    """Aplica no banco o extrato ja obtido do provedor."""
    log = SyncLog(
        connection_id=connection.id,
        started_at=datetime.now(UTC),
        status="EXECUTANDO",
        accounts_synced=accounts_synced,
    )
    db.add(log)

    accounts = {
        account.provider_account_id: account
        for account in db.scalars(
            select(Account).where(Account.connection_id == connection.id)
        ).all()
    }

    created = updated = 0
    for item in transactions:
        account = accounts.get(item.provider_account_id)
        if account is None:
            continue

        existing = db.scalar(
            select(Transaction).where(
                Transaction.account_id == account.id,
                Transaction.provider_tx_id == item.provider_tx_id,
            )
        )
        if existing:
            existing.amount = item.amount
            existing.description = item.description
            existing.status = TxStatus.CONCILIADA
            updated += 1
            continue

        manual = _find_manual_match(db, account.id, item)
        if manual:
            # o usuario ja tinha lancado: apenas concilia
            manual.provider_tx_id = item.provider_tx_id
            manual.provider_payload = item.raw
            manual.status = TxStatus.CONCILIADA
            manual.source = TxSource.OPEN_FINANCE
            updated += 1
            continue

        tx = Transaction(
            family_id=connection.family_id,
            account_id=account.id,
            owner_member_id=account.owner_member_id,
            booked_on=item.booked_on,
            amount=item.amount,
            direction=item.direction,
            description=item.description,
            description_norm=normalize(item.description),
            status=TxStatus.CONCILIADA,
            source=TxSource.OPEN_FINANCE,
            provider_tx_id=item.provider_tx_id,
            provider_payload=item.raw,
            installment_no=item.installment_no,
            installment_total=item.installment_total,
            ir_year=item.booked_on.year,
        )
        autocategorize(db, connection.family_id, tx)
        db.add(tx)
        created += 1

    log.transactions_created = created
    log.transactions_updated = updated
    log.status = "SUCESSO"
    log.finished_at = datetime.now(UTC)
    connection.last_synced_at = log.finished_at
    db.flush()
    return log


def recompute_balance(db: Session, account: Account) -> Decimal:
    """Recalcula o saldo materializado a partir do razao."""
    rows = db.scalars(select(Transaction).where(Transaction.account_id == account.id)).all()
    balance = sum((tx.signed_amount for tx in rows), Decimal("0"))
    account.current_balance = balance
    return balance


def default_sync_window(connection: BankConnection, days: int = 90) -> tuple[date, date]:
    since = (connection.last_synced_at.date() if connection.last_synced_at
             else date.today() - timedelta(days=days))
    return since, date.today()
