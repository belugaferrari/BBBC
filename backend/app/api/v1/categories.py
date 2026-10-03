"""Arvore de categorias (profundidade ilimitada) e tags."""

import re
import unicodedata
from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Query, status
from pydantic import BaseModel
from sqlalchemy import select, text

from app.api.deps import CurrentMember, DbSession, owned_category, owned_member
from app.models import Category, Tag
from app.schemas.transactions import CategoryCreate, CategoryNode, CategoryOut, TagOut
from app.services.analise_categoria import analise, primeiro_do_mes

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
        icon=row.icon, color=row.color,
        requires_note=row.requires_note,
        counts_as_expense=row.counts_as_expense,
        counts_as_income=row.counts_as_income,
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


class CategoryUpdate(BaseModel):
    """O que da para mudar numa categoria depois de criada.

    O nome, sim. O `slug` e o `path`, nao - e nao e preguica. O caminho e a
    coluna que amarra a arvore: os filhos de 'despesas.transporte' tem o caminho
    do pai dentro do proprio caminho, e as regras de sugestao e os tetos apontam
    para a categoria pelo id, mas a soma da subarvore se faz pelo caminho. Trocar
    o caminho de uma categoria com filhos exigiria reescrever o de todos os
    descendentes na mesma transacao, e um erro no meio disso deixaria a arvore
    partida. Como o caminho nunca aparece na tela, renomear resolve tudo o que o
    usuario quer de fato.
    """

    name: str | None = None
    icon: str | None = None
    color: str | None = None
    requires_note: bool | None = None
    counts_as_expense: bool | None = None


@router.patch("/categories/{category_id}", response_model=CategoryOut)
def update_category(
    category_id: UUID, payload: CategoryUpdate, current: CurrentMember, db: DbSession
) -> CategoryOut:
    categoria = owned_category(db, category_id, current)
    mudancas = payload.model_dump(exclude_unset=True, exclude_none=True)
    for campo, valor in mudancas.items():
        setattr(categoria, campo, valor)
    db.flush()
    db.refresh(categoria)
    return _to_out(categoria)


@router.delete("/categories/{category_id}")
def delete_category(category_id: UUID, current: CurrentMember, db: DbSession) -> dict:
    """Apaga a categoria, ou a arquiva quando ha historico em cima dela.

    Apagar de verdade uma categoria que tem lancamento transformaria gasto
    classificado em gasto solto - e o estrago apareceria no fechamento do mes, nao
    agora. Nesse caso a categoria sai da tela (`is_archived`) e os lancamentos
    antigos continuam somando onde sempre somaram. Quando nao ha historico, o
    sumico e completo, que e o que a pessoa espera de "excluir".

    A subarvore vai junto nos dois casos: apagar 'Transporte' e deixar 'Gasolina'
    orfa nao e um estado que faca sentido.
    """
    categoria = owned_category(db, category_id, current)

    com_historico = db.execute(
        text(
            """
            SELECT count(*)
              FROM transactions t
              JOIN categories c ON c.id = t.category_id
             WHERE c.family_id = :familia
               AND c.path <@ (SELECT path FROM categories WHERE id = :id)
            """
        ),
        {"familia": current.family_id, "id": category_id},
    ).scalar_one()

    descendentes = db.execute(
        text(
            """
            SELECT count(*) FROM categories
             WHERE family_id = :familia
               AND path <@ (SELECT path FROM categories WHERE id = :id)
               AND id <> :id
            """
        ),
        {"familia": current.family_id, "id": category_id},
    ).scalar_one()

    if com_historico:
        db.execute(
            text(
                """
                UPDATE categories SET is_archived = true
                 WHERE family_id = :familia
                   AND path <@ (SELECT path FROM categories WHERE id = :id)
                """
            ),
            {"familia": current.family_id, "id": category_id},
        )
        db.flush()
        return {
            "arquivada": True,
            "nome": categoria.name,
            "subcategorias": int(descendentes),
            "lancamentos": int(com_historico),
            "aviso": (
                f"'{categoria.name}' saiu da tela, mas os {com_historico} lançamentos "
                "que já estavam nela continuam contando onde sempre contaram."
            ),
        }

    db.execute(
        text(
            """
            DELETE FROM categories
             WHERE family_id = :familia
               AND path <@ (SELECT path FROM categories WHERE id = :id)
            """
        ),
        {"familia": current.family_id, "id": category_id},
    )
    db.flush()
    return {
        "arquivada": False,
        "nome": categoria.name,
        "subcategorias": int(descendentes),
        "lancamentos": 0,
    }


@router.get("/categories/{category_id}/analise")
def category_analysis(
    category_id: UUID,
    current: CurrentMember,
    db: DbSession,
    month: date | None = None,
    member_id: UUID | None = None,
) -> dict:
    """Como esta categoria se comportou: no mes, contra a meta, contra o ano
    passado e contra os doze meses.

    Vale para qualquer categoria, de qualquer nivel - a mesma leitura serve para
    'Transporte' e para 'Gasolina', que e o que permite descer no detalhe quando
    o balde grande estoura e nao se sabe por que.
    """
    categoria = owned_category(db, category_id, current)
    if member_id:
        owned_member(db, member_id, current)

    mes = primeiro_do_mes(month or date.today())
    dados = analise(db, current.family_id, category_id, mes, member_id)

    filhas = db.scalars(
        select(Category)
        .where(
            Category.family_id == current.family_id,
            Category.parent_id == category_id,
            Category.is_archived.is_(False),
        )
        .order_by(Category.sort_order)
    ).all()

    return {
        "category": {
            "id": categoria.id,
            "name": categoria.name,
            "path": str(categoria.path),
            "depth": categoria.depth,
            "kind": categoria.kind,
            "icon": categoria.icon,
            "requires_note": categoria.requires_note,
            "counts_as_expense": categoria.counts_as_expense,
        },
        # Cada filha com o proprio numero do mes: "Transporte estourou" vira
        # "Transporte estourou por causa de Gasolina".
        "children": [
            {
                "id": filha.id,
                "name": filha.name,
                "icon": filha.icon,
                **{
                    chave: valor
                    for chave, valor in analise(
                        db, current.family_id, filha.id, mes, member_id
                    ).items()
                    if chave in ("spent", "transactions", "cap", "used_pct",
                                 "same_month_last_year", "monthly_average")
                },
            }
            for filha in filhas
        ],
        **dados,
    }


@router.get("/categories/resumo")
def category_overview(
    current: CurrentMember,
    db: DbSession,
    month: date | None = None,
    depth: int = Query(2, ge=1, le=6),
) -> dict:
    """A lista de categorias com meta e gasto do mes, para a tela de categorias.

    Uma consulta so, em vez de uma por categoria: com quinze categorias e mais
    subcategorias, uma chamada por linha faria a tela abrir em etapas visiveis.

    O gasto de cada linha ja inclui a subarvore dela, entao as linhas NAO podem
    ser somadas entre si - 'Transporte' ja contem 'Gasolina'. Os totais aqui
    somam so o nivel 1 (as quinze), que e a unica soma que fecha.
    """
    mes = primeiro_do_mes(month or date.today())

    linhas = db.execute(
        text(
            """
            WITH gasto AS (
                SELECT c.id AS category_id,
                       COALESCE(SUM(t.amount), 0) AS total,
                       COUNT(t.id)                AS lancamentos
                  FROM categories c
                  LEFT JOIN categories filha
                         ON filha.family_id = c.family_id AND filha.path <@ c.path
                  LEFT JOIN transactions t
                         ON t.category_id = filha.id
                        AND t.direction = 'SAIDA'
                        AND t.status IN ('EFETIVADA', 'CONCILIADA')
                        AND COALESCE(filha.counts_as_expense, true)
                        AND date_trunc('month', t.booked_on)
                            = date_trunc('month', CAST(:mes AS date))
                 WHERE c.family_id = :familia
                 GROUP BY c.id
            )
            SELECT c.id, c.parent_id, c.name, c.path::text AS path, c.depth,
                   c.kind::text AS kind, c.icon, c.counts_as_expense,
                   g.total AS spent, g.lancamentos AS transactions,
                   b.id AS cap_id, b.amount AS cap
              FROM categories c
              JOIN gasto g ON g.category_id = c.id
              LEFT JOIN budget_caps b
                     ON b.category_id = c.id
                    AND b.family_id = c.family_id
                    AND b.starts_on <= CAST(:mes AS date)
                    AND (b.ends_on IS NULL OR b.ends_on >= CAST(:mes AS date))
             WHERE c.family_id = :familia
               AND c.is_archived = false
               AND c.kind = 'DESPESA'
               AND nlevel(c.path) <= :niveis
             ORDER BY c.sort_order, c.path
            """
        ),
        {"familia": current.family_id, "mes": mes, "niveis": depth + 1},
    ).mappings().all()

    itens = [dict(linha) for linha in linhas]
    # O total soma so o segundo nivel (as quinze), ou as subcategorias entrariam
    # de novo no bolo e o mes dobraria.
    total_gasto = sum(
        (item["spent"] for item in itens if item["depth"] == 1), start=Decimal("0")
    )
    total_meta = sum(
        ((item["cap"] or Decimal("0")) for item in itens if item["depth"] == 1),
        start=Decimal("0"),
    )

    return {
        "month": mes,
        "total_spent": total_gasto,
        "total_cap": total_meta,
        "categories": itens,
    }
