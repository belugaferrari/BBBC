"""Tetos de gasto por categoria e metas de longo prazo."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, Date, Numeric, SmallInteger, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, PKUuid, TimestampMixin, pg_enum, uuid_fk
from app.models.enums import GoalStatus, PeriodType


class BudgetCap(PKUuid, TimestampMixin, Base):
    """member_id NULL = teto familiar; preenchido = teto individual."""

    __tablename__ = "budget_caps"

    family_id: Mapped[UUID] = uuid_fk("families.id", nullable=False)
    category_id: Mapped[UUID] = uuid_fk("categories.id", nullable=False)
    member_id: Mapped[UUID | None] = uuid_fk("members.id")
    period: Mapped[PeriodType] = mapped_column(
        pg_enum(PeriodType, "period_type"), default=PeriodType.MENSAL
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    includes_descendants: Mapped[bool] = mapped_column(Boolean, default=True)
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[date | None] = mapped_column(Date)
    alert_at_pct: Mapped[Decimal] = mapped_column(Numeric(4, 3), default=Decimal("0.8"))


class Goal(PKUuid, TimestampMixin, Base):
    __tablename__ = "goals"

    family_id: Mapped[UUID] = uuid_fk("families.id", nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    target_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    target_date: Mapped[date] = mapped_column(Date, nullable=False)
    current_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    monthly_contribution: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    expected_annual_rate: Mapped[Decimal] = mapped_column(Numeric(6, 4), default=Decimal("0"))
    inflation_indexed: Mapped[bool] = mapped_column(Boolean, default=False)
    linked_account_id: Mapped[UUID | None] = uuid_fk("accounts.id")
    linked_tag_id: Mapped[UUID | None] = uuid_fk("tags.id")
    status: Mapped[GoalStatus] = mapped_column(
        pg_enum(GoalStatus, "goal_status"), default=GoalStatus.ATIVA
    )
    priority: Mapped[int] = mapped_column(SmallInteger, default=1)


class GoalContribution(PKUuid, Base):
    __tablename__ = "goal_contributions"

    goal_id: Mapped[UUID] = uuid_fk("goals.id", nullable=False)
    transaction_id: Mapped[UUID | None] = uuid_fk("transactions.id")
    member_id: Mapped[UUID | None] = uuid_fk("members.id")
    contributed_on: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
