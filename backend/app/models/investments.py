"""Custodia consolidada, evolucao patrimonial e series de indicadores."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, Date, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, PKUuid, pg_enum, uuid_fk
from app.models.enums import AssetClass, IRTreatment


class Asset(PKUuid, Base):
    __tablename__ = "assets"

    family_id: Mapped[UUID | None] = uuid_fk("families.id")
    symbol: Mapped[str | None] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    asset_class: Mapped[AssetClass] = mapped_column(
        pg_enum(AssetClass, "asset_class"), nullable=False
    )
    issuer: Mapped[str | None] = mapped_column(Text)
    benchmark_code: Mapped[str | None] = mapped_column(Text)
    # 1.1200 = 112% do CDI; 0.1250 = 12,5% a.a. no prefixado
    contracted_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    maturity_date: Mapped[date | None] = mapped_column(Date)
    is_ir_exempt: Mapped[bool] = mapped_column(Boolean, default=False)


class Position(PKUuid, Base):
    __tablename__ = "positions"

    family_id: Mapped[UUID] = uuid_fk("families.id", nullable=False)
    account_id: Mapped[UUID] = uuid_fk("accounts.id", nullable=False)
    asset_id: Mapped[UUID] = uuid_fk("assets.id", nullable=False)
    owner_member_id: Mapped[UUID] = uuid_fk("members.id", nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(24, 8), default=Decimal("0"))
    average_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    invested_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    market_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    opened_on: Mapped[date | None] = mapped_column(Date)
    closed_on: Mapped[date | None] = mapped_column(Date)
    provider_position_id: Mapped[str | None] = mapped_column(Text)


class PositionSnapshot(PKUuid, Base):
    __tablename__ = "position_snapshots"

    position_id: Mapped[UUID] = uuid_fk("positions.id", nullable=False)
    snapshot_on: Mapped[date] = mapped_column(Date, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    market_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    invested_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)


class InvestmentTransaction(PKUuid, Base):
    __tablename__ = "investment_transactions"

    position_id: Mapped[UUID] = uuid_fk("positions.id", nullable=False)
    transaction_id: Mapped[UUID | None] = uuid_fk("transactions.id")
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    traded_on: Mapped[date] = mapped_column(Date, nullable=False)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(24, 8))
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    gross_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    fees: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    withheld_tax: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    ir_treatment: Mapped[IRTreatment] = mapped_column(
        pg_enum(IRTreatment, "ir_treatment"), default=IRTreatment.EXCLUSIVA_FONTE
    )


class BenchmarkSeries(Base):
    """CDI, IPCA, SELIC, IBOV: variacao do periodo e indice acumulado."""

    __tablename__ = "benchmark_series"

    code: Mapped[str] = mapped_column(Text, primary_key=True)
    reference_on: Mapped[date] = mapped_column(Date, primary_key=True)
    period_rate: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False)
    index_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    source: Mapped[str | None] = mapped_column(Text)
