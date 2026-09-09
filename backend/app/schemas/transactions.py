"""Schemas de lancamentos, categorias e tags."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import (
    CategoryKind,
    ExpenseNature,
    IncomeNature,
    IRDeductionType,
    IRTreatment,
    TxDirection,
    TxSource,
    TxStatus,
)
from app.schemas.common import ORMModel


class CategoryOut(ORMModel):
    id: UUID
    parent_id: UUID | None
    name: str
    slug: str
    path: str
    depth: int
    kind: CategoryKind
    income_nature: IncomeNature | None = None
    expense_nature: ExpenseNature | None = None
    ir_treatment: IRTreatment
    ir_deduction_type: IRDeductionType
    icon: str | None = None
    color: str | None = None


class CategoryNode(CategoryOut):
    children: list["CategoryNode"] = Field(default_factory=list)


class CategoryCreate(BaseModel):
    parent_id: UUID | None = None
    name: str
    slug: str | None = None
    kind: CategoryKind
    income_nature: IncomeNature | None = None
    expense_nature: ExpenseNature | None = None
    ir_treatment: IRTreatment = IRTreatment.NAO_APLICAVEL
    ir_deduction_type: IRDeductionType = IRDeductionType.NENHUMA
    icon: str | None = None
    color: str | None = None


class TagOut(ORMModel):
    id: UUID
    name: str
    color: str | None = None
    budget: Decimal | None = None


class TransactionCreate(BaseModel):
    account_id: UUID
    booked_on: date
    amount: Decimal = Field(gt=0)
    direction: TxDirection
    description: str
    category_id: UUID | None = None
    paid_on: date | None = None
    notes: str | None = None
    status: TxStatus = TxStatus.EFETIVADA
    tags: list[UUID] = Field(default_factory=list)
    installment_no: int | None = None
    installment_total: int | None = None
    ir_treatment_override: IRTreatment | None = None
    ir_deduction_type_override: IRDeductionType | None = None
    ir_deduction_member_id: UUID | None = None
    ir_document_number: str | None = None


class TransactionUpdate(BaseModel):
    category_id: UUID | None = None
    description: str | None = None
    notes: str | None = None
    status: TxStatus | None = None
    ir_treatment_override: IRTreatment | None = None
    ir_deduction_type_override: IRDeductionType | None = None
    ir_deduction_member_id: UUID | None = None
    ir_document_number: str | None = None
    # dispara o aprendizado de regra de fornecedor
    learn_rule: bool = True


class TransactionOut(ORMModel):
    id: UUID
    account_id: UUID
    owner_member_id: UUID
    category_id: UUID | None
    booked_on: date
    amount: Decimal
    direction: TxDirection
    description: str
    status: TxStatus
    source: TxSource
    notes: str | None = None
    ir_deduction_member_id: UUID | None = None
    auto_confidence: Decimal | None = None
