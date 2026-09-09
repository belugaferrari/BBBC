"""Consolidacao da carteira e comparativo honesto contra o CDI."""

from datetime import date
from decimal import Decimal

from app.models.enums import AssetClass
from app.services.investments import (
    MonthPoint,
    PositionView,
    compare_to_benchmark,
    consolidate,
    real_return,
    time_weighted_return,
)


def carteira() -> list[PositionView]:
    return [
        PositionView("CDB Banco X", AssetClass.RENDA_FIXA_POS, "Felipe",
                     Decimal("100000"), Decimal("112000")),
        PositionView("LCI Banco Y", AssetClass.RENDA_FIXA_POS, "Clarissa",
                     Decimal("50000"), Decimal("54000"), is_ir_exempt=True),
        PositionView("HGLG11", AssetClass.FII, "Felipe",
                     Decimal("60000"), Decimal("58000")),
    ]


def test_consolidacao_por_classe_e_por_titular():
    resumo = consolidate(carteira())
    assert resumo.total_invested == Decimal("210000.00")
    assert resumo.total_market_value == Decimal("224000.00")
    assert resumo.total_profit == Decimal("14000.00")
    assert resumo.by_owner["Felipe"] == Decimal("170000.00")
    assert resumo.by_class[0].asset_class == AssetClass.RENDA_FIXA_POS
    # 54.000 de 224.000 estao em papel isento
    assert resumo.exempt_share == Decimal("0.2411")


def test_twr_ignora_o_efeito_do_momento_do_aporte():
    pontos = [
        MonthPoint(date(2026, 1, 31), Decimal("100000"), Decimal("0")),
        MonthPoint(date(2026, 2, 28), Decimal("111000"), Decimal("10000")),
    ]
    # 110.000 de base -> 111.000: 0,909% no mes, e nao 11%
    assert time_weighted_return(pontos) == Decimal("0.009091")


def test_carteira_sombra_usa_os_mesmos_aportes():
    pontos = [
        MonthPoint(date(2026, 1, 31), Decimal("100000"), Decimal("0")),
        MonthPoint(date(2026, 2, 28), Decimal("102500"), Decimal("0")),
        MonthPoint(date(2026, 3, 31), Decimal("115000"), Decimal("10000")),
    ]
    cdi = {date(2026, 2, 28): Decimal("0.0090"), date(2026, 3, 31): Decimal("0.0090")}
    comparativo = compare_to_benchmark(pontos, cdi, "CDI")

    assert comparativo.code == "CDI"
    assert comparativo.benchmark_return > 0
    assert comparativo.portfolio_return > comparativo.benchmark_return
    assert comparativo.excess_return > 0
    assert comparativo.pct_of_benchmark > 1
    assert len(comparativo.benchmark_curve) == 3


def test_rentabilidade_real_desconta_o_ipca():
    assert real_return(Decimal("0.10"), Decimal("0.045")) == Decimal("0.052632")
