"""Evolutivo dos proximos meses.

A projecao soma tres origens, e a distincao entre elas e o que torna o numero
util - um total unico esconde o que e compromisso e o que e chute:

  FIXO      lancamento recorrente cadastrado (aluguel, escola, plano de saude).
            Data e valor conhecidos; e o piso do mes.
  ESPERADO  lancamento que ja existe no sistema com data futura: parcela de
            cartao, conta agendada, aporte programado.
  ESTIMADO  media historica por categoria, para o gasto que sempre acontece mas
            nao esta cadastrado em lugar nenhum (mercado, restaurante, farmacia).

A armadilha desta conta e somar a mesma despesa duas vezes: a escola cadastrada
como recorrente TAMBEM aparece na media historica da categoria Educacao. Por
isso `estimate_by_category` recebe quais categorias ja estao cobertas por FIXO
ou ESPERADO e as descarta - ver `subtract_covered`.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import StrEnum

from app.models.enums import TxDirection
from app.services.money import ZERO, brl


class FlowKind(StrEnum):
    FIXO = "FIXO"
    ESPERADO = "ESPERADO"
    ESTIMADO = "ESTIMADO"


@dataclass(frozen=True)
class ForecastEvent:
    """Um valor previsto para um mes, com a sua procedencia."""

    month: date                    # sempre o primeiro dia do mes
    kind: FlowKind
    direction: TxDirection
    amount: Decimal
    label: str
    category_path: str | None = None
    category_name: str | None = None


@dataclass
class MonthProjection:
    month: date
    opening_balance: Decimal
    inflow: Decimal
    outflow: Decimal
    net: Decimal
    closing_balance: Decimal
    outflow_by_kind: dict[str, Decimal] = field(default_factory=dict)
    inflow_by_kind: dict[str, Decimal] = field(default_factory=dict)
    items: list[dict] = field(default_factory=list)

    @property
    def negative(self) -> bool:
        return self.closing_balance < 0


def month_start(day: date) -> date:
    return day.replace(day=1)


def add_months(reference: date, count: int) -> date:
    """Primeiro dia do mes `count` meses a frente."""
    total = reference.month - 1 + count
    return date(reference.year + total // 12, total % 12 + 1, 1)


def horizon(start: date, months: int) -> list[date]:
    base = month_start(start)
    return [add_months(base, index) for index in range(months)]


# ---------------------------------------------------------------------------
# Estimativa por categoria
# ---------------------------------------------------------------------------
def average_by_category(
    history: list[tuple[date, str, Decimal]], months_observed: int
) -> dict[str, Decimal]:
    """Media mensal de gasto por categoria a partir do historico.

    `history` traz (mes, caminho da categoria, total do mes). A media divide
    pelo numero de meses observados, e nao pelo numero de meses em que houve
    gasto: uma despesa que aconteceu em 1 de 3 meses nao deve ser projetada
    como se acontecesse todo mes.
    """
    if months_observed <= 0:
        return {}
    somas: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for _mes, caminho, total in history:
        somas[caminho] += total
    return {caminho: brl(total / months_observed) for caminho, total in somas.items()}


def subtract_covered(
    estimates: dict[str, Decimal], covered: dict[str, Decimal]
) -> dict[str, Decimal]:
    """Desconta da estimativa o que ja esta previsto como FIXO ou ESPERADO.

    Sem isto, a escola cadastrada como recorrente entraria duas vezes: uma pelo
    recorrente e outra pela media historica de Educacao. O desconto e parcial de
    proposito - se a media de Educacao e 900 e o recorrente cobre 680, sobram
    220 de material e extras que continuam sendo gasto real.
    """
    resultado: dict[str, Decimal] = {}
    for caminho, media in estimates.items():
        ja_previsto = ZERO
        for coberto, valor in covered.items():
            # a cobertura vale para a categoria e para toda a sua subarvore
            if coberto == caminho or coberto.startswith(f"{caminho}."):
                ja_previsto += valor
        restante = media - ja_previsto
        if restante > 0:
            resultado[caminho] = brl(restante)
    return resultado


# ---------------------------------------------------------------------------
# Projecao
# ---------------------------------------------------------------------------
def project(
    opening_balance: Decimal,
    events: list[ForecastEvent],
    start: date,
    months: int = 6,
) -> list[MonthProjection]:
    """Encadeia os meses: o saldo final de um e o inicial do proximo."""
    por_mes: dict[date, list[ForecastEvent]] = defaultdict(list)
    for evento in events:
        por_mes[month_start(evento.month)].append(evento)

    saldo = opening_balance
    resultado: list[MonthProjection] = []

    for mes in horizon(start, months):
        do_mes = por_mes.get(mes, [])

        entradas: dict[str, Decimal] = defaultdict(lambda: ZERO)
        saidas: dict[str, Decimal] = defaultdict(lambda: ZERO)
        for evento in do_mes:
            destino = entradas if evento.direction == TxDirection.ENTRADA else saidas
            destino[evento.kind.value] += evento.amount

        total_entrada = brl(sum(entradas.values(), ZERO))
        total_saida = brl(sum(saidas.values(), ZERO))
        abertura = saldo
        saldo = brl(abertura + total_entrada - total_saida)

        resultado.append(
            MonthProjection(
                month=mes,
                opening_balance=brl(abertura),
                inflow=total_entrada,
                outflow=total_saida,
                net=brl(total_entrada - total_saida),
                closing_balance=saldo,
                inflow_by_kind={k: brl(v) for k, v in entradas.items()},
                outflow_by_kind={k: brl(v) for k, v in saidas.items()},
                items=sorted(
                    (
                        {
                            "kind": e.kind.value,
                            "direction": e.direction.value,
                            "amount": brl(e.amount),
                            "label": e.label,
                            "category_name": e.category_name,
                        }
                        for e in do_mes
                    ),
                    key=lambda item: item["amount"],
                    reverse=True,
                ),
            )
        )

    return resultado


def first_negative_month(projections: list[MonthProjection]) -> date | None:
    """Em que mes o dinheiro acaba, se acabar. E o alerta que importa."""
    for projecao in projections:
        if projecao.negative:
            return projecao.month
    return None


def summarize(projections: list[MonthProjection]) -> dict:
    entradas = brl(sum((p.inflow for p in projections), ZERO))
    saidas = brl(sum((p.outflow for p in projections), ZERO))
    return {
        "months": len(projections),
        "total_inflow": entradas,
        "total_outflow": saidas,
        "net": brl(entradas - saidas),
        "closing_balance": projections[-1].closing_balance if projections else ZERO,
        "first_negative_month": first_negative_month(projections),
        "average_monthly_outflow": (
            brl(saidas / len(projections)) if projections else ZERO
        ),
    }
