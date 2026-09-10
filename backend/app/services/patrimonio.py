"""Patrimonio consolidado: contas, investimentos, bens e dividas.

O numero que interessa nao e o saldo da conta nem a carteira isolada - e o
quanto a familia vale somando tudo e tirando o que deve.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from app.models.enums import HoldingKind
from app.services.money import ZERO, brl, safe_div


@dataclass(frozen=True)
class HoldingView:
    kind: HoldingKind
    name: str
    owner: str
    current_value: Decimal
    acquisition_value: Decimal | None = None
    ownership_percentage: Decimal | None = None


@dataclass
class NetWorth:
    liquid: Decimal              # conta corrente, poupanca, dinheiro
    invested: Decimal            # carteira financeira
    holdings: Decimal            # imoveis, terrenos, participacoes
    debts: Decimal               # fatura de cartao em aberto
    total: Decimal
    by_kind: dict[str, Decimal] = field(default_factory=dict)
    by_owner: dict[str, Decimal] = field(default_factory=dict)

    @property
    def illiquid_share(self) -> Decimal:
        """Quanto do patrimonio nao da para transformar em dinheiro rapido.

        Numero desconfortavel e util: um patrimonio alto todo em imovel nao
        paga a escola no mes que a receita cair.
        """
        return safe_div(self.holdings, self.total).quantize(Decimal("0.0001"))


def consolidate_net_worth(
    *,
    liquid: Decimal,
    invested: Decimal,
    debts: Decimal,
    holdings: list[HoldingView],
) -> NetWorth:
    by_kind: dict[str, Decimal] = {}
    by_owner: dict[str, Decimal] = {}
    total_holdings = ZERO

    for item in holdings:
        total_holdings += item.current_value
        by_kind[item.kind.value] = by_kind.get(item.kind.value, ZERO) + item.current_value
        by_owner[item.owner] = by_owner.get(item.owner, ZERO) + item.current_value

    return NetWorth(
        liquid=brl(liquid),
        invested=brl(invested),
        holdings=brl(total_holdings),
        debts=brl(debts),
        total=brl(liquid + invested + total_holdings - debts),
        by_kind={k: brl(v) for k, v in by_kind.items()},
        by_owner={k: brl(v) for k, v in by_owner.items()},
    )


@dataclass(frozen=True)
class ValuationPoint:
    valued_on: date
    value: Decimal


def valuation_series(points: list[ValuationPoint]) -> list[dict]:
    """Evolucao de um bem, com a variacao desde a avaliacao anterior."""
    ordenados = sorted(points, key=lambda p: p.valued_on)
    serie: list[dict] = []
    anterior: Decimal | None = None

    for ponto in ordenados:
        variacao = None if anterior is None else safe_div(ponto.value - anterior, anterior)
        serie.append(
            {
                "valued_on": ponto.valued_on.isoformat(),
                "value": brl(ponto.value),
                "change": (
                    variacao.quantize(Decimal("0.0001")) if variacao is not None else None
                ),
            }
        )
        anterior = ponto.value
    return serie
