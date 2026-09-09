"""Montagem do grafico em cascata (Sankey) do dashboard.

O fluxo tem tres estagios:
    origens de receita -> 'Renda do mes' -> grupos de despesa -> subcategorias
O que sobra vira um no proprio ('Sobra do mes'), para o desenho fechar: a soma
dos links que saem do no central e sempre igual a receita total.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from decimal import Decimal

from app.services.money import ZERO, brl

CENTRAL_NODE = "Renda do mes"
SURPLUS_NODE = "Sobra do mes"
DEFICIT_NODE = "Uso de reservas"


@dataclass(frozen=True)
class FlowRow:
    """Uma linha agregada de v_monthly_cashflow."""

    direction: str          # ENTRADA | SAIDA
    group: str              # nivel 2 da arvore (ex.: 'Essenciais')
    category: str           # nivel folha exibido (ex.: 'Supermercado')
    amount: Decimal


@dataclass
class SankeyNode:
    id: str
    label: str
    stage: int
    value: Decimal


@dataclass
class SankeyLink:
    source: str
    target: str
    value: Decimal


def build_sankey(rows: list[FlowRow], *, min_share: Decimal = Decimal("0.01")) -> dict:
    """Agrupa fluxos pequenos em 'Outros' para o grafico continuar legivel no celular."""
    income_rows = [r for r in rows if r.direction == "ENTRADA"]
    expense_rows = [r for r in rows if r.direction == "SAIDA"]

    total_income = brl(sum((r.amount for r in income_rows), ZERO))
    total_expense = brl(sum((r.amount for r in expense_rows), ZERO))

    nodes: dict[str, SankeyNode] = {}
    links: list[SankeyLink] = []

    def node(node_id: str, label: str, stage: int, value: Decimal) -> None:
        existing = nodes.get(node_id)
        if existing:
            existing.value = brl(existing.value + value)
        else:
            nodes[node_id] = SankeyNode(id=node_id, label=label, stage=stage, value=brl(value))

    node(CENTRAL_NODE, CENTRAL_NODE, 1, total_income)

    # Estagio 0: origens de receita -> no central
    by_income: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for row in income_rows:
        by_income[row.category or row.group] += row.amount
    for label, amount in sorted(by_income.items(), key=lambda kv: kv[1], reverse=True):
        node(f"in:{label}", label, 0, amount)
        links.append(SankeyLink(source=f"in:{label}", target=CENTRAL_NODE, value=brl(amount)))

    # Estagio 2: no central -> grupos de despesa
    by_group: dict[str, Decimal] = defaultdict(lambda: ZERO)
    by_leaf: dict[tuple[str, str], Decimal] = defaultdict(lambda: ZERO)
    for row in expense_rows:
        by_group[row.group] += row.amount
        by_leaf[(row.group, row.category)] += row.amount

    threshold = total_expense * min_share
    for group, amount in sorted(by_group.items(), key=lambda kv: kv[1], reverse=True):
        node(f"grp:{group}", group, 2, amount)
        links.append(SankeyLink(source=CENTRAL_NODE, target=f"grp:{group}", value=brl(amount)))

        # Estagio 3: grupo -> subcategorias (agregando as irrelevantes)
        leaves = {leaf: value for (grp, leaf), value in by_leaf.items() if grp == group}
        others = ZERO
        for leaf, value in sorted(leaves.items(), key=lambda kv: kv[1], reverse=True):
            if value < threshold and len(leaves) > 3:
                others += value
                continue
            node(f"leaf:{group}:{leaf}", leaf, 3, value)
            links.append(
                SankeyLink(source=f"grp:{group}", target=f"leaf:{group}:{leaf}", value=brl(value))
            )
        if others > 0:
            node(f"leaf:{group}:Outros", "Outros", 3, others)
            links.append(
                SankeyLink(source=f"grp:{group}", target=f"leaf:{group}:Outros", value=brl(others))
            )

    # Fechamento: sobra ou uso de reservas
    balance = brl(total_income - total_expense)
    if balance > 0:
        node(SURPLUS_NODE, SURPLUS_NODE, 2, balance)
        links.append(SankeyLink(source=CENTRAL_NODE, target=SURPLUS_NODE, value=balance))
    elif balance < 0:
        node(DEFICIT_NODE, DEFICIT_NODE, 0, -balance)
        links.append(SankeyLink(source=DEFICIT_NODE, target=CENTRAL_NODE, value=-balance))

    return {
        "total_income": total_income,
        "total_expense": total_expense,
        "balance": balance,
        "nodes": [asdict(n) for n in nodes.values()],
        "links": [asdict(link) for link in links],
    }
