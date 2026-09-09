"""Previsoes: tetos por categoria e simulador de metas."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import CurrentMember, DbSession
from app.models import BudgetCap, Goal
from app.models.enums import PeriodType
from app.services.projection import GoalInput, simulate_goal

router = APIRouter(tags=["previsoes"])


class BudgetCapIn(BaseModel):
    category_id: UUID
    amount: Decimal = Field(gt=0)
    member_id: UUID | None = None
    period: PeriodType = PeriodType.MENSAL
    includes_descendants: bool = True
    alert_at_pct: Decimal = Decimal("0.8")
    starts_on: date | None = None


class GoalIn(BaseModel):
    name: str
    target_amount: Decimal = Field(gt=0)
    target_date: date
    current_amount: Decimal = Decimal("0")
    monthly_contribution: Decimal = Decimal("0")
    expected_annual_rate: Decimal = Decimal("0")
    inflation_indexed: bool = False
    description: str | None = None


class SimulationIn(BaseModel):
    """Cenario 'e se': sobrepoe os parametros da meta sem grava-los."""

    monthly_contribution: Decimal | None = None
    expected_annual_rate: Decimal | None = None
    target_date: date | None = None
    target_amount: Decimal | None = None
    expected_inflation: Decimal = Decimal("0.045")


@router.post("/budget-caps", status_code=status.HTTP_201_CREATED)
def create_budget_cap(payload: BudgetCapIn, current: CurrentMember, db: DbSession) -> dict:
    cap = BudgetCap(
        family_id=current.family_id,
        starts_on=payload.starts_on or date.today().replace(day=1),
        **payload.model_dump(exclude={"starts_on"}),
    )
    db.add(cap)
    db.flush()
    return {"id": cap.id}


@router.get("/goals")
def list_goals(current: CurrentMember, db: DbSession) -> list[dict]:
    goals = db.scalars(select(Goal).where(Goal.family_id == current.family_id)).all()
    return [
        {
            "id": g.id,
            "name": g.name,
            "target_amount": g.target_amount,
            "target_date": g.target_date,
            "current_amount": g.current_amount,
            "monthly_contribution": g.monthly_contribution,
            "status": g.status,
            "projection": simulate_goal(_to_input(g)).__dict__,
        }
        for g in goals
    ]


@router.post("/goals", status_code=status.HTTP_201_CREATED)
def create_goal(payload: GoalIn, current: CurrentMember, db: DbSession) -> dict:
    goal = Goal(family_id=current.family_id, **payload.model_dump())
    db.add(goal)
    db.flush()
    return {"id": goal.id, "projection": simulate_goal(_to_input(goal)).__dict__}


@router.post("/goals/{goal_id}/simulate")
def simulate(
    goal_id: UUID, payload: SimulationIn, current: CurrentMember, db: DbSession
) -> dict:
    """Simulador de aportes: quanto por mes para a viagem sair no prazo."""
    goal = db.get(Goal, goal_id)
    if not goal or goal.family_id != current.family_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Meta nao encontrada")

    scenario = GoalInput(
        name=goal.name,
        target_amount=payload.target_amount or goal.target_amount,
        target_date=payload.target_date or goal.target_date,
        current_amount=goal.current_amount,
        monthly_contribution=(
            payload.monthly_contribution
            if payload.monthly_contribution is not None
            else goal.monthly_contribution
        ),
        expected_annual_rate=(
            payload.expected_annual_rate
            if payload.expected_annual_rate is not None
            else goal.expected_annual_rate
        ),
        inflation_indexed=goal.inflation_indexed,
        expected_inflation=payload.expected_inflation,
    )
    return {"baseline": simulate_goal(_to_input(goal)).__dict__,
            "scenario": simulate_goal(scenario).__dict__}


def _to_input(goal: Goal) -> GoalInput:
    return GoalInput(
        name=goal.name,
        target_amount=goal.target_amount,
        target_date=goal.target_date,
        current_amount=goal.current_amount,
        monthly_contribution=goal.monthly_contribution,
        expected_annual_rate=goal.expected_annual_rate,
        inflation_indexed=goal.inflation_indexed,
    )
