"""Evolutivo dos proximos meses.

O teste que mais importa aqui e o da dupla contagem: a escola cadastrada como
gasto fixo TAMBEM aparece na media historica de Educacao. Somar as duas
inflaria a previsao justamente nas categorias mais pesadas.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.models.enums import TxDirection
from app.services.forecast import (
    FlowKind,
    ForecastEvent,
    add_months,
    average_by_category,
    first_negative_month,
    horizon,
    project,
    subtract_covered,
    summarize,
)

JAN = date(2026, 1, 1)


def evento(mes, tipo, direcao, valor, rotulo="x", caminho=None):
    return ForecastEvent(
        month=mes, kind=tipo, direction=direcao, amount=Decimal(valor),
        label=rotulo, category_path=caminho,
    )


# ------------------------------------------------------------- calendario ---
def test_horizonte_comeca_no_mes_da_data_e_avanca():
    meses = horizon(date(2026, 11, 20), 4)
    assert meses == [date(2026, 11, 1), date(2026, 12, 1), date(2027, 1, 1), date(2027, 2, 1)]


def test_soma_de_meses_vira_o_ano():
    assert add_months(date(2026, 12, 1), 1) == date(2027, 1, 1)
    assert add_months(date(2026, 1, 1), -1) == date(2025, 12, 1)


# --------------------------------------------------------------- medias -----
def test_media_divide_pelos_meses_observados_e_nao_pelos_com_gasto():
    """Uma despesa que ocorreu em 1 de 3 meses nao acontece todo mes."""
    historico = [(date(2026, 1, 1), "despesas.saude", Decimal("900"))]
    assert average_by_category(historico, months_observed=3) == {
        "despesas.saude": Decimal("300.00")
    }


def test_media_de_varios_meses():
    historico = [
        (date(2026, 1, 1), "despesas.mercado", Decimal("1200")),
        (date(2026, 2, 1), "despesas.mercado", Decimal("1500")),
        (date(2026, 3, 1), "despesas.mercado", Decimal("1300")),
    ]
    assert average_by_category(historico, 3)["despesas.mercado"] == Decimal("1333.33")


# ---------------------------------------------------------- dupla contagem --
def test_gasto_ja_previsto_como_fixo_sai_da_estimativa():
    """A escola cadastrada como recorrente nao pode entrar de novo pela media."""
    medias = {"despesas.educacao": Decimal("900.00")}
    coberto = {"despesas.educacao": Decimal("900.00")}
    assert subtract_covered(medias, coberto) == {}


def test_desconto_e_parcial_e_preserva_o_que_sobra():
    """Media de 900 com 680 cobertos deixa 220 de material e extras."""
    medias = {"despesas.educacao": Decimal("900.00")}
    coberto = {"despesas.educacao": Decimal("680.00")}
    assert subtract_covered(medias, coberto) == {"despesas.educacao": Decimal("220.00")}


def test_cobertura_de_subcategoria_desconta_do_grupo():
    """O recorrente esta em Educacao > Escola; a media, no grupo Educacao."""
    medias = {"despesas.educacao": Decimal("900.00")}
    coberto = {"despesas.educacao.escola": Decimal("680.00")}
    assert subtract_covered(medias, coberto) == {"despesas.educacao": Decimal("220.00")}


def test_categoria_sem_cobertura_permanece_inteira():
    medias = {"despesas.mercado": Decimal("1300.00")}
    assert subtract_covered(medias, {"despesas.educacao": Decimal("680")}) == medias


# -------------------------------------------------------------- projecao ----
def test_saldo_encadeia_de_um_mes_para_o_outro():
    eventos = [
        evento(JAN, FlowKind.FIXO, TxDirection.ENTRADA, "28000", "Pró-labore"),
        evento(JAN, FlowKind.FIXO, TxDirection.SAIDA, "6800", "Escola"),
        evento(date(2026, 2, 1), FlowKind.FIXO, TxDirection.ENTRADA, "28000"),
        evento(date(2026, 2, 1), FlowKind.ESTIMADO, TxDirection.SAIDA, "4200"),
    ]
    meses = project(Decimal("10000"), eventos, JAN, months=2)

    assert meses[0].closing_balance == Decimal("31200.00")
    assert meses[1].opening_balance == Decimal("31200.00")
    assert meses[1].closing_balance == Decimal("55000.00")


def test_cada_mes_separa_o_que_e_compromisso_do_que_e_chute():
    eventos = [
        evento(JAN, FlowKind.FIXO, TxDirection.SAIDA, "6800", "Escola"),
        evento(JAN, FlowKind.ESPERADO, TxDirection.SAIDA, "890", "Parcela 2/3"),
        evento(JAN, FlowKind.ESTIMADO, TxDirection.SAIDA, "4200", "Supermercado"),
    ]
    mes = project(Decimal("0"), eventos, JAN, months=1)[0]

    assert mes.outflow_by_kind == {
        "FIXO": Decimal("6800.00"),
        "ESPERADO": Decimal("890.00"),
        "ESTIMADO": Decimal("4200.00"),
    }
    assert mes.outflow == Decimal("11890.00")


def test_mes_sem_evento_nao_some_da_projecao():
    meses = project(Decimal("500"), [], JAN, months=3)
    assert len(meses) == 3
    assert all(m.closing_balance == Decimal("500.00") for m in meses)


def test_itens_vem_do_maior_para_o_menor():
    eventos = [
        evento(JAN, FlowKind.ESTIMADO, TxDirection.SAIDA, "300", "Farmácia"),
        evento(JAN, FlowKind.FIXO, TxDirection.SAIDA, "6800", "Escola"),
        evento(JAN, FlowKind.ESTIMADO, TxDirection.SAIDA, "1200", "Mercado"),
    ]
    mes = project(Decimal("0"), eventos, JAN, months=1)[0]
    assert [i["label"] for i in mes.items] == ["Escola", "Mercado", "Farmácia"]


# --------------------------------------------------------------- alertas ----
def test_avisa_em_que_mes_o_dinheiro_acaba():
    eventos = [
        evento(mes, FlowKind.ESTIMADO, TxDirection.SAIDA, "4000")
        for mes in horizon(JAN, 4)
    ]
    meses = project(Decimal("9000"), eventos, JAN, months=4)

    assert first_negative_month(meses) == date(2026, 3, 1)
    assert meses[2].negative
    assert not meses[1].negative


def test_sem_aperto_nao_ha_alerta():
    eventos = [evento(JAN, FlowKind.FIXO, TxDirection.ENTRADA, "5000")]
    assert first_negative_month(project(Decimal("100"), eventos, JAN, months=2)) is None


def test_resumo_do_periodo():
    eventos = [
        evento(JAN, FlowKind.FIXO, TxDirection.ENTRADA, "28000"),
        evento(JAN, FlowKind.FIXO, TxDirection.SAIDA, "11000"),
        evento(date(2026, 2, 1), FlowKind.FIXO, TxDirection.ENTRADA, "28000"),
        evento(date(2026, 2, 1), FlowKind.FIXO, TxDirection.SAIDA, "13000"),
    ]
    resumo = summarize(project(Decimal("0"), eventos, JAN, months=2))

    assert resumo["total_inflow"] == Decimal("56000.00")
    assert resumo["total_outflow"] == Decimal("24000.00")
    assert resumo["net"] == Decimal("32000.00")
    assert resumo["average_monthly_outflow"] == Decimal("12000.00")
    assert resumo["first_negative_month"] is None


@pytest.mark.parametrize("meses", [1, 6, 12, 24])
def test_projecao_devolve_exatamente_os_meses_pedidos(meses):
    assert len(project(Decimal("0"), [], JAN, months=meses)) == meses
