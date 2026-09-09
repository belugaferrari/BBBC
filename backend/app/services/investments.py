"""Consolidacao da custodia, evolucao patrimonial e comparativo CDI / IPCA."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.models.enums import AssetClass
from app.services.money import ZERO, brl, safe_div


@dataclass(frozen=True)
class PositionView:
    asset_name: str
    asset_class: AssetClass
    owner: str
    invested_amount: Decimal
    market_value: Decimal
    benchmark_code: str | None = None
    is_ir_exempt: bool = False


@dataclass
class ClassAllocation:
    asset_class: AssetClass
    market_value: Decimal
    invested_amount: Decimal
    profit: Decimal
    profit_pct: Decimal
    weight: Decimal


@dataclass
class PortfolioSummary:
    total_invested: Decimal
    total_market_value: Decimal
    total_profit: Decimal
    total_profit_pct: Decimal
    by_class: list[ClassAllocation]
    by_owner: dict[str, Decimal]
    exempt_share: Decimal        # fatia isenta de IR (LCI/LCA, dividendos...)


def consolidate(positions: list[PositionView]) -> PortfolioSummary:
    total_mv = brl(sum((p.market_value for p in positions), ZERO))
    total_inv = brl(sum((p.invested_amount for p in positions), ZERO))

    grouped: dict[AssetClass, list[PositionView]] = defaultdict(list)
    by_owner: dict[str, Decimal] = defaultdict(lambda: ZERO)
    exempt_value = ZERO
    for position in positions:
        grouped[position.asset_class].append(position)
        by_owner[position.owner] += position.market_value
        if position.is_ir_exempt:
            exempt_value += position.market_value

    allocations: list[ClassAllocation] = []
    for asset_class, items in grouped.items():
        mv = brl(sum((i.market_value for i in items), ZERO))
        inv = brl(sum((i.invested_amount for i in items), ZERO))
        allocations.append(
            ClassAllocation(
                asset_class=asset_class,
                market_value=mv,
                invested_amount=inv,
                profit=brl(mv - inv),
                profit_pct=safe_div(mv - inv, inv).quantize(Decimal("0.0001")),
                weight=safe_div(mv, total_mv).quantize(Decimal("0.0001")),
            )
        )
    allocations.sort(key=lambda a: a.market_value, reverse=True)

    return PortfolioSummary(
        total_invested=total_inv,
        total_market_value=total_mv,
        total_profit=brl(total_mv - total_inv),
        total_profit_pct=safe_div(total_mv - total_inv, total_inv).quantize(Decimal("0.0001")),
        by_class=allocations,
        by_owner={k: brl(v) for k, v in by_owner.items()},
        exempt_share=safe_div(exempt_value, total_mv).quantize(Decimal("0.0001")),
    )


# ---------------------------------------------------------------------------
# Evolucao patrimonial e comparativo contra indicadores
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class MonthPoint:
    reference: date
    market_value: Decimal
    net_contribution: Decimal    # aportes menos resgates no mes


@dataclass
class BenchmarkComparison:
    code: str
    portfolio_return: Decimal        # rentabilidade da carteira no periodo (TWR)
    benchmark_return: Decimal
    excess_return: Decimal
    pct_of_benchmark: Decimal        # 1.12 = carteira rendeu 112% do CDI
    portfolio_curve: list[dict]
    benchmark_curve: list[dict]      # carteira-sombra com os mesmos aportes


def time_weighted_return(points: list[MonthPoint]) -> Decimal:
    """TWR: neutraliza o efeito do momento dos aportes."""
    if len(points) < 2:
        return ZERO
    accumulated = Decimal("1")
    for previous, current in zip(points, points[1:], strict=False):
        base = previous.market_value + current.net_contribution
        if base <= 0:
            continue
        accumulated *= 1 + safe_div(current.market_value - base, base)
    return (accumulated - 1).quantize(Decimal("0.000001"))


def compare_to_benchmark(
    points: list[MonthPoint], benchmark_rates: dict[date, Decimal], code: str
) -> BenchmarkComparison:
    """Constroi a carteira-sombra: os MESMOS aportes rendendo o indicador.

    E a unica comparacao honesta - confrontar a rentabilidade da carteira com o
    CDI acumulado ignora que o dinheiro entrou em datas diferentes.
    """
    if not points:
        return BenchmarkComparison(code, ZERO, ZERO, ZERO, ZERO, [], [])

    portfolio_curve: list[dict] = []
    benchmark_curve: list[dict] = []

    shadow = points[0].market_value
    accumulated_benchmark = Decimal("1")

    for index, point in enumerate(points):
        if index > 0:
            rate = benchmark_rates.get(point.reference, ZERO)
            shadow = shadow * (1 + rate) + point.net_contribution
            accumulated_benchmark *= 1 + rate
        portfolio_curve.append(
            {"reference": point.reference.isoformat(), "value": brl(point.market_value)}
        )
        benchmark_curve.append(
            {"reference": point.reference.isoformat(), "value": brl(shadow)}
        )

    portfolio_return = time_weighted_return(points)
    benchmark_return = (accumulated_benchmark - 1).quantize(Decimal("0.000001"))

    return BenchmarkComparison(
        code=code,
        portfolio_return=portfolio_return,
        benchmark_return=benchmark_return,
        excess_return=(portfolio_return - benchmark_return).quantize(Decimal("0.000001")),
        pct_of_benchmark=(
            safe_div(portfolio_return, benchmark_return).quantize(Decimal("0.0001"))
            if benchmark_return
            else ZERO
        ),
        portfolio_curve=portfolio_curve,
        benchmark_curve=benchmark_curve,
    )


def real_return(nominal_return: Decimal, inflation: Decimal) -> Decimal:
    """Rentabilidade real (descontado o IPCA), pela formula de Fisher."""
    if inflation <= -1:
        return ZERO
    return ((1 + nominal_return) / (1 + inflation) - 1).quantize(Decimal("0.000001"))
