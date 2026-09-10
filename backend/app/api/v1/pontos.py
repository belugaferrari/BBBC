"""Pontos de cartao de credito."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, text

from app.api.deps import CurrentMember, DbSession, owned_account
from app.models import CardProgram, PointMovement
from app.services.points import EarningRule, points_for_spend, summarize_program

router = APIRouter(prefix="/card-programs", tags=["pontos"])


class ProgramIn(BaseModel):
    name: str
    card_name: str | None = None
    account_id: UUID | None = None
    points_per_currency: Decimal = Field(default=Decimal("0"), ge=0)
    # cartao brasileiro costuma pontuar por dolar gasto, e nao por real
    currency_basis: str = "USD"
    balance: Decimal = Decimal("0")
    point_value_brl: Decimal | None = None
    expires_next_on: date | None = None
    expires_next_points: Decimal | None = None
    notes: str | None = None


class MovementIn(BaseModel):
    moved_on: date
    kind: str = Field(pattern="^(ACUMULO|RESGATE|EXPIRACAO|TRANSFERENCIA|AJUSTE|BONUS)$")
    points: Decimal
    description: str | None = None


def _serialize(row: CardProgram) -> dict:
    resumo = summarize_program(
        name=row.name,
        balance=row.balance,
        point_value_brl=row.point_value_brl,
        expires_next_on=row.expires_next_on,
        expires_next_points=row.expires_next_points,
    )
    return {
        "id": row.id,
        "name": row.name,
        "card_name": row.card_name,
        "account_id": row.account_id,
        "points_per_currency": row.points_per_currency,
        "currency_basis": row.currency_basis,
        "balance": row.balance,
        "balance_value_brl": row.balance_value_brl,
        "point_value_brl": row.point_value_brl,
        "expires_next_on": row.expires_next_on,
        "expires_next_points": row.expires_next_points,
        "days_to_expire": resumo.days_to_expire,
        "should_alert": resumo.should_alert,
    }


@router.get("")
def list_programs(current: CurrentMember, db: DbSession) -> dict:
    linhas = db.scalars(
        select(CardProgram).where(
            CardProgram.family_id == current.family_id, CardProgram.is_active.is_(True)
        ).order_by(CardProgram.name)
    ).all()
    programas = [_serialize(row) for row in linhas]
    return {
        "programs": programas,
        "total_points": sum((p["balance"] for p in programas), Decimal("0")),
        "total_value_brl": sum(
            (p["balance_value_brl"] or Decimal("0") for p in programas), Decimal("0")
        ),
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_program(payload: ProgramIn, current: CurrentMember, db: DbSession) -> dict:
    if payload.account_id:
        owned_account(db, payload.account_id, current)
    row = CardProgram(family_id=current.family_id, **payload.model_dump())
    db.add(row)
    db.flush()
    return _serialize(row)


@router.post("/{program_id}/movements", status_code=status.HTTP_201_CREATED)
def add_movement(
    program_id: UUID, payload: MovementIn, current: CurrentMember, db: DbSession
) -> dict:
    """Lanca entrada ou saida de pontos e atualiza o saldo.

    O saldo e recalculado a partir dos movimentos, e nao incrementado: assim um
    lancamento reenviado nao inventa pontos.
    """
    programa = db.get(CardProgram, program_id)
    if not programa or programa.family_id != current.family_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Programa nao encontrado")

    db.add(PointMovement(program_id=program_id, **payload.model_dump()))
    db.flush()

    programa.balance = db.execute(
        text("SELECT COALESCE(SUM(points), 0) FROM point_movements WHERE program_id = :id"),
        {"id": program_id},
    ).scalar_one()
    db.flush()
    return _serialize(programa)


@router.get("/{program_id}/movements")
def list_movements(program_id: UUID, current: CurrentMember, db: DbSession) -> list[dict]:
    programa = db.get(CardProgram, program_id)
    if not programa or programa.family_id != current.family_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Programa nao encontrado")
    return [
        dict(linha)
        for linha in db.execute(
            text(
                "SELECT id, moved_on, kind, points, description FROM point_movements"
                " WHERE program_id = :id ORDER BY moved_on DESC, created_at DESC LIMIT 200"
            ),
            {"id": program_id},
        ).mappings()
    ]


class EstimateIn(BaseModel):
    amount_brl: Decimal = Field(gt=0)
    usd_rate: Decimal | None = Field(default=None, gt=0)


@router.post("/{program_id}/estimate")
def estimate_points(
    program_id: UUID, payload: EstimateIn, current: CurrentMember, db: DbSession
) -> dict:
    """Quantos pontos uma compra renderia neste programa."""
    programa = db.get(CardProgram, program_id)
    if not programa or programa.family_id != current.family_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Programa nao encontrado")

    try:
        pontos = points_for_spend(
            payload.amount_brl,
            EarningRule(programa.points_per_currency, programa.currency_basis),
            payload.usd_rate,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    return {
        "amount_brl": payload.amount_brl,
        "points": pontos,
        "currency_basis": programa.currency_basis,
        "value_brl": (
            (pontos * programa.point_value_brl).quantize(Decimal("0.01"))
            if programa.point_value_brl
            else None
        ),
    }
