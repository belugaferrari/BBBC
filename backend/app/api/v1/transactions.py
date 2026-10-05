"""Lancamentos: listagem com filtros individual/familiar, criacao e correcao."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import and_, or_, select, text

from app.api.deps import (
    CurrentMember,
    DbSession,
    owned_account,
    owned_category,
    owned_donor,
    owned_member,
    owned_tag,
    scope_member_id,
)
from app.models import Category, Transaction, TransactionTag
from app.models.enums import TxDirection, TxStatus
from app.schemas.transactions import TransactionCreate, TransactionOut, TransactionUpdate
from app.services.caixa import caixa_da_conta
from app.services.categorization_repository import apply_correction, autocategorize
from app.services.mascara import sem_digitos_sensiveis
from app.services.queries import note_required_for, spend_by_category, spend_by_member

router = APIRouter(prefix="/transactions", tags=["gastos"])


def owned_reembolso(db, reembolso_de_id: UUID, current) -> Transaction:  # noqa: ANN001
    """O gasto que o reembolso devolve: da propria familia, e SAIDA.

    Apontar um reembolso para outra entrada nao quer dizer nada, e passaria
    despercebido ate alguem estranhar o consumo do mes - por isso a checagem e
    aqui, onde da para recusar com uma frase, e nao no relatorio.
    """
    gasto = db.get(Transaction, reembolso_de_id)
    if not gasto or gasto.family_id != current.family_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lancamento nao encontrado")
    if gasto.direction != TxDirection.SAIDA:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Reembolso so pode apontar para um gasto - o que voce escolheu e uma entrada.",
        )
    return gasto


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
        # O periodo e o do CAIXA: a compra de 25 de setembro feita no cartao
        # aparece na lista de OUTUBRO, que e o mes em que ela saiu da conta e o
        # mes em que ela pesa no Resumo. A linha mostra as duas datas quando
        # elas diferem - a lista e a mesma coisa que o Resumo, vista de perto, e
        # duas respostas diferentes para "quanto foi outubro" seria pior do que
        # a surpresa de encontrar o jantar de setembro aqui.
        Transaction.paid_on.between(start, end),
        Transaction.status != TxStatus.IGNORADA,
    ]
    owner = scope_member_id(current, scope)
    if owner:
        filters.append(Transaction.owner_member_id == owner)
    if only_uncategorized:
        # "Sem categoria" passou a ter duas formas: a antiga (categoria nula, de
        # antes de existir "A definir") e a de agora, que e a categoria "A
        # definir" propriamente. Filtrar so por uma delas deixaria metade dos
        # pendentes invisivel justamente na tela onde eles sao resolvidos.
        pendente = select(Category.id).where(
            Category.family_id == current.family_id,
            Category.slug == "a_definir",
        )
        filters.append(
            or_(Transaction.category_id.is_(None), Transaction.category_id.in_(pendente))
        )
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


@router.get("/reembolsaveis")
def reembolsaveis(
    current: CurrentMember,
    db: DbSession,
    days: int = Query(60, ge=1, le=365),
    limit: int = Query(40, le=200),
) -> list[dict]:
    """Os gastos recentes, com quanto de cada um ja voltou.

    Existe para a tela poder perguntar "reembolso de qual gasto?" com uma lista
    curta e util em vez de um campo de id. O `reembolsado` vem junto porque a
    pergunta seguinte e sempre essa: se os amigos ja devolveram a parte deles, o
    jantar nao esta mais esperando nada.
    """
    linhas = db.execute(
        text(
            """
            SELECT t.id, t.booked_on, t.amount, t.description,
                   c.name AS category_name,
                   COALESCE((
                       SELECT SUM(r.amount) FROM transactions r
                        WHERE r.reembolso_de_id = t.id
                          AND r.status IN ('EFETIVADA', 'CONCILIADA')
                   ), 0) AS reembolsado
              FROM transactions t
              LEFT JOIN categories c ON c.id = t.category_id
             WHERE t.family_id = :familia
               AND t.direction = 'SAIDA'
               AND t.status IN ('EFETIVADA', 'CONCILIADA')
               AND COALESCE(c.counts_as_expense, true)
               AND t.booked_on >= CURRENT_DATE - CAST(:dias AS int)
             ORDER BY t.booked_on DESC, t.amount DESC
             LIMIT :limite
            """
        ),
        {"familia": current.family_id, "dias": days, "limite": limit},
    ).mappings().all()

    return [
        {
            "id": linha["id"],
            "booked_on": linha["booked_on"],
            "amount": linha["amount"],
            "description": sem_digitos_sensiveis(linha["description"]),
            "category_name": linha["category_name"],
            "reembolsado": linha["reembolsado"],
            # quanto ainda sobra para ser devolvido, para a tela nao oferecer um
            # gasto que ja voltou inteiro como se nada tivesse acontecido
            "falta": max(linha["amount"] - linha["reembolsado"], 0),
        }
        for linha in linhas
    ]


@router.post("", response_model=TransactionOut, status_code=status.HTTP_201_CREATED)
def create_transaction(
    payload: TransactionCreate, current: CurrentMember, db: DbSession
) -> Transaction:
    """Insercao manual. A categorizacao automatica roda mesmo aqui - o usuario
    so precisa confirmar quando o motor errar.

    Com `client_key`, reenviar o mesmo lancamento devolve o que ja foi gravado
    em vez de criar outro. E o que permite ao aplicativo subir a fila offline
    sem medo: conexao que cai no meio, aplicativo fechado e nova tentativa sao
    o caminho normal, nao a excecao.
    """
    if payload.client_key:
        ja_gravado = db.scalar(
            select(Transaction).where(
                Transaction.family_id == current.family_id,
                Transaction.client_key == payload.client_key,
            )
        )
        if ja_gravado is not None:
            # Mesma resposta da primeira vez. O aplicativo nao precisa saber se
            # acertou agora ou da outra vez - em ambos o lancamento existe.
            return ja_gravado

    account = owned_account(db, payload.account_id, current)
    if payload.category_id:
        owned_category(db, payload.category_id, current)
        # 'Unicos (com comentarios)': daqui a seis meses ninguem lembra o que
        # foi aquele gasto de R$ 3.400 se ele entrar sem explicacao
        exige = note_required_for(db, payload.category_id)
        if exige and not (payload.notes or "").strip():
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"A categoria '{exige}' exige um comentario explicando o gasto.",
            )
    if payload.ir_deduction_member_id:
        owned_member(db, payload.ir_deduction_member_id, current)
    if payload.owner_member_id:
        owned_member(db, payload.owner_member_id, current)
    if payload.donor_id:
        owned_donor(db, payload.donor_id, current)
    if payload.donation_for_category_id:
        owned_category(db, payload.donation_for_category_id, current)
    if payload.reembolso_de_id:
        owned_reembolso(db, payload.reembolso_de_id, current)
    for tag_id in payload.tags:
        owned_tag(db, tag_id, current)

    tx = Transaction(
        family_id=current.family_id,
        # sem responsavel informado, o gasto e de quem e a conta
        ir_year=payload.booked_on.year,
        **payload.model_dump(exclude={"tags", "owner_member_id"}),
        owner_member_id=payload.owner_member_id or account.owner_member_id,
        # quando o dinheiro sai: no cartao, o vencimento da fatura que cobra
        # esta compra; em qualquer outra conta, o proprio dia
        paid_on=caixa_da_conta(account, payload.booked_on, payload.direction),
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
    if payload.donor_id:
        owned_donor(db, payload.donor_id, current)
    if payload.donation_for_category_id:
        owned_category(db, payload.donation_for_category_id, current)
    if payload.reembolso_de_id:
        owned_reembolso(db, payload.reembolso_de_id, current)

    data = payload.model_dump(exclude_unset=True, exclude={"learn_rule", "category_id"})
    for field, value in data.items():
        setattr(tx, field, value)

    if payload.category_id and payload.category_id != tx.category_id:
        owned_category(db, payload.category_id, current)
        exige = note_required_for(db, payload.category_id)
        if exige and not (payload.notes or tx.notes or "").strip():
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"A categoria '{exige}' exige um comentario explicando o gasto.",
            )
        apply_correction(
            db, current.family_id, tx, payload.category_id, current.id, learn=payload.learn_rule
        )
    db.flush()
    return tx
