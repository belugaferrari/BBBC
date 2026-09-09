"""Previsoes: tetos de gasto, simulador de aportes e projecao de fluxo de caixa."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.services.money import ZERO, brl, safe_div

MONTHS_IN_YEAR = Decimal("12")


# ---------------------------------------------------------------------------
# Matematica financeira
# ---------------------------------------------------------------------------
def monthly_rate(annual_rate: Decimal) -> Decimal:
    """Converte taxa nominal anual em equivalente mensal composta."""
    if annual_rate == 0:
        return ZERO
    return Decimal(str((1 + float(annual_rate)) ** (1 / 12) - 1))


def future_value(
    present_value: Decimal, monthly_contribution: Decimal, annual_rate: Decimal, months: int
) -> Decimal:
    """VF de um capital inicial mais aportes mensais no fim de cada mes."""
    if months <= 0:
        return brl(present_value)
    i = monthly_rate(annual_rate)
    if i == 0:
        return brl(present_value + monthly_contribution * months)
    growth = (1 + i) ** months
    return brl(present_value * growth + monthly_contribution * (growth - 1) / i)


def required_monthly_contribution(
    target: Decimal, present_value: Decimal, annual_rate: Decimal, months: int
) -> Decimal:
    """Aporte mensal necessario para atingir a meta no prazo."""
    if months <= 0:
        return brl(max(ZERO, target - present_value))
    i = monthly_rate(annual_rate)
    if i == 0:
        return brl(max(ZERO, (target - present_value) / months))
    growth = (1 + i) ** months
    needed = (target - present_value * growth) * i / (growth - 1)
    return brl(max(ZERO, needed))


def months_to_target(
    target: Decimal,
    present_value: Decimal,
    monthly_contribution: Decimal,
    annual_rate: Decimal,
    max_months: int = 1200,
) -> int | None:
    """Em quantos meses a meta e atingida com o aporte informado."""
    if present_value >= target:
        return 0
    if monthly_contribution <= 0 and annual_rate <= 0:
        return None
    i = monthly_rate(annual_rate)
    balance = present_value
    for month in range(1, max_months + 1):
        balance = balance * (1 + i) + monthly_contribution
        if balance >= target:
            return month
    return None


def months_between(start: date, end: date) -> int:
    return max(0, (end.year - start.year) * 12 + (end.month - start.month))


# ---------------------------------------------------------------------------
# Simulador de metas (ex.: viagem da familia para a Disney)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class GoalInput:
    name: str
    target_amount: Decimal
    target_date: date
    current_amount: Decimal = ZERO
    monthly_contribution: Decimal = ZERO
    expected_annual_rate: Decimal = ZERO
    inflation_indexed: bool = False
    expected_inflation: Decimal = Decimal("0.045")


@dataclass
class GoalProjection:
    name: str
    months_remaining: int
    adjusted_target: Decimal
    projected_amount: Decimal
    gap: Decimal                      # > 0 falta dinheiro
    required_monthly: Decimal
    contribution_delta: Decimal       # quanto falta no aporte atual
    on_track: bool
    months_needed_at_current_pace: int | None
    series: list[dict]                # evolucao mes a mes para o grafico


def simulate_goal(goal: GoalInput, today: date | None = None) -> GoalProjection:
    today = today or date.today()
    months = months_between(today, goal.target_date)

    target = goal.target_amount
    if goal.inflation_indexed and months > 0:
        target = brl(
            goal.target_amount
            * Decimal(str((1 + float(goal.expected_inflation)) ** (months / 12)))
        )

    projected = future_value(
        goal.current_amount, goal.monthly_contribution, goal.expected_annual_rate, months
    )
    required = required_monthly_contribution(
        target, goal.current_amount, goal.expected_annual_rate, months
    )

    i = monthly_rate(goal.expected_annual_rate)
    balance = goal.current_amount
    series: list[dict] = [{"month": 0, "balance": brl(balance), "target": target}]
    for month in range(1, months + 1):
        balance = balance * (1 + i) + goal.monthly_contribution
        series.append({"month": month, "balance": brl(balance), "target": target})

    return GoalProjection(
        name=goal.name,
        months_remaining=months,
        adjusted_target=brl(target),
        projected_amount=projected,
        gap=brl(max(ZERO, target - projected)),
        required_monthly=required,
        contribution_delta=brl(max(ZERO, required - goal.monthly_contribution)),
        on_track=projected >= target,
        months_needed_at_current_pace=months_to_target(
            target, goal.current_amount, goal.monthly_contribution, goal.expected_annual_rate
        ),
        series=series,
    )


# ---------------------------------------------------------------------------
# Tetos de gasto por categoria
# ---------------------------------------------------------------------------
@dataclass
class BudgetStatus:
    category_id: str
    category_name: str
    cap: Decimal
    spent: Decimal
    remaining: Decimal
    used_pct: Decimal
    projected_spend: Decimal      # ritmo atual extrapolado ate o fim do periodo
    projected_overflow: Decimal
    should_alert: bool
    severity: str                 # INFO | ATENCAO | CRITICO


def budget_status(
    *,
    category_id: str,
    category_name: str,
    cap: Decimal,
    spent: Decimal,
    days_elapsed: int,
    days_in_period: int,
    alert_at_pct: Decimal = Decimal("0.8"),
) -> BudgetStatus:
    """Compara o gasto realizado com o teto e projeta o fechamento do periodo."""
    days_elapsed = max(1, days_elapsed)
    days_in_period = max(days_elapsed, days_in_period)

    used_pct = safe_div(spent, cap)
    projected = brl(spent / days_elapsed * days_in_period)
    overflow = brl(max(ZERO, projected - cap))

    if spent > cap:
        severity = "CRITICO"
    elif overflow > 0 or used_pct >= alert_at_pct:
        severity = "ATENCAO"
    else:
        severity = "INFO"

    return BudgetStatus(
        category_id=category_id,
        category_name=category_name,
        cap=brl(cap),
        spent=brl(spent),
        remaining=brl(cap - spent),
        used_pct=used_pct.quantize(Decimal("0.0001")),
        projected_spend=projected,
        projected_overflow=overflow,
        should_alert=severity != "INFO",
        severity=severity,
    )


# ---------------------------------------------------------------------------
# Projecao de fluxo de caixa
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ScheduledFlow:
    description: str
    amount: Decimal      # positivo entra, negativo sai
    month_offset: int    # 0 = mes corrente


def cashflow_forecast(
    opening_balance: Decimal, flows: list[ScheduledFlow], months: int = 6
) -> list[dict]:
    """Saldo projetado mes a mes a partir dos lancamentos previstos/recorrentes."""
    balance = opening_balance
    result: list[dict] = []
    for offset in range(months):
        month_flows = [f for f in flows if f.month_offset == offset]
        inflow = brl(sum((f.amount for f in month_flows if f.amount > 0), ZERO))
        outflow = brl(sum((-f.amount for f in month_flows if f.amount < 0), ZERO))
        balance = brl(balance + inflow - outflow)
        result.append(
            {
                "month_offset": offset,
                "inflow": inflow,
                "outflow": outflow,
                "net": brl(inflow - outflow),
                "closing_balance": balance,
            }
        )
    return result
