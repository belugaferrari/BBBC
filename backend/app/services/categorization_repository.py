"""Carga e persistencia das regras de categorizacao."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CategorizationRule, Category, Transaction
from app.models.enums import TxDirection
from app.services.categorization import (
    Rule,
    TransactionFacts,
    categorize,
    learn_from_correction,
    normalize,
    reinforce,
)


def _to_rule(row: CategorizationRule) -> Rule:
    return Rule(
        id=row.id,
        pattern=row.pattern,
        category_id=row.category_id,
        match_type=row.match_type,
        direction=row.direction,
        account_id=row.account_id,
        min_amount=row.min_amount,
        max_amount=row.max_amount,
        apply_tag_id=row.apply_tag_id,
        ir_deduction_member_id=row.ir_deduction_member_id,
        priority=row.priority,
        confidence=Decimal(row.confidence),
        hit_count=row.hit_count,
        is_learned=row.is_learned,
    )


# Onde vai o lancamento que nenhuma regra reconheceu, por direcao.
#
# Nao e so um rotulo bonito para "sem categoria". Categoria nula sai da soma por
# categoria (que nasce de um JOIN com `categories`) e continua no fluxo do mes
# (que soma lancamento direto) - o painel acusava "gastou R$ 5.000" com a lista
# somando R$ 4.200 e nenhuma linha explicando a diferenca. Com categoria de
# verdade, o pendente aparece com nome e total, impossivel de nao ver.
_A_DEFINIR = {
    TxDirection.SAIDA: "despesas.a_definir",
    TxDirection.ENTRADA: "receitas.a_definir",
}


def categoria_a_definir(
    db: Session, family_id: UUID, direction: TxDirection | str
) -> UUID | None:
    """A categoria "A definir" da familia para aquela direcao.

    Devolve None para TRANSFERENCIA (que nao e gasto nem receita: pedir uma
    categoria para "pagamento de fatura" seria pedir uma decisao que nao existe)
    e tambem quando a familia e de antes da migration que criou a categoria - ai
    o comportamento volta a ser o antigo, que e pior, mas nao quebra nada.
    """
    caminho = _A_DEFINIR.get(TxDirection(direction))
    if not caminho:
        return None
    return db.scalar(
        select(Category.id).where(
            Category.family_id == family_id,
            Category.path == caminho,
        )
    )


def load_rules(db: Session, family_id: UUID) -> list[Rule]:
    rows = db.scalars(
        select(CategorizationRule).where(CategorizationRule.family_id == family_id)
    ).all()
    return [_to_rule(r) for r in rows]


def autocategorize(db: Session, family_id: UUID, tx: Transaction) -> Transaction:
    """Aplica a melhor regra disponivel.

    Sem regra que reconheca, o lancamento vai para "A definir" em vez de ficar
    sem categoria - ver o comentario de `categoria_a_definir`.
    """
    tx.description_norm = normalize(tx.description)
    match = categorize(
        TransactionFacts(
            description=tx.description,
            amount=tx.amount,
            direction=TxDirection(tx.direction),
            account_id=tx.account_id,
        ),
        load_rules(db, family_id),
    )
    if not match:
        tx.category_id = categoria_a_definir(db, family_id, tx.direction)
        return tx

    tx.category_id = match.category_id
    tx.applied_rule_id = match.rule.id
    tx.auto_confidence = match.confidence
    if match.ir_deduction_member_id and not tx.ir_deduction_member_id:
        tx.ir_deduction_member_id = match.ir_deduction_member_id

    if match.rule.id:
        row = db.get(CategorizationRule, match.rule.id)
        if row:
            updated = reinforce(match.rule)
            row.confidence = updated.confidence
            row.hit_count = updated.hit_count
            row.last_hit_at = datetime.now(UTC).date()
    return tx


def apply_correction(
    db: Session,
    family_id: UUID,
    tx: Transaction,
    new_category_id: UUID,
    corrected_by: UUID,
    *,
    learn: bool = True,
) -> CategorizationRule | None:
    """Grava a correcao e, se pedido, transforma-a em regra de fornecedor."""
    tx.category_id = new_category_id
    tx.reviewed_by = corrected_by
    tx.reviewed_at = datetime.now(UTC)
    if not learn:
        return None

    existing = load_rules(db, family_id)
    new_rule, weakened = learn_from_correction(
        TransactionFacts(
            description=tx.description,
            amount=tx.amount,
            direction=TxDirection(tx.direction),
            account_id=tx.account_id,
        ),
        new_category_id,
        existing,
        ir_deduction_member_id=tx.ir_deduction_member_id,
    )

    for rule in weakened:
        if rule.id:
            row = db.get(CategorizationRule, rule.id)
            if row:
                row.confidence = rule.confidence

    if new_rule.id:
        row = db.get(CategorizationRule, new_rule.id)
        if row:
            row.category_id = new_rule.category_id
            row.confidence = new_rule.confidence
            row.hit_count = new_rule.hit_count
        return row

    row = CategorizationRule(
        family_id=family_id,
        match_type=new_rule.match_type,
        pattern=new_rule.pattern,
        direction=new_rule.direction,
        category_id=new_rule.category_id,
        apply_tag_id=new_rule.apply_tag_id,
        ir_deduction_member_id=new_rule.ir_deduction_member_id,
        priority=new_rule.priority,
        confidence=new_rule.confidence,
        hit_count=new_rule.hit_count,
        is_learned=True,
        created_by=corrected_by,
    )
    db.add(row)
    return row
