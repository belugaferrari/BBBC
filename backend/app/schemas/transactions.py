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
    requires_note: bool = False
    counts_as_expense: bool = True
    # false na doacao recebida: entra na conta, mas nao e renda da familia. A
    # tela usa isto para pedir quem doou e para que, em vez de tratar a entrada
    # como salario.
    counts_as_income: bool = True


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
    # Gerada pelo aplicativo quando o lancamento nasce, mesmo sem conexao.
    # Reenviar a fila com a mesma chave devolve o lancamento ja gravado em vez
    # de criar outro.
    client_key: str | None = None
    account_id: UUID
    # Quem e o responsavel pelo gasto. Opcional: quando vazio, assume o dono da
    # conta. Existe porque a conta pode ser conjunta e o gasto ser de um so -
    # e a visao "so eu" depende disso para fazer sentido.
    owner_member_id: UUID | None = None
    booked_on: date
    amount: Decimal = Field(gt=0)
    direction: TxDirection
    description: str
    category_id: UUID | None = None
    # A data de caixa NAO vem de fora: quem decide e o servidor, lendo o tipo da
    # conta e os dias da fatura (ver app/services/caixa.py). Deixar o cliente
    # mandar abriria a porta para um gasto de cartao contar no mes errado por
    # engano de uma tela - e o mes errado e invisivel depois de gravado.
    notes: str | None = None
    status: TxStatus = TxStatus.EFETIVADA
    tags: list[UUID] = Field(default_factory=list)
    installment_no: int | None = None
    installment_total: int | None = None
    ir_treatment_override: IRTreatment | None = None
    ir_deduction_type_override: IRDeductionType | None = None
    ir_deduction_member_id: UUID | None = None
    ir_document_number: str | None = None
    # Quem doou. O limite de isencao do ITCMD e por doador e por ano, entao a
    # doacao sem dono nao da para medir contra limite nenhum.
    donor_id: UUID | None = None
    # Para que a doacao foi dada. Permite abater do consumo da familia o que ela
    # cobriu - a escola paga pelos avos nao e gasto da casa.
    donation_for_category_id: UUID | None = None
    # Para uma ENTRADA de reembolso: qual gasto ela devolve. E o que permite
    # dizer quanto daquele gasto ja voltou, e nao abater mais do que foi gasto.
    reembolso_de_id: UUID | None = None


class TransactionUpdate(BaseModel):
    category_id: UUID | None = None
    owner_member_id: UUID | None = None
    description: str | None = None
    notes: str | None = None
    status: TxStatus | None = None
    ir_treatment_override: IRTreatment | None = None
    ir_deduction_type_override: IRDeductionType | None = None
    ir_deduction_member_id: UUID | None = None
    ir_document_number: str | None = None
    donor_id: UUID | None = None
    donation_for_category_id: UUID | None = None
    reembolso_de_id: UUID | None = None
    # dispara o aprendizado de regra de fornecedor
    learn_rule: bool = True


class TransactionOut(ORMModel):
    id: UUID
    account_id: UUID
    owner_member_id: UUID  # responsavel pelo gasto
    category_id: UUID | None
    booked_on: date
    # Quando o dinheiro sai da conta. Igual a `booked_on` em tudo que nao e
    # compra no cartao; no cartao, o vencimento da fatura que cobra a compra -
    # e e ESTE mes que o Resumo conta.
    paid_on: date
    amount: Decimal
    direction: TxDirection
    description: str
    status: TxStatus
    source: TxSource
    notes: str | None = None
    ir_deduction_member_id: UUID | None = None
    donor_id: UUID | None = None
    donation_for_category_id: UUID | None = None
    reembolso_de_id: UUID | None = None
    # "parcela 2 de 10": o que a tela precisa para dizer que esta compra ainda
    # vai aparecer em oito meses
    installment_no: int | None = None
    installment_total: int | None = None
    auto_confidence: Decimal | None = None
