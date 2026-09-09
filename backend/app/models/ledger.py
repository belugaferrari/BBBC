"""Transacoes, rateios, vinculo com tags e lancamentos recorrentes."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, SmallInteger, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, PKUuid, TimestampMixin, pg_enum, uuid_fk
from app.models.enums import IRDeductionType, IRTreatment, TxDirection, TxSource, TxStatus


class Transaction(PKUuid, TimestampMixin, Base):
    __tablename__ = "transactions"

    family_id: Mapped[UUID] = uuid_fk("families.id", nullable=False)
    account_id: Mapped[UUID] = uuid_fk("accounts.id", nullable=False)
    owner_member_id: Mapped[UUID] = uuid_fk("members.id", nullable=False)
    category_id: Mapped[UUID | None] = uuid_fk("categories.id")
    merchant_id: Mapped[UUID | None] = uuid_fk("merchants.id")

    booked_on: Mapped[date] = mapped_column(Date, nullable=False)
    paid_on: Mapped[date | None] = mapped_column(Date)
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
