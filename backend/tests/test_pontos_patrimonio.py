"""Pontos de cartao e consolidacao de patrimonio."""

from datetime import date
from decimal import Decimal

import pytest

from app.models.enums import HoldingKind
from app.services.patrimonio import (
    HoldingView,
    ValuationPoint,
    consolidate_net_worth,
    valuation_series,
)
from app.services.points import (
    EarningRule,
    apply_movements,
    points_for_spend,
    summarize_program,
)


# ---------------------------------------------------------------- pontos ---
def test_cartao_que_pontua_por_dolar_usa_a_cotacao():
    """A maioria dos cartoes brasileiros pontua por dolar gasto. Tratar como
    real inflaria o saldo em cinco vezes."""
    pontos = points_for_spend(
        Decimal("1000.00"), EarningRule(Decimal("2.2"), "USD"), usd_rate=Decimal("5.00")
    )
    assert pontos == Decimal("440.00")     # 1000/5 = 200 dolares x 2,2


def test_cartao_que_pontua_por_real_dispensa_cotacao():
    pontos = points_for_spend(Decimal("1000.00"), EarningRule(Decimal("1.5"), "BRL"))
    assert pontos == Decimal("1500.00")


def test_pontuacao_em_dolar_sem_cotacao_falha_alto():
    """Chutar 1:1 seria pior do que recusar: o saldo ficaria cinco vezes maior."""
    with pytest.raises(ValueError, match="cotacao"):
        points_for_spend(Decimal("1000"), EarningRule(Decimal("2.2"), "USD"))


def test_compra_sem_valor_nao_pontua():
    assert points_for_spend(Decimal("0"), EarningRule(Decimal("2"), "BRL")) == Decimal("0")


def test_saldo_e_a_soma_dos_movimentos():
    saldo = apply_movements(
        Decimal("10000"),
        [Decimal("2200"), Decimal("-5000"), Decimal("-1200"), Decimal("300")],
    )
    assert saldo == Decimal("6300.00")


def test_resumo_avisa_quando_a_expiracao_esta_perto():
    resumo = summarize_program(
        name="Livelo", balance=Decimal("32000"), point_value_brl=Decimal("0.02"),
        expires_next_on=date(2026, 10, 20), expires_next_points=Decimal("8000"),
        today=date(2026, 9, 10),
    )
    assert resumo.days_to_expire == 40
    assert resumo.should_alert
    assert resumo.value_brl == Decimal("640.00")


def test_expiracao_distante_nao_avisa():
    resumo = summarize_program(
        name="Smiles", balance=Decimal("5000"), point_value_brl=None,
        expires_next_on=date(2027, 6, 1), expires_next_points=Decimal("5000"),
        today=date(2026, 9, 10),
    )
    assert not resumo.should_alert
    assert resumo.value_brl is None


def test_programa_sem_data_de_expiracao_nao_avisa():
    resumo = summarize_program(
        name="Esfera", balance=Decimal("1000"), point_value_brl=None,
        expires_next_on=None, expires_next_points=None, today=date(2026, 9, 10),
    )
    assert resumo.days_to_expire is None
    assert not resumo.should_alert


# ------------------------------------------------------------ patrimonio ---
def bem(kind, nome, valor, dono="Felipe", aquisicao=None):
    return HoldingView(
        kind=kind, name=nome, owner=dono, current_value=Decimal(valor),
        acquisition_value=Decimal(aquisicao) if aquisicao else None,
    )


def test_patrimonio_soma_tudo_e_desconta_a_divida():
    resultado = consolidate_net_worth(
        liquid=Decimal("31074.10"),
        invested=Decimal("224000.00"),
        debts=Decimal("3200.00"),
        holdings=[
            bem(HoldingKind.IMOVEL, "Apartamento", "850000", aquisicao="620000"),
            bem(HoldingKind.TERRENO, "Terreno", "180000", "Clarissa"),
            bem(HoldingKind.PARTICIPACAO, "Checkmotor", "400000"),
        ],
    )

    assert resultado.holdings == Decimal("1430000.00")
    assert resultado.total == Decimal("1681874.10")
    assert resultado.by_kind["IMOVEL"] == Decimal("850000.00")
    assert resultado.by_owner["Clarissa"] == Decimal("180000.00")


def test_fatia_iliquida_mostra_o_que_nao_paga_a_escola_no_mes_que_vem():
    resultado = consolidate_net_worth(
        liquid=Decimal("10000"), invested=Decimal("90000"), debts=Decimal("0"),
        holdings=[bem(HoldingKind.IMOVEL, "Apartamento", "900000")],
    )
    assert resultado.illiquid_share == Decimal("0.9000")


def test_patrimonio_sem_bens_nao_estoura():
    resultado = consolidate_net_worth(
        liquid=Decimal("5000"), invested=Decimal("0"), debts=Decimal("1000"),
        holdings=[],
    )
    assert resultado.total == Decimal("4000.00")
    assert resultado.illiquid_share == Decimal("0.0000")


def test_serie_de_reavaliacao_mostra_a_variacao():
    serie = valuation_series(
        [
            ValuationPoint(date(2024, 1, 1), Decimal("620000")),
            ValuationPoint(date(2025, 1, 1), Decimal("700000")),
            ValuationPoint(date(2026, 1, 1), Decimal("850000")),
        ]
    )
    assert serie[0]["change"] is None            # nao ha com o que comparar
    assert serie[1]["change"] == Decimal("0.1290")
    assert serie[2]["value"] == Decimal("850000.00")


def test_serie_ordena_por_data_mesmo_fora_de_ordem():
    serie = valuation_series(
        [
            ValuationPoint(date(2026, 1, 1), Decimal("850000")),
            ValuationPoint(date(2024, 1, 1), Decimal("620000")),
        ]
    )
    assert [p["valued_on"] for p in serie] == ["2024-01-01", "2026-01-01"]
