"""Lancamentos: listagem com filtros individual/familiar, criacao e correcao."""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import and_, select

from app.api.deps import CurrentMember, DbSession, scope_member_id
from app.models import Category, Transaction, TransactionTag
from app.models.enums import TxStatus
from app.schemas.transactions import TransactionCreate, TransactionOut, TransactionUpdate
from app.services.categorization_repository import apply_correction, autocategorize

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
        category = db.get(Category, category_id)
        if not category:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Categoria nao encontrada")
        subtree = select(Category.id).where(Category.path.op("<@")(category.path))
        filters.append(Transaction.category_id.in_(subtree))
    if tag_id:
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


@router.post("", response_model=TransactionOut, status_code=status.HTTP_201_CREATED)
def create_transaction(
    payload: TransactionCreate, current: CurrentMember, db: DbSession
) -> Transaction:
    """Insercao manual. A categorizacao automatica roda mesmo aqui - o usuario
    so precisa confirmar quando o motor errar."""
    tx = Transaction(
        family_id=current.family_id,
        owner_member_id=current.id,
        ir_year=payload.booked_on.year,
        **payload.model_dump(exclude={"tags"}),
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

    data = payload.model_dump(exclude_unset=True, exclude={"learn_rule", "category_id"})
    for field, value in data.items():
        setattr(tx, field, value)

    if payload.category_id and payload.category_id != tx.category_id:
        apply_correction(
            db, current.family_id, tx, payload.category_id, current.id, learn=payload.learn_rule
        )
    db.flush()
    return tx
