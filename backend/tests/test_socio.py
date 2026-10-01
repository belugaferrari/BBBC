"""A fronteira entre o dinheiro da familia e o da empresa.

O teste central e o do par: uma conta pessoal paga pela empresa nao pode mexer
no caixa da familia (o dinheiro nao era dela) e ao mesmo tempo PRECISA contar na
categoria (o gasto existiu). Lancar so a despesa derruba o saldo por um gasto
que nao saiu do bolso; ignorar a linha esconde o consumo. So o par acerta os
dois ao mesmo tempo.
"""

from decimal import Decimal
from uuid import uuid4

import pytest

from app.models.enums import SocioFlow, TxDirection
from app.services.socio import (
    CONTRAPARTIDA_PADRAO,
    CONTRAPARTIDAS,
    ContrapartidaDesconhecida,
    Pendencia,
    conta_da_empresa_paga_por_mim,
    conta_paga_pela_empresa,
    efeito_no_caixa,
    efeito_no_consumo,
    saldo_com_a_empresa,
)

ESCOLA = Decimal("3000.00")


def test_conta_paga_pela_empresa_nao_mexe_no_caixa():
    """O caso da escola da Cecilia. Dois lancamentos, efeito zero no saldo."""
    par = list(conta_paga_pela_empresa(
        descricao="Escola Cecilia",
        valor=ESCOLA,
        categoria_pessoal_path="despesas.educacao.escola",
    ))
    assert efeito_no_caixa(par) == Decimal("0")


def test_mas_o_gasto_conta_na_categoria():
    """Efeito zero no caixa nao pode virar efeito zero no consumo."""
    par = list(conta_paga_pela_empresa(
        descricao="Escola Cecilia",
        valor=ESCOLA,
        categoria_pessoal_path="despesas.educacao.escola",
    ))
    assert efeito_no_consumo(par) == ESCOLA

    despesa, _ = par
    assert despesa.categoria_path == "despesas.educacao.escola"
    assert despesa.direcao == TxDirection.SAIDA


def test_so_a_despesa_leva_a_categoria_pessoal():
    """A entrada nao pode herdar a categoria do gasto - duplicaria Educacao."""
    despesa, entrada = conta_paga_pela_empresa(
        descricao="Escola Cecilia",
        valor=ESCOLA,
        categoria_pessoal_path="despesas.educacao.escola",
    )
    assert entrada.categoria_path != despesa.categoria_path
    assert entrada.direcao == TxDirection.ENTRADA


@pytest.mark.parametrize(
    ("contrapartida", "path"),
    sorted(CONTRAPARTIDAS.items()),
)
def test_a_contrapartida_escolhe_o_tratamento_de_ir(contrapartida, path):
    """Pro-labore, lucro e adiantamento sao impostos diferentes."""
    _, entrada = conta_paga_pela_empresa(
        descricao="Escola Cecilia",
        valor=ESCOLA,
        categoria_pessoal_path="despesas.educacao.escola",
        contrapartida=contrapartida,
    )
    assert entrada.categoria_path == path


def test_o_padrao_nao_afirma_nada_sobre_imposto():
    """Pro-labore por omissao inventaria tributo; lucro esconderia um."""
    assert CONTRAPARTIDA_PADRAO == "ADIANTAMENTO"
    _, entrada = conta_paga_pela_empresa(
        descricao="Escola Cecilia",
        valor=ESCOLA,
        categoria_pessoal_path="despesas.educacao.escola",
    )
    assert entrada.categoria_path == CONTRAPARTIDAS["ADIANTAMENTO"]


def test_contrapartida_inventada_e_recusada():
    with pytest.raises(ContrapartidaDesconhecida):
        conta_paga_pela_empresa(
            descricao="Escola",
            valor=ESCOLA,
            categoria_pessoal_path="despesas.educacao.escola",
            contrapartida="SEI_LA",
        )


def test_os_dois_lados_ficam_marcados():
    """Sem a marca nos dois, um relatorio futuro mostraria metade do par."""
    despesa, entrada = conta_paga_pela_empresa(
        descricao="Escola Cecilia",
        valor=ESCOLA,
        categoria_pessoal_path="despesas.educacao.escola",
    )
    assert despesa.socio_flow == SocioFlow.PESSOAL_VIA_EMPRESA
    assert entrada.socio_flow == SocioFlow.PESSOAL_VIA_EMPRESA


# --------------------------------------------------------- o caminho inverso


def test_o_que_pago_pela_empresa_sai_do_caixa():
    """O dinheiro saiu de verdade: o saldo tem que cair."""
    lan = conta_da_empresa_paga_por_mim(descricao="Fornecedor Checkmotor",
                                        valor=Decimal("800.00"))
    assert efeito_no_caixa([lan]) == Decimal("-800.00")


def test_mas_nao_conta_como_gasto_da_familia():
    """E credito a receber, nao consumo. Contado, inflaria a categoria e o teto."""
    lan = conta_da_empresa_paga_por_mim(descricao="Fornecedor Checkmotor",
                                        valor=Decimal("800.00"))
    assert lan.conta_como_gasto is False
    assert efeito_no_consumo([lan]) == Decimal("0")
    assert lan.em_aberto is True


def test_valor_negativo_e_recusado():
    for fn in (
        lambda: conta_paga_pela_empresa(
            descricao="x", valor=Decimal("-1"), categoria_pessoal_path="a.b"),
        lambda: conta_da_empresa_paga_por_mim(descricao="x", valor=Decimal("0")),
    ):
        with pytest.raises(ValueError):
            fn()


# ------------------------------------------------------------- as pendencias


def _pend(valor, flow):
    from datetime import date
    return Pendencia(id=uuid4(), descricao="x", valor=Decimal(valor),
                     data=date(2026, 3, 1), socio_flow=flow)


def test_saldo_com_a_empresa_soma_os_dois_sentidos():
    pendencias = [
        _pend("800.00", SocioFlow.EMPRESA_VIA_PESSOAL),   # ela me deve
        _pend("300.00", SocioFlow.EMPRESA_VIA_PESSOAL),   # ela me deve
        _pend("500.00", SocioFlow.PESSOAL_VIA_EMPRESA),   # eu devo
    ]
    assert saldo_com_a_empresa(pendencias) == Decimal("600.00")


def test_quem_deve_fala_a_lingua_do_usuario():
    assert _pend("1", SocioFlow.EMPRESA_VIA_PESSOAL).quem_deve == "A empresa me deve"
    assert _pend("1", SocioFlow.PESSOAL_VIA_EMPRESA).quem_deve == "Devo a empresa"
