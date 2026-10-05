"""Transacoes, rateios, vinculo com tags e lancamentos recorrentes."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, SmallInteger, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, PKUuid, TimestampMixin, pg_enum, uuid_fk
from app.models.enums import (
    IRDeductionType,
    IRTreatment,
    SocioFlow,
    TxDirection,
    TxSource,
    TxStatus,
)


class Transaction(PKUuid, TimestampMixin, Base):
    __tablename__ = "transactions"

    family_id: Mapped[UUID] = uuid_fk("families.id", nullable=False)
    account_id: Mapped[UUID] = uuid_fk("accounts.id", nullable=False)
    owner_member_id: Mapped[UUID] = uuid_fk("members.id", nullable=False)
    category_id: Mapped[UUID | None] = uuid_fk("categories.id")
    merchant_id: Mapped[UUID | None] = uuid_fk("merchants.id")

    # Quando ACONTECEU: o dia da compra, o que esta no extrato, o que ele lembra.
    booked_on: Mapped[date] = mapped_column(Date, nullable=False)
    # Quando o DINHEIRO SAI da conta, e o mes que o Resumo conta. Em conta
    # corrente e o mesmo dia; no cartao e o vencimento da fatura que cobra a
    # compra. Ver app/services/caixa.py.
    #
    # O padrao e `booked_on` porque e a resposta certa para tudo que nao e
    # cartao - e porque uma coluna NOT NULL sem padrao transformaria qualquer
    # caminho esquecido num erro de banco no meio de uma gravacao. Quem sabe
    # mais (a importacao, o lancamento manual) passa o valor calculado.
    paid_on: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        default=lambda contexto: contexto.get_current_parameters()["booked_on"],
    )
    # sempre positivo; o sinal vem de `direction`
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    direction: Mapped[TxDirection] = mapped_column(
        pg_enum(TxDirection, "tx_direction"), nullable=False
    )
    currency: Mapped[str] = mapped_column(Text, default="BRL")

    description: Mapped[str] = mapped_column(Text, nullable=False)
    description_norm: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)

    status: Mapped[TxStatus] = mapped_column(
        pg_enum(TxStatus, "tx_status"), default=TxStatus.EFETIVADA
    )
    source: Mapped[TxSource] = mapped_column(
        pg_enum(TxSource, "tx_source"), default=TxSource.MANUAL
    )
    provider_tx_id: Mapped[str | None] = mapped_column(Text)
    provider_payload: Mapped[dict | None] = mapped_column(JSONB)

    installment_no: Mapped[int | None] = mapped_column(SmallInteger)
    installment_total: Mapped[int | None] = mapped_column(SmallInteger)
    installment_group: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))

    # Fronteira entre pessoa fisica e empresa. Ver SocioFlow.
    socio_flow: Mapped[SocioFlow | None] = mapped_column(
        pg_enum(SocioFlow, "socio_flow"), nullable=True
    )
    # Data do acerto. Preenchido com socio_flow = em aberto: e dai que sai a
    # lista de "a empresa me deve".
    settled_on: Mapped[date | None] = mapped_column(Date, nullable=True)

    transfer_pair_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("transactions.id")
    )

    # Quando NULL, o tratamento efetivo e herdado da categoria.
    ir_treatment_override: Mapped[IRTreatment | None] = mapped_column(
        pg_enum(IRTreatment, "ir_treatment")
    )
    ir_deduction_type_override: Mapped[IRDeductionType | None] = mapped_column(
        pg_enum(IRDeductionType, "ir_deduction_type")
    )
    ir_deduction_member_id: Mapped[UUID | None] = uuid_fk("members.id")
    ir_document_number: Mapped[str | None] = mapped_column(Text)
    ir_year: Mapped[int | None] = mapped_column(SmallInteger)

    # origem: lote de importacao de extrato
    import_id: Mapped[UUID | None] = uuid_fk("statement_imports.id")
    import_fingerprint: Mapped[str | None] = mapped_column(Text)
    # Identidade gerada pelo aplicativo antes de haver conexao: permite reenviar
    # a fila de lancamentos offline sem duplicar.
    client_key: Mapped[str | None] = mapped_column(Text)
    # Quem doou. O limite de isencao do ITCMD e por doador e por ano, entao somar
    # tudo num balde so nao responde a pergunta que importa.
    donor_id: Mapped[UUID | None] = uuid_fk("donors.id")
    # Para que a doacao foi dada. Permite abater do consumo da familia o que ela
    # cobriu: a escola paga pelos avos nao e gasto da casa.
    donation_for_category_id: Mapped[UUID | None] = uuid_fk("categories.id")
    # Numa ENTRADA de reembolso: o gasto que ela devolve. Doacao e dinheiro de
    # outra pessoa que chega; reembolso e dinheiro dele que volta - parecidos no
    # efeito, diferentes na origem, e por isso campos diferentes.
    reembolso_de_id: Mapped[UUID | None] = uuid_fk("transactions.id")

    applied_rule_id: Mapped[UUID | None] = uuid_fk("categorization_rules.id")
    auto_confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    reviewed_by: Mapped[UUID | None] = uuid_fk("members.id")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @property
    def signed_amount(self) -> Decimal:
        return -self.amount if self.direction == TxDirection.SAIDA else self.amount


class TransactionSplit(PKUuid, Base):
    __tablename__ = "transaction_splits"

    transaction_id: Mapped[UUID] = uuid_fk("transactions.id", nullable=False)
    category_id: Mapped[UUID] = uuid_fk("categories.id", nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    ir_deduction_member_id: Mapped[UUID | None] = uuid_fk("members.id")
    notes: Mapped[str | None] = mapped_column(Text)


class TransactionTag(Base):
    __tablename__ = "transaction_tags"

    transaction_id: Mapped[UUID] = uuid_fk("transactions.id", primary_key=True)
    tag_id: Mapped[UUID] = uuid_fk("tags.id", primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RecurringTransaction(PKUuid, Base):
    """Alimenta a projecao de fluxo de caixa dos proximos meses."""

    __tablename__ = "recurring_transactions"

    family_id: Mapped[UUID] = uuid_fk("families.id", nullable=False)
    account_id: Mapped[UUID | None] = uuid_fk("accounts.id")
    owner_member_id: Mapped[UUID] = uuid_fk("members.id", nullable=False)
    category_id: Mapped[UUID | None] = uuid_fk("categories.id")
    description: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    direction: Mapped[TxDirection] = mapped_column(
        pg_enum(TxDirection, "tx_direction"), nullable=False
    )
    rrule: Mapped[str] = mapped_column(Text, nullable=False)
    next_run_on: Mapped[date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[date | None] = mapped_column(Date)
    auto_post: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
