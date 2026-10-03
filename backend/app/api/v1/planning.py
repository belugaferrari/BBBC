"""Previsoes: tetos por categoria e simulador de metas."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import CurrentMember, DbSession, owned_category, owned_member
from app.models import BudgetCap, Category, Goal
from app.models.enums import PeriodType
from app.services.analise_categoria import primeiro_do_mes
from app.services.projection import GoalInput, simulate_goal
from app.services.queries import spend_by_budget_cap

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


class BudgetCapUpdate(BaseModel):
    amount: Decimal | None = Field(default=None, gt=0)
    alert_at_pct: Decimal | None = None
    includes_descendants: bool | None = None
    ends_on: date | None = None


def _cap_proprio(db: DbSession, cap_id: UUID, current: CurrentMember) -> BudgetCap:
    cap = db.get(BudgetCap, cap_id)
    if not cap or cap.family_id != current.family_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Meta nao encontrada")
    return cap


@router.get("/budget-caps")
def list_budget_caps(
    current: CurrentMember, db: DbSession, month: date | None = None
) -> list[dict]:
    """As metas que valiam no mes, com o quanto já foi gasto em cada uma."""
    mes = primeiro_do_mes(month or date.today())
    linhas = spend_by_budget_cap(db, current.family_id, mes)
    caminhos = {
        linha[0]: linha[1]
        for linha in db.execute(
            select(Category.id, Category.path).where(
                Category.family_id == current.family_id
            )
        )
    }
    return [
        {
            **linha,
            "path": str(caminhos.get(linha["category_id"], "")),
            "remaining": Decimal(linha["cap"]) - Decimal(linha["spent"]),
            "used_pct": (
                (Decimal(linha["spent"]) / Decimal(linha["cap"])).quantize(
                    Decimal("0.0001")
                )
                if Decimal(linha["cap"])
                else None
            ),
        }
        for linha in linhas
    ]


@router.post("/budget-caps", status_code=status.HTTP_201_CREATED)
def create_budget_cap(payload: BudgetCapIn, current: CurrentMember, db: DbSession) -> dict:
    """Define a meta da categoria. Definir de novo SUBSTITUI, nao empilha.

    Sem isso, tocar duas vezes em "salvar meta" deixaria duas metas vivas para
    Mercado, e o painel escolheria uma delas sem dizer qual - o tipo de numero
    que faz a pessoa perder a confianca na tela inteira. A meta de um mes vale
    para um (categoria, pessoa, periodo) por vez.
    """
    owned_category(db, payload.category_id, current)
    if payload.member_id:
        owned_member(db, payload.member_id, current)

    comeco = payload.starts_on or date.today().replace(day=1)

    anterior = db.scalar(
        select(BudgetCap).where(
            BudgetCap.family_id == current.family_id,
            BudgetCap.category_id == payload.category_id,
            BudgetCap.member_id.is_(None)
            if payload.member_id is None
            else BudgetCap.member_id == payload.member_id,
            BudgetCap.period == payload.period,
            BudgetCap.starts_on <= comeco,
            (BudgetCap.ends_on.is_(None)) | (BudgetCap.ends_on >= comeco),
        )
    )
    if anterior is not None:
        # A meta antiga e atualizada no lugar, e nao encerrada e recriada: o
        # historico de quanto foi o teto em marco nao e informacao que alguem
        # tenha pedido, e manter duas linhas por categoria complica a leitura de
        # tudo o que olha teto.
        anterior.amount = payload.amount
        anterior.alert_at_pct = payload.alert_at_pct
        anterior.includes_descendants = payload.includes_descendants
        anterior.starts_on = min(anterior.starts_on, comeco)
        anterior.ends_on = None
        db.flush()
        return {"id": anterior.id, "substituiu": True}

    cap = BudgetCap(
        family_id=current.family_id,
        starts_on=comeco,
        **payload.model_dump(exclude={"starts_on"}),
    )
    db.add(cap)
    db.flush()
    return {"id": cap.id, "substituiu": False}


@router.patch("/budget-caps/{cap_id}")
def update_budget_cap(
    cap_id: UUID, payload: BudgetCapUpdate, current: CurrentMember, db: DbSession
) -> dict:
    cap = _cap_proprio(db, cap_id, current)
    for campo, valor in payload.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(cap, campo, valor)
    db.flush()
    return {"id": cap.id, "amount": cap.amount}


@router.delete("/budget-caps/{cap_id}")
def delete_budget_cap(cap_id: UUID, current: CurrentMember, db: DbSession) -> dict:
    """Apaga a meta. O gasto continua onde esta - so o teto deixa de existir."""
    cap = _cap_proprio(db, cap_id, current)
    db.delete(cap)
    db.flush()
    return {"apagada": True}


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
