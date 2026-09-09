"""Familia, membros, instituicoes, conexoes Open Finance e contas."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, Date, DateTime, Numeric, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, PKUuid, TimestampMixin, pg_enum, uuid_fk
from app.models.enums import AccountType, ConnectionStatus, MemberRole


class Family(PKUuid, TimestampMixin, Base):
    __tablename__ = "families"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    base_currency: Mapped[str] = mapped_column(String(3), default="BRL")
    timezone: Mapped[str] = mapped_column(Text, default="America/Sao_Paulo")

    members: Mapped[list["Member"]] = relationship(back_populates="family")


class Member(PKUuid, TimestampMixin, Base):
    """Felipe e Clarissa tem login; as filhas existem como DEPENDENTE (sem login),
    porque sao necessarias para as deducoes de saude e educacao no IR."""

    __tablename__ = "members"

    family_id: Mapped[UUID] = uuid_fk("families.id", nullable=False)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    nickname: Mapped[str | None] = mapped_column(Text)
    role: Mapped[MemberRole] = mapped_column(pg_enum(MemberRole, "member_role"), nullable=False)
    birth_date: Mapped[date | None] = mapped_column(Date)
    cpf: Mapped[str | None] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(Text, unique=True)
    password_hash: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_ir_dependent: Mapped[bool] = mapped_column(Boolean, default=False)
    ir_dependent_of: Mapped[UUID | None] = uuid_fk("members.id")

    family: Mapped[Family] = relationship(back_populates="members")

    @property
    def can_login(self) -> bool:
        return self.password_hash is not None and self.is_active


class Institution(PKUuid, Base):
    __tablename__ = "institutions"

    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    ispb: Mapped[str | None] = mapped_column(Text)
    provider_ref: Mapped[str | None] = mapped_column(Text)
    logo_url: Mapped[str | None] = mapped_column(Text)


class BankConnection(PKUuid, TimestampMixin, Base):
    """Vinculo com o provedor de Open Finance. Credenciais bancarias nunca sao
    persistidas aqui: guardamos apenas o id do item/link no provedor."""

    __tablename__ = "bank_connections"

    family_id: Mapped[UUID] = uuid_fk("families.id", nullable=False)
    owner_member_id: Mapped[UUID] = uuid_fk("members.id", nullable=False)
    institution_id: Mapped[UUID | None] = uuid_fk("institutions.id")
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    provider_item_id: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ConnectionStatus] = mapped_column(
        pg_enum(ConnectionStatus, "connection_status"), default=ConnectionStatus.CRIADA
    )
    consent_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    connection_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)


class Account(PKUuid, TimestampMixin, Base):
    __tablename__ = "accounts"

    family_id: Mapped[UUID] = uuid_fk("families.id", nullable=False)
    owner_member_id: Mapped[UUID] = uuid_fk("members.id", nullable=False)
    institution_id: Mapped[UUID | None] = uuid_fk("institutions.id")
    connection_id: Mapped[UUID | None] = uuid_fk("bank_connections.id")
    name: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[AccountType] = mapped_column(pg_enum(AccountType, "account_type"), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="BRL")
    current_balance: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    credit_limit: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    statement_close_day: Mapped[int | None] = mapped_column(SmallInteger)
    statement_due_day: Mapped[int | None] = mapped_column(SmallInteger)
    provider_account_id: Mapped[str | None] = mapped_column(Text)
    is_shared: Mapped[bool] = mapped_column(Boolean, default=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
