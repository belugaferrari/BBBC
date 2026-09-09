"""Parametros fiscais versionados por ano-calendario e resultado das apuracoes.

Nenhuma aliquota ou limite vive no codigo: tudo vem destas tabelas, para que a
virada de ano seja um INSERT e nao um deploy.
"""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, SmallInteger, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, PKUuid, uuid_fk


class TaxYear(Base):
    __tablename__ = "tax_years"

    year: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    # PROVISORIO enquanto os numeros nao foram conferidos contra a IN do ano
    status: Mapped[str] = mapped_column(Text, default="PROVISORIO")
    source_reference: Mapped[str | None] = mapped_column(Text)


class TaxBracket(PKUuid, Base):
    __tablename__ = "tax_brackets"

    year: Mapped[int] = mapped_column(SmallInteger, ForeignKey("tax_years.year"), nullable=False)
    scope: Mapped[str] = mapped_column(Text, nullable=False)  # MENSAL | ANUAL
    min_base: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    max_base: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    rate: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    deduction: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    valid_from: Mapped[date | None] = mapped_column(Date)


class TaxParameter(Base):
    __tablename__ = "tax_parameters"

    year: Mapped[int] = mapped_column(SmallInteger, ForeignKey("tax_years.year"), primary_key=True)
    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit: Mapped[str] = mapped_column(Text, default="BRL")
    description: Mapped[str | None] = mapped_column(Text)


class IRIncomeStatement(PKUuid, Base):
    """Informe de rendimentos da fonte pagadora, usado para conferir a apuracao."""

    __tablename__ = "ir_income_statements"

    family_id: Mapped[UUID] = uuid_fk("families.id", nullable=False)
    member_id: Mapped[UUID] = uuid_fk("members.id", nullable=False)
    year: Mapped[int] = mapped_column(SmallInteger, ForeignKey("tax_years.year"), nullable=False)
    payer_name: Mapped[str] = mapped_column(Text, nullable=False)
    payer_cnpj: Mapped[str | None] = mapped_column(Text)
    taxable_income: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    exempt_income: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    exclusive_taxed_income: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    withheld_tax: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    official_pension: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))


class IRAssessment(PKUuid, Base):
    """Cache auditavel do motor de calculo (breakdown guarda o memorial)."""

    __tablename__ = "ir_assessments"

    family_id: Mapped[UUID] = uuid_fk("families.id", nullable=False)
    member_id: Mapped[UUID] = uuid_fk("members.id", nullable=False)
    year: Mapped[int] = mapped_column(SmallInteger, ForeignKey("tax_years.year"), nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    taxable_income: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    total_deductions: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    calculation_base: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    tax_due: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    withheld_tax: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    balance: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    effective_rate: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    breakdown: Mapped[dict] = mapped_column(JSONB, default=dict)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
