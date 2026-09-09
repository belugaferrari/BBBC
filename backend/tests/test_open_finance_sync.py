"""Conciliacao do Open Finance com um provedor falso.

Cobre o que mais dói num app de finanças: lançamento duplicado. O provedor
falso devolve o mesmo extrato duas vezes e uma compra que o usuário já tinha
digitado à mão.
"""

from __future__ import annotations

import os
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("BBBC_TEST_DATABASE_URL"),
    reason="defina BBBC_TEST_DATABASE_URL para rodar a integracao",
)


@pytest.fixture
def cenario():
    from sqlalchemy import select

    from app.cli import seed_family
    from app.db.session import SessionLocal
    from app.models import BankConnection, Member
    from app.models.enums import ConnectionStatus

    suffix = uuid.uuid4().hex[:8]
    family_id = seed_family(
        name=f"Familia {suffix}",
        titular="Felipe",
        titular_email=f"felipe.of.{suffix}@exemplo.com",
        titular_password="segredo-de-teste",
        conjuge=None,
        conjuge_email=None,
        conjuge_password=None,
        dependentes=[],
    )
    db = SessionLocal()
    titular = db.scalar(select(Member).where(Member.family_id == family_id))
    connection = BankConnection(
        family_id=family_id,
        owner_member_id=titular.id,
        provider="pluggy",
        provider_item_id=f"item-{suffix}",
        status=ConnectionStatus.ATIVA,
    )
    db.add(connection)
    db.flush()
    yield db, connection, titular
    db.rollback()
    db.close()


def _extrato(hoje: date):
    from app.integrations.openfinance.base import ProviderAccount, ProviderTransaction
    from app.models.enums import AccountType, TxDirection

    contas = [
        ProviderAccount(
            provider_account_id="acc-1",
            name="Conta corrente",
            type=AccountType.CONTA_CORRENTE,
            balance=Decimal("12500.00"),
        ),
        ProviderAccount(
            provider_account_id="acc-2",
            name="Cartao",
            type=AccountType.CARTAO_CREDITO,
            balance=Decimal("-3200.00"),
            credit_limit=Decimal("30000.00"),
        ),
    ]
    lancamentos = [
        ProviderTransaction(
            provider_tx_id="tx-1",
            provider_account_id="acc-1",
            booked_on=hoje,
            amount=Decimal("28000.00"),
            direction=TxDirection.ENTRADA,
            description="PRO LABORE CHECKMOTOR",
        ),
        ProviderTransaction(
            provider_tx_id="tx-2",
            provider_account_id="acc-2",
            booked_on=hoje,
            amount=Decimal("890.00"),
            direction=TxDirection.SAIDA,
            description="COMPRA CARTAO BAMBU LAB",
        ),
    ]
    return contas, lancamentos


def test_primeira_sincronizacao_cria_as_contas_do_provedor(cenario):
    from app.services.open_finance_sync import sync_connection

    db, connection, _ = cenario
    contas, lancamentos = _extrato(date.today())

    log = sync_connection(db, connection, provider=None, transactions=lancamentos,
                          provider_accounts=contas)

    assert log.accounts_synced == 2
    assert log.transactions_created == 2
    assert log.status == "SUCESSO"

    from sqlalchemy import select

    from app.models import Account

    criadas = db.scalars(
        select(Account).where(Account.connection_id == connection.id)
    ).all()
    assert {a.provider_account_id for a in criadas} == {"acc-1", "acc-2"}
    cartao = next(a for a in criadas if a.provider_account_id == "acc-2")
    assert cartao.credit_limit == Decimal("30000.00")


def test_reprocessar_o_mesmo_periodo_nao_duplica(cenario):
    from sqlalchemy import func, select

    from app.models import Transaction
    from app.services.open_finance_sync import sync_connection

    db, connection, _ = cenario
    contas, lancamentos = _extrato(date.today())

    sync_connection(db, connection, None, lancamentos, provider_accounts=contas)
    segundo = sync_connection(db, connection, None, lancamentos, provider_accounts=contas)

    assert segundo.transactions_created == 0
    assert segundo.transactions_updated == 2

    total = db.scalar(
        select(func.count()).select_from(Transaction).where(
            Transaction.family_id == connection.family_id
        )
    )
    assert total == 2


def test_lancamento_manual_e_conciliado_em_vez_de_duplicado(cenario):
    from sqlalchemy import func, select

    from app.models import Account, Transaction
    from app.models.enums import TxDirection, TxSource, TxStatus
    from app.services.open_finance_sync import sync_connection, upsert_accounts

    db, connection, titular = cenario
    hoje = date.today()
    contas, lancamentos = _extrato(hoje)
    upsert_accounts(db, connection, contas)

    cartao = db.scalar(
        select(Account).where(Account.provider_account_id == "acc-2")
    )
    # o usuario digitou a compra dois dias antes de o banco publicar
    db.add(
        Transaction(
            family_id=connection.family_id,
            account_id=cartao.id,
            owner_member_id=titular.id,
            booked_on=hoje - timedelta(days=2),
            amount=Decimal("890.00"),
            direction=TxDirection.SAIDA,
            description="Filamento Bambu Lab",
            source=TxSource.MANUAL,
            status=TxStatus.EFETIVADA,
        )
    )
    db.flush()

    log = sync_connection(db, connection, None, lancamentos, provider_accounts=contas)

    assert log.transactions_created == 1   # so o pro-labore
    assert log.transactions_updated == 1   # a compra foi conciliada

    total = db.scalar(
        select(func.count()).select_from(Transaction).where(
            Transaction.family_id == connection.family_id
        )
    )
    assert total == 2

    conciliada = db.scalar(
        select(Transaction).where(Transaction.provider_tx_id == "tx-2")
    )
    assert conciliada.description == "Filamento Bambu Lab"  # o texto do usuario permanece
    assert conciliada.status == TxStatus.CONCILIADA


def test_transacao_de_conta_desconhecida_deixa_rastro(cenario):
    from app.services.open_finance_sync import sync_connection

    db, connection, _ = cenario
    contas, lancamentos = _extrato(date.today())

    # o provedor lista so a primeira conta, mas manda extrato das duas
    log = sync_connection(db, connection, None, lancamentos, provider_accounts=contas[:1])

    assert log.transactions_created == 1
    assert "conta nao encontrada" in log.error_message
    assert "acc-2" in log.error_message
