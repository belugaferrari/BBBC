"""Evolutivo dos proximos meses."""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import CurrentMember, DbSession, owned_member, scope_member_id
from app.services.forecast import project, summarize
from app.services.forecast_repository import build_events, opening_balance

router = APIRouter(prefix="/forecast", tags=["previsoes"])


@router.get("")
def cashflow_forecast(
    current: CurrentMember,
    db: DbSession,
    months: int = Query(6, ge=1, le=24),
    scope: str = Query("familia", pattern="^(familia|individual)$"),
    member_id: UUID | None = None,
    start: date | None = None,
) -> dict:
    """Saldo projetado mes a mes, separando o que e compromisso do que e chute.

    Cada mes traz o total por origem: FIXO (recorrente cadastrado), ESPERADO
    (lancamento futuro que ja existe) e ESTIMADO (media historica da categoria).
    Um total unico esconderia justamente essa diferenca.
    """
    if member_id:
        owned_member(db, member_id, current)
        alvo = member_id
    else:
        alvo = scope_member_id(current, scope)

    inicio = start or date.today()
    eventos, procedencia = build_events(db, current.family_id, inicio, months, alvo)
    projecoes = project(
        opening_balance(db, current.family_id, alvo), eventos, inicio, months
    )

    return {
        "start": inicio,
        "months": months,
        "scope": scope,
        "sources": procedencia,
        "summary": summarize(projecoes),
        "projection": [
            {
                "month": p.month,
                "opening_balance": p.opening_balance,
                "inflow": p.inflow,
                "outflow": p.outflow,
                "net": p.net,
                "closing_balance": p.closing_balance,
                "inflow_by_kind": p.inflow_by_kind,
                "outflow_by_kind": p.outflow_by_kind,
                # so os maiores: a lista completa de um mes passa de 30 linhas
                "items": p.items[:12],
            }
            for p in projecoes
        ],
    }
