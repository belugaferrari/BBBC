"""Patrimonio nao financeiro: imoveis, terrenos e participacoes societarias."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, Date, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, PKUuid, TimestampMixin, pg_enum, uuid_fk
from app.models.enums import HoldingKind


class Holding(PKUuid, TimestampMixin, Base):
    """Um bem. Imovel, terreno e participacao sao a mesma coisa para o sistema
    e para a Receita: algo que voce possui, com valor de aquisicao e de hoje."""

    __tablename__ = "holdings"

    family_id: Mapped[UUID] = uuid_fk("families.id", nullable=False)
    owner_member_id: Mapped[UUID] = uuid_fk("members.id", nullable=False)
    kind: Mapped[HoldingKind] = mapped_column(
        pg_enum(HoldingKind, "holding_kind"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    acquired_on: Mapped[date | None] = mapped_column(Date)
    acquisition_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    current_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    # a Receita declara bem pelo custo de aquisicao, nao pelo valor de mercado
    ir_declared_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))

    company_cnpj: Mapped[str | None] = mapped_column(Text)
    ownership_percentage: Mapped[Decimal | None] = mapped_column(Numeric(7, 4))

    registration: Mapped[str | None] = mapped_column(Text)
    address: Mapped[str | None] = mapped_column(Text)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sold_on: Mapped[date | None] = mapped_column(Date)
    sale_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    notes: Mapped[str | None] = mapped_column(Text)

    @property
    def unrealized_gain(self) -> Decimal | None:
        """Valorizacao ainda nao realizada. So vira ganho de capital na venda."""
        if self.acquisition_value is None:
            return None
        return self.current_value - self.acquisition_value


class HoldingValuation(PKUuid, Base):
    """Reavaliacao. E o que permite ver o patrimonio evoluir, em vez de so ter
    o numero de hoje."""

    __tablename__ = "holding_valuations"

    holding_id: Mapped[UUID] = uuid_fk("holdings.id", nullable=False)
    valued_on: Mapped[date] = mapped_column(Date, nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    source: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
