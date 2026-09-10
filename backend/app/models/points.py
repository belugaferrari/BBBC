"""Pontos de cartao de credito."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, Date, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, PKUuid, TimestampMixin, uuid_fk


class CardProgram(PKUuid, TimestampMixin, Base):
    __tablename__ = "card_programs"

    family_id: Mapped[UUID] = uuid_fk("families.id", nullable=False)
    account_id: Mapped[UUID | None] = uuid_fk("accounts.id")
    name: Mapped[str] = mapped_column(Text, nullable=False)
    card_name: Mapped[str | None] = mapped_column(Text)

    # Cartao brasileiro costuma pontuar por DOLAR gasto, e nao por real:
    # `currency_basis` diz por unidade de que moeda os pontos sao contados.
    points_per_currency: Mapped[Decimal] = mapped_column(
        Numeric(10, 4), default=Decimal("0")
    )
    currency_basis: Mapped[str] = mapped_column(String(3), default="USD")

    balance: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    point_value_brl: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))

    expires_next_on: Mapped[date | None] = mapped_column(Date)
    expires_next_points: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text)

    @property
    def balance_value_brl(self) -> Decimal | None:
        """Quanto o saldo vale em dinheiro, pelo valor de referencia do ponto."""
        if self.point_value_brl is None:
            return None
        return (self.balance * self.point_value_brl).quantize(Decimal("0.01"))


class PointMovement(PKUuid, Base):
    __tablename__ = "point_movements"

    program_id: Mapped[UUID] = uuid_fk("card_programs.id", nullable=False)
    transaction_id: Mapped[UUID | None] = uuid_fk("transactions.id")
    moved_on: Mapped[date] = mapped_column(Date, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    # positivo entra, negativo sai
    points: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
