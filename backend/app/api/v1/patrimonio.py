"""Patrimonio: imoveis, terrenos e participacoes societarias."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, text

from app.api.deps import CurrentMember, DbSession, owned_member
from app.models import Holding, HoldingValuation
from app.models.enums import HoldingKind
from app.services.patrimonio import (
    HoldingView,
    ValuationPoint,
    consolidate_net_worth,
    valuation_series,
)

router = APIRouter(tags=["patrimonio"])


class HoldingIn(BaseModel):
    kind: HoldingKind
    name: str
    description: str | None = None
    acquired_on: date | None = None
    acquisition_value: Decimal | None = None
    current_value: Decimal = Decimal("0")
    # valor declarado no IR: a Receita usa o custo de aquisicao, nao o de mercado
    ir_declared_value: Decimal | None = None
    company_cnpj: str | None = None
    ownership_percentage: Decimal | None = Field(default=None, gt=0, le=100)
    registration: str | None = None
    address: str | None = None
    owner_member_id: UUID | None = None
    notes: str | None = None


class ValuationIn(BaseModel):
    valued_on: date
    value: Decimal
    source: str | None = None
    notes: str | None = None


def _serialize(row: Holding) -> dict:
    return {
        "id": row.id,
        "kind": row.kind,
        "name": row.name,
        "description": row.description,
        "acquired_on": row.acquired_on,
        "acquisition_value": row.acquisition_value,
        "current_value": row.current_value,
        "ir_declared_value": row.ir_declared_value,
        "unrealized_gain": row.unrealized_gain,
        "company_cnpj": row.company_cnpj,
        "ownership_percentage": row.ownership_percentage,
        "registration": row.registration,
        "address": row.address,
        "owner_member_id": row.owner_member_id,
        "is_active": row.is_active,
        "notes": row.notes,
    }


@router.get("/holdings")
def list_holdings(
    current: CurrentMember,
    db: DbSession,
    kind: HoldingKind | None = None,
    include_inactive: bool = False,
) -> list[dict]:
    """Bens da familia. `kind=PARTICIPACAO` responde a tela de participacoes."""
    filtros = [Holding.family_id == current.family_id]
    if kind:
        filtros.append(Holding.kind == kind)
    if not include_inactive:
        filtros.append(Holding.is_active.is_(True))

    return [
        _serialize(row)
        for row in db.scalars(select(Holding).where(*filtros).order_by(Holding.name)).all()
    ]


@router.post("/holdings", status_code=status.HTTP_201_CREATED)
def create_holding(payload: HoldingIn, current: CurrentMember, db: DbSession) -> dict:
    if payload.owner_member_id:
        owned_member(db, payload.owner_member_id, current)
    if payload.kind == HoldingKind.PARTICIPACAO and payload.ownership_percentage is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "participacao societaria precisa do percentual de participacao",
        )

    row = Holding(
        family_id=current.family_id,
        owner_member_id=payload.owner_member_id or current.id,
        **payload.model_dump(exclude={"owner_member_id"}),
    )
    db.add(row)
    db.flush()

    # a primeira avaliacao e o proprio valor informado, para a serie comecar
    if row.current_value:
        db.add(
            HoldingValuation(
                holding_id=row.id,
                valued_on=payload.acquired_on or date.today(),
                value=row.current_value,
                source="cadastro",
            )
        )
        db.flush()
    return _serialize(row)


@router.post("/holdings/{holding_id}/valuations", status_code=status.HTTP_201_CREATED)
def add_valuation(
    holding_id: UUID, payload: ValuationIn, current: CurrentMember, db: DbSession
) -> dict:
    """Reavalia o bem. O valor de hoje passa a ser o da avaliacao mais recente."""
    row = db.get(Holding, holding_id)
    if not row or row.family_id != current.family_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bem nao encontrado")

    db.merge(
        HoldingValuation(
            holding_id=holding_id,
            valued_on=payload.valued_on,
            value=payload.value,
            source=payload.source,
            notes=payload.notes,
        )
    )
    db.flush()

    mais_recente = db.execute(
        text(
            """
            SELECT value FROM holding_valuations
             WHERE holding_id = :id ORDER BY valued_on DESC LIMIT 1
            """
        ),
        {"id": holding_id},
    ).scalar_one()
    row.current_value = mais_recente
    db.flush()
    return _serialize(row)


@router.get("/holdings/{holding_id}/valuations")
def holding_history(holding_id: UUID, current: CurrentMember, db: DbSession) -> dict:
    row = db.get(Holding, holding_id)
    if not row or row.family_id != current.family_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bem nao encontrado")

    pontos = [
        ValuationPoint(valued_on=linha["valued_on"], value=Decimal(linha["value"]))
        for linha in db.execute(
            text(
                "SELECT valued_on, value FROM holding_valuations"
                " WHERE holding_id = :id ORDER BY valued_on"
            ),
            {"id": holding_id},
        ).mappings()
    ]
    return {"holding": _serialize(row), "series": valuation_series(pontos)}


@router.get("/net-worth")
def net_worth(
    current: CurrentMember,
    db: DbSession,
    scope: str = Query("familia", pattern="^(familia|individual)$"),
) -> dict:
    """Patrimonio total: contas, carteira, bens e o que se deve."""
    saldos = db.execute(
        text(
            """
            SELECT
              COALESCE(SUM(current_balance) FILTER (
                  WHERE type IN ('CONTA_CORRENTE','POUPANCA','DINHEIRO')), 0) AS liquido,
              COALESCE(SUM(current_balance) FILTER (WHERE type = 'INVESTIMENTO'), 0)
                                                                              AS investido,
              COALESCE(-SUM(current_balance) FILTER (
                  WHERE type = 'CARTAO_CREDITO' AND current_balance < 0), 0)  AS dividas
              FROM accounts
             WHERE family_id = :family_id AND is_archived = false
            """
        ),
        {"family_id": current.family_id},
    ).mappings().one()

    bens = [
        HoldingView(
            kind=HoldingKind(linha["kind"]),
            name=linha["name"],
            owner=linha["dono"],
            current_value=Decimal(linha["current_value"]),
            acquisition_value=(
                Decimal(linha["acquisition_value"])
                if linha["acquisition_value"] is not None
                else None
            ),
            ownership_percentage=(
                Decimal(linha["ownership_percentage"])
                if linha["ownership_percentage"] is not None
                else None
            ),
        )
        for linha in db.execute(
            text(
                """
                SELECT h.kind::text, h.name, h.current_value, h.acquisition_value,
                       h.ownership_percentage,
                       COALESCE(m.nickname, m.full_name) AS dono
                  FROM holdings h
                  JOIN members m ON m.id = h.owner_member_id
                 WHERE h.family_id = :family_id AND h.is_active
                """
            ),
            {"family_id": current.family_id},
        ).mappings()
    ]

    resultado = consolidate_net_worth(
        liquid=Decimal(saldos["liquido"]),
        invested=Decimal(saldos["investido"]),
        debts=Decimal(saldos["dividas"]),
        holdings=bens,
    )

    return {
        "scope": scope,
        "liquid": resultado.liquid,
        "invested": resultado.invested,
        "holdings": resultado.holdings,
        "debts": resultado.debts,
        "total": resultado.total,
        "illiquid_share": resultado.illiquid_share,
        "by_kind": resultado.by_kind,
        "by_owner": resultado.by_owner,
    }
