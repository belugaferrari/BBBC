"""Arvore de categorias multinivel, tags, fornecedores e regras de categorizacao."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, Date, Integer, Numeric, SmallInteger, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import UserDefinedType

from app.models.base import Base, PKUuid, TimestampMixin, pg_enum, uuid_fk
from app.models.enums import (
    CategoryKind,
    ExpenseNature,
    IncomeNature,
    IRDeductionType,
    IRTreatment,
    TxDirection,
)


class Ltree(UserDefinedType):
    """Tipo ltree do PostgreSQL (caminho materializado da arvore)."""

    cache_ok = True

    def get_col_spec(self, **kw: object) -> str:
        return "ltree"

    def bind_processor(self, dialect: object):
        return lambda value: value

    def result_processor(self, dialect: object, coltype: object):
        return lambda value: value


class Category(PKUuid, TimestampMixin, Base):
    """Profundidade ilimitada via `path` (ltree). `family_id NULL` = catalogo global."""

    __tablename__ = "categories"

    family_id: Mapped[UUID | None] = uuid_fk("families.id")
    parent_id: Mapped[UUID | None] = uuid_fk("categories.id")
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[CategoryKind] = mapped_column(
        pg_enum(CategoryKind, "category_kind"), nullable=False
    )
    path: Mapped[str] = mapped_column(Ltree, nullable=False)
    depth: Mapped[int] = mapped_column(SmallInteger, default=0)
    income_nature: Mapped[IncomeNature | None] = mapped_column(
        pg_enum(IncomeNature, "income_nature")
    )
    expense_nature: Mapped[ExpenseNature | None] = mapped_column(
        pg_enum(ExpenseNature, "expense_nature")
    )
    ir_treatment: Mapped[IRTreatment] = mapped_column(
        pg_enum(IRTreatment, "ir_treatment"), default=IRTreatment.NAO_APLICAVEL
    )
    ir_deduction_type: Mapped[IRDeductionType] = mapped_column(
        pg_enum(IRDeductionType, "ir_deduction_type"), default=IRDeductionType.NENHUMA
    )
    color: Mapped[str | None] = mapped_column(Text)
    icon: Mapped[str | None] = mapped_column(Text)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    children: Mapped[list["Category"]] = relationship(
        back_populates="parent", cascade="all, delete-orphan"
    )
    parent: Mapped["Category | None"] = relationship(
        back_populates="children", remote_side="Category.id"
    )


class Tag(PKUuid, Base):
    """Tag transacional livre (#ViagemPraia). Pode carregar orcamento e janela."""

    __tablename__ = "tags"

    family_id: Mapped[UUID] = uuid_fk("families.id", nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    color: Mapped[str | None] = mapped_column(Text)
    starts_on: Mapped[date | None] = mapped_column(Date)
    ends_on: Mapped[date | None] = mapped_column(Date)
    budget: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)


class Merchant(PKUuid, Base):
    __tablename__ = "merchants"

    family_id: Mapped[UUID | None] = uuid_fk("families.id")
    normalized_name: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    cnpj: Mapped[str | None] = mapped_column(Text)
    default_category_id: Mapped[UUID | None] = uuid_fk("categories.id")


class CategorizationRule(PKUuid, TimestampMixin, Base):
    """Regra de categorizacao. `is_learned` marca as regras criadas a partir de
    uma recategorizacao manual (o aprendizado de fornecedores)."""

    __tablename__ = "categorization_rules"

    family_id: Mapped[UUID] = uuid_fk("families.id", nullable=False)
    match_type: Mapped[str] = mapped_column(Text, default="CONTEM")
    pattern: Mapped[str] = mapped_column(Text, nullable=False)
    merchant_id: Mapped[UUID | None] = uuid_fk("merchants.id")
    account_id: Mapped[UUID | None] = uuid_fk("accounts.id")
    min_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    max_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    direction: Mapped[TxDirection | None] = mapped_column(pg_enum(TxDirection, "tx_direction"))
    category_id: Mapped[UUID] = uuid_fk("categories.id", nullable=False)
    apply_tag_id: Mapped[UUID | None] = uuid_fk("tags.id")
    ir_deduction_member_id: Mapped[UUID | None] = uuid_fk("members.id")
    priority: Mapped[int] = mapped_column(Integer, default=100)
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3), default=Decimal("0.5"))
    hit_count: Mapped[int] = mapped_column(Integer, default=0)
    last_hit_at: Mapped[date | None] = mapped_column(Date)
    is_learned: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[UUID | None] = uuid_fk("members.id")
