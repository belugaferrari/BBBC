"""Lancamentos: listagem com filtros individual/familiar, criacao e correcao."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import and_, select

from app.api.deps import (
    CurrentMember,
    DbSession,
    owned_account,
    owned_category,
    owned_member,
    owned_tag,
    scope_member_id,
)
from app.models import Category, Transaction, TransactionTag
from app.models.enums import TxStatus
from app.schemas.transactions import TransactionCreate, TransactionOut, TransactionUpdate
from app.services.categorization_repository import apply_correction, autocategorize
from app.services.queries import spend_by_category, spend_by_member

router = APIRouter(prefix="/transactions", tags=["gastos"])


@router.get("", response_model=list[TransactionOut])
def list_transactions(
    current: CurrentMember,
    db: DbSession,
    start: date,
    end: date,
    scope: str = Query("familia", pattern="^(familia|individual)$"),
    category_id: UUID | None = None,
    tag_id: UUID | None = None,
    search: str | None = None,
    only_uncategorized: bool = False,
    limit: int = Query(200, le=1000),
    offset: int = 0,
) -> list[Transaction]:
    filters = [
        Transaction.family_id == current.family_id,
        Transaction.booked_on.between(start, end),
        Transaction.status != TxStatus.IGNORADA,
    ]
    owner = scope_member_id(current, scope)
    if owner:
        filters.append(Transaction.owner_member_id == owner)
    if only_uncategorized:
        filters.append(Transaction.category_id.is_(None))
    if search:
        filters.append(Transaction.description.ilike(f"%{search}%"))
    if category_id:
        # inclui a subarvore da categoria escolhida
        category = owned_category(db, category_id, current)
        subtree = select(Category.id).where(Category.path.op("<@")(category.path))
        filters.append(Transaction.category_id.in_(subtree))
    if tag_id:
        owned_tag(db, tag_id, current)
        tagged = select(TransactionTag.transaction_id).where(TransactionTag.tag_id == tag_id)
        filters.append(Transaction.id.in_(tagged))

    return list(
        db.scalars(
            select(Transaction)
            .where(and_(*filters))
            .order_by(Transaction.booked_on.desc(), Transaction.created_at.desc())
            .limit(limit)
            .offset(offset)
        ).all()
    )


@router.get("/by-category")
def by_category(
    current: CurrentMember,
    db: DbSession,
    start: date,
    end: date,
    scope: str = Query("familia", pattern="^(familia|individual)$"),
    depth: int = Query(2, ge=1, le=6),
    member_id: UUID | None = None,
) -> dict:
    """Gastos do periodo somados por categoria, no nivel de detalhe pedido.

    `depth` escolhe o corte da arvore: 1 agrupa nos grandes blocos, 2 desce um
    nivel, e assim por diante. `member_id` responde 'quanto a Clarissa gastou'.
    """
    if member_id:
        owned_member(db, member_id, current)
        alvo = member_id
    else:
        alvo = scope_member_id(current, scope)

    grupos = spend_by_category(db, current.family_id, start, end, alvo, depth)
    return {
        "start": start,
        "end": end,
        "depth": depth,
        "total": sum((g["total"] for g in grupos), Decimal("0")),
        "categories": grupos,
        "by_member": spend_by_member(db, current.family_id, start, end),
    }


@router.post("", response_model=TransactionOut, status_code=status.HTTP_201_CREATED)
def create_transaction(
    payload: TransactionCreate, current: CurrentMember, db: DbSession
) -> Transaction:
    """Insercao manual. A categorizacao automatica roda mesmo aqui - o usuario
    so precisa confirmar quando o motor errar."""
    account = owned_account(db, payload.account_id, current)
    if payload.category_id:
        owned_category(db, payload.category_id, current)
    if payload.ir_deduction_member_id:
        owned_member(db, payload.ir_deduction_member_id, current)
    if payload.owner_member_id:
        owned_member(db, payload.owner_member_id, current)
    for tag_id in payload.tags:
        owned_tag(db, tag_id, current)

    tx = Transaction(
        family_id=current.family_id,
        # sem responsavel informado, o gasto e de quem e a conta
        ir_year=payload.booked_on.year,
        **payload.model_dump(exclude={"tags", "owner_member_id"}),
        owner_member_id=payload.owner_member_id or account.owner_member_id,
    )
    if not tx.category_id:
        autocategorize(db, current.family_id, tx)
    db.add(tx)
    db.flush()

    for tag_id in payload.tags:
        db.add(TransactionTag(transaction_id=tx.id, tag_id=tag_id))
    db.flush()
    return tx


@router.patch("/{transaction_id}", response_model=TransactionOut)
def update_transaction(
    transaction_id: UUID, payload: TransactionUpdate, current: CurrentMember, db: DbSession
) -> Transaction:
    """Corrigir a categoria aqui alimenta o aprendizado de regras de fornecedor."""
    tx = db.get(Transaction, transaction_id)
    if not tx or tx.family_id != current.family_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lancamento nao encontrado")

    if payload.ir_deduction_member_id:
        owned_member(db, payload.ir_deduction_member_id, current)
    if payload.owner_member_id:
        owned_member(db, payload.owner_member_id, current)

    data = payload.model_dump(exclude_unset=True, exclude={"learn_rule", "category_id"})
    for field, value in data.items():
        setattr(tx, field, value)

    if payload.category_id and payload.category_id != tx.category_id:
        owned_category(db, payload.category_id, current)
        apply_correction(
            db, current.family_id, tx, payload.category_id, current.id, learn=payload.learn_rule
        )
    db.flush()
    return tx
