"""Arvore de categorias (profundidade ilimitada) e tags."""

import re
import unicodedata

from fastapi import APIRouter, status
from sqlalchemy import select

from app.api.deps import CurrentMember, DbSession, owned_category
from app.models import Category, Tag
from app.schemas.transactions import CategoryCreate, CategoryNode, CategoryOut, TagOut

router = APIRouter(tags=["taxonomia"])


def slugify(name: str) -> str:
    text = unicodedata.normalize("NFKD", name.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def _to_out(row: Category) -> CategoryOut:
    return CategoryOut(
        id=row.id, parent_id=row.parent_id, name=row.name, slug=row.slug,
        path=str(row.path), depth=row.depth, kind=row.kind,
        income_nature=row.income_nature, expense_nature=row.expense_nature,
        ir_treatment=row.ir_treatment, ir_deduction_type=row.ir_deduction_type,
        icon=row.icon, color=row.color, requires_note=row.requires_note,
    )


@router.get("/categories", response_model=list[CategoryNode])
def category_tree(current: CurrentMember, db: DbSession) -> list[CategoryNode]:
    """Devolve a arvore da familia, montada. O app renderiza recursivamente.

    So a copia da familia. O catalogo global (`family_id IS NULL`) e um modelo
    do qual cada familia recebe a sua copia na criacao - devolver os dois faria
    cada categoria aparecer duas vezes na tela, com ids diferentes. Ele so
    aparece como reserva, para uma familia que ainda nao tenha a sua copia.
    """
    rows = db.scalars(
        select(Category)
        .where(Category.family_id == current.family_id, Category.is_archived.is_(False))
        .order_by(Category.sort_order)
    ).all()

    if not rows:
        rows = db.scalars(
            select(Category)
            .where(Category.family_id.is_(None), Category.is_archived.is_(False))
            .order_by(Category.sort_order)
        ).all()

    nodes = {row.id: CategoryNode(**_to_out(row).model_dump(), children=[]) for row in rows}
    roots: list[CategoryNode] = []
    for row in rows:
        node = nodes[row.id]
        parent = nodes.get(row.parent_id) if row.parent_id else None
        (parent.children if parent else roots).append(node)
    return roots


@router.post("/categories", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
def create_category(payload: CategoryCreate, current: CurrentMember, db: DbSession) -> CategoryOut:
    if payload.parent_id:
        owned_category(db, payload.parent_id, current)

    row = Category(
        family_id=current.family_id,
        parent_id=payload.parent_id,
        slug=payload.slug or slugify(payload.name),
        name=payload.name,
        kind=payload.kind,
        income_nature=payload.income_nature,
        expense_nature=payload.expense_nature,
        ir_treatment=payload.ir_treatment,
        ir_deduction_type=payload.ir_deduction_type,
        icon=payload.icon,
        color=payload.color,
        # path/depth sao preenchidos pelo trigger categories_sync_path
        path=payload.slug or slugify(payload.name),
    )
    db.add(row)
    db.flush()
    db.refresh(row)
    return _to_out(row)


@router.get("/tags", response_model=list[TagOut])
def list_tags(current: CurrentMember, db: DbSession) -> list[Tag]:
    return list(
        db.scalars(
            select(Tag)
            .where(Tag.family_id == current.family_id, Tag.is_archived.is_(False))
            .order_by(Tag.name)
        ).all()
    )
