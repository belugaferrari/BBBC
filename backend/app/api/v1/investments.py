"""Investimentos: custodia consolidada, evolucao e comparativo CDI / IPCA."""

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Query
from sqlalchemy import text

from app.api.deps import CurrentMember, DbSession
from app.models.enums import AssetClass
from app.services.investments import (
    MonthPoint,
    PositionView,
    compare_to_benchmark,
    consolidate,
    real_return,
)

router = APIRouter(prefix="/investments", tags=["investimentos"])


@router.get("/portfolio")
def portfolio(current: CurrentMember, db: DbSession) -> dict:
    rows = db.execute(
        text(
            """
            SELECT a.name AS asset_name, a.asset_class::text AS asset_class,
                   a.is_ir_exempt, a.benchmark_code,
                   m.full_name AS owner,
                   p.invested_amount, p.market_value
              FROM positions p
              JOIN assets  a ON a.id = p.asset_id
              JOIN members m ON m.id = p.owner_member_id
             WHERE p.family_id = :family_id
               AND p.closed_on IS NULL
            """
        ),
        {"family_id": current.family_id},
    ).mappings().all()

    summary = consolidate(
        [
            PositionView(
                asset_name=r["asset_name"],
                asset_class=AssetClass(r["asset_class"]),
                owner=r["owner"],
                invested_amount=Decimal(r["invested_amount"]),
                market_value=Decimal(r["market_value"]),
                benchmark_code=r["benchmark_code"],
                is_ir_exempt=r["is_ir_exempt"],
            )
            for r in rows
        ]
    )
    return {
        "total_invested": summary.total_invested,
        "total_market_value": summary.total_market_value,
        "total_profit": summary.total_profit,
        "total_profit_pct": summary.total_profit_pct,
        "exempt_share": summary.exempt_share,
        "by_class": [alloc.__dict__ for alloc in summary.by_class],
        "by_owner": summary.by_owner,
    }


@router.get("/evolution")
def evolution(
    current: CurrentMember,
    db: DbSession,
    start: date,
    end: date,
    benchmark: str = Query("CDI", pattern="^(CDI|IPCA|SELIC|IBOV)$"),
) -> dict:
    """Curva do patrimonio contra a carteira-sombra rendendo o indicador."""
    points_rows = db.execute(
        text(
            """
            SELECT s.snapshot_on AS reference,
                   SUM(s.market_value) AS market_value,
                   SUM(s.invested_amount) AS invested
              FROM position_snapshots s
              JOIN positions p ON p.id = s.position_id
             WHERE p.family_id = :family_id
               AND s.snapshot_on BETWEEN :start AND :end
             GROUP BY s.snapshot_on
             ORDER BY s.snapshot_on
            """
        ),
        {"family_id": current.family_id, "start": start, "end": end},
    ).mappings().all()

    points: list[MonthPoint] = []
    previous_invested = None
    for row in points_rows:
        invested = Decimal(row["invested"])
        contribution = Decimal("0") if previous_invested is None else invested - previous_invested
        previous_invested = invested
        points.append(
            MonthPoint(
                reference=row["reference"],
                market_value=Decimal(row["market_value"]),
                net_contribution=contribution,
            )
        )

    rates = {
        r["reference_on"]: Decimal(r["period_rate"])
        for r in db.execute(
            text(
                """
                SELECT reference_on, period_rate FROM benchmark_series
                 WHERE code = :code AND reference_on BETWEEN :start AND :end
                """
            ),
            {"code": benchmark, "start": start, "end": end},
        ).mappings()
    }
    inflation_rates = {
        r["reference_on"]: Decimal(r["period_rate"])
        for r in db.execute(
            text(
                """
                SELECT reference_on, period_rate FROM benchmark_series
                 WHERE code = 'IPCA' AND reference_on BETWEEN :start AND :end
                """
            ),
            {"start": start, "end": end},
        ).mappings()
    }

    comparison = compare_to_benchmark(points, rates, benchmark)
    accumulated_inflation = Decimal("1")
    for rate in inflation_rates.values():
        accumulated_inflation *= 1 + rate

    return {
        "benchmark": benchmark,
        "portfolio_return": comparison.portfolio_return,
        "benchmark_return": comparison.benchmark_return,
        "excess_return": comparison.excess_return,
        "pct_of_benchmark": comparison.pct_of_benchmark,
        "real_return_vs_ipca": real_return(
            comparison.portfolio_return, accumulated_inflation - 1
        ),
        "portfolio_curve": comparison.portfolio_curve,
        "benchmark_curve": comparison.benchmark_curve,
    }
