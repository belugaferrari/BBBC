"""Dashboard: fluxo do mes, saldos consolidados, Sankey e alertas."""

from calendar import monthrange
from datetime import date

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.api.deps import CurrentMember, DbSession, scope_member_id
from app.models import Alert
from app.services.evolucao import evolucao_do_mes
from app.services.projection import budget_status
from app.services.queries import (
    consolidated_balances,
    monthly_cashflow,
    pendentes_de_categoria,
    sankey_rows,
    spend_by_budget_cap,
)
from app.services.sankey import build_sankey

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("")
def dashboard(
    current: CurrentMember,
    db: DbSession,
    month: date | None = None,
    scope: str = Query("familia", pattern="^(familia|individual)$"),
) -> dict:
    reference = (month or date.today()).replace(day=1)
    owner = scope_member_id(current, scope)

    today = date.today()
    days_in_month = monthrange(reference.year, reference.month)[1]
    days_elapsed = today.day if (today.year, today.month) == (
        reference.year, reference.month
    ) else days_in_month

    caps = [
        budget_status(
            category_id=str(row["category_id"]),
            category_name=row["category_name"],
            cap=row["cap"],
            spent=row["spent"],
            days_elapsed=days_elapsed,
            days_in_period=days_in_month,
            alert_at_pct=row["alert_at_pct"],
        )
        for row in spend_by_budget_cap(db, current.family_id, reference)
    ]

    alerts = db.scalars(
        select(Alert)
        .where(Alert.family_id == current.family_id, Alert.read_at.is_(None))
        .order_by(Alert.created_at.desc())
        .limit(10)
    ).all()

    return {
        "reference_month": reference,
        "scope": scope,
        "cashflow": monthly_cashflow(db, current.family_id, reference, owner),
        # O que ainda esta em "A definir". Vem no painel porque "salvo agora,
        # arrumo depois" so funciona se o depois aparecer em algum lugar.
        "pendentes": pendentes_de_categoria(db, current.family_id, reference, owner),
        "balances": consolidated_balances(db, current.family_id, owner),
        "sankey": build_sankey(sankey_rows(db, current.family_id, reference, owner)),
        "budget_caps": [cap.__dict__ for cap in caps],
        "alerts": [
            {
                "id": a.id, "kind": a.kind, "severity": a.severity,
                "title": a.title, "body": a.body, "created_at": a.created_at,
            }
            for a in alerts
        ],
    }


@router.get("/evolucao")
def evolucao(
    current: CurrentMember,
    db: DbSession,
    month: date | None = None,
    scope: str = Query("familia", pattern="^(familia|individual)$"),
) -> dict:
    """O gasto acumulado dia a dia, com o mes passado, o ano passado e a meta.

    Responde a pergunta que se faz no dia 12 do mes - "estou gastando rapido
    demais?" - que o total sozinho nao responde: ritmo so aparece comparado.
    """
    reference = (month or date.today()).replace(day=1)
    return evolucao_do_mes(
        db, current.family_id, reference, scope_member_id(current, scope)
    )
