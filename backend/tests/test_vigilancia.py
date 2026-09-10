"""Avisos: extrato que falta, conta a vencer e ponto a expirar.

Modulo puro, entao da para testar cada regra sem banco nem rede - inclusive as
bordas de data, que sao onde este tipo de aviso costuma errar.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.services.vigilancia import (
    ContaAVencer,
    ContaEsperada,
    PontosAExpirar,
    avisos_de_extrato,
    avisos_de_pontos,
    avisos_de_vencimento,
    checklist_extratos,
    proximo_vencimento,
)

HOJE = date(2026, 9, 10)
MES = date(2026, 9, 1)


# ------------------------------------------------- extratos ----------------
def conta(nome, dia=None, recebido=None):
    return ContaEsperada(
        account_id=f"id-{nome}", name=nome, institution=None,
        expected_day=dia, received_at=recebido,
    )


def test_checklist_separa_recebido_pendente_e_atrasado():
    resultado = checklist_extratos(
        [
            conta("Itau", 5, date(2026, 9, 7)),      # ja chegou
            conta("Nubank", 20),                      # ainda nao venceu
            conta("Bradesco", 3),                     # atrasado
        ],
        MES,
        today=HOJE,
    )

    assert resultado["received"] == 1
    assert resultado["missing"] == 2
    assert [c["name"] for c in resultado["pending_list"]] == ["Nubank"]
    assert [c["name"] for c in resultado["late_list"]] == ["Bradesco"]
    assert resultado["late_list"][0]["days_late"] == 7
    assert not resultado["complete"]


def test_checklist_completo_quando_todos_mandaram():
    resultado = checklist_extratos(
        [conta("Itau", 5, date(2026, 9, 6)), conta("Nubank", 8, date(2026, 9, 9))],
        MES, today=HOJE,
    )
    assert resultado["complete"]
    assert resultado["missing"] == 0


def test_conta_sem_dia_esperado_nunca_e_dada_como_atrasada():
    """Sem saber quando o extrato costuma sair, cobrar seria chute."""
    resultado = checklist_extratos([conta("Corretora")], MES, today=HOJE)
    assert resultado["late_list"] == []
    assert len(resultado["pending_list"]) == 1


def test_dia_29_a_31_nao_estoura_em_mes_curto():
    resultado = checklist_extratos(
        [conta("Banco", 31)], date(2026, 2, 1), today=date(2026, 2, 28)
    )
    assert len(resultado["late_list"]) == 1


def test_aviso_de_extrato_diz_qual_banco_e_ha_quantos_dias():
    avisos = avisos_de_extrato(
        checklist_extratos([conta("Bradesco", 3)], MES, today=HOJE)
    )
    assert len(avisos) == 1
    assert "Bradesco" in avisos[0].title
    assert "7 dias" in avisos[0].body
    assert avisos[0].dedupe_key.endswith("2026-09-01")


# ------------------------------------------------- vencimentos -------------
def vencimento(dias, antecedencia=3, valor="450.00"):
    from datetime import timedelta

    return ContaAVencer(
        id=f"c{dias}", description="Conta de luz", amount=Decimal(valor),
        due_on=HOJE + timedelta(days=dias), remind_days_before=antecedencia,
    )


def test_so_avisa_dentro_da_janela_de_antecedencia():
    avisos = avisos_de_vencimento([vencimento(10), vencimento(2)], HOJE)
    assert len(avisos) == 1
    assert "2 dias" in avisos[0].title


@pytest.mark.parametrize(
    ("dias", "texto", "severidade"),
    [
        (3, "vence em 3 dias", "ATENCAO"),
        (1, "vence amanha", "ATENCAO"),
        (0, "vence hoje", "CRITICO"),
        (-2, "venceu ha 2 dia(s)", "CRITICO"),
    ],
)
def test_urgencia_muda_conforme_o_prazo(dias, texto, severidade):
    aviso = avisos_de_vencimento([vencimento(dias)], HOJE)[0]
    assert texto in aviso.title
    assert aviso.severity == severidade


def test_antecedencia_e_por_conta_e_nao_global():
    """A fatura do cartao precisa de mais dias do que a conta de luz."""
    avisos = avisos_de_vencimento(
        [vencimento(6, antecedencia=3), vencimento(6, antecedencia=7)], HOJE
    )
    assert len(avisos) == 1


def test_chave_de_deduplicacao_muda_com_o_vencimento():
    """O aviso de outubro nao pode ser confundido com o de setembro: e a mesma
    conta de luz, mas e outra fatura."""
    setembro = ContaAVencer(
        id="luz", description="Conta de luz", amount=Decimal("450"),
        due_on=date(2026, 9, 11),
    )
    outubro = ContaAVencer(
        id="luz", description="Conta de luz", amount=Decimal("470"),
        due_on=date(2026, 10, 11),
    )
    a = avisos_de_vencimento([setembro], HOJE)[0]
    b = avisos_de_vencimento([outubro], date(2026, 10, 9))[0]

    assert a.dedupe_key != b.dedupe_key
    assert a.dedupe_key == "vencimento:luz:2026-09-11"


def test_valor_no_aviso_e_escrito_como_dinheiro():
    """O aviso vai para o celular: '450.00' pareceria defeito."""
    aviso = avisos_de_vencimento([vencimento(1, valor="1450.90")], HOJE)[0]
    assert "R$ 1.450,90" in aviso.body


# ------------------------------------------------- pontos ------------------
def test_avisa_pontos_a_expirar_com_folga():
    avisos = avisos_de_pontos(
        [
            PontosAExpirar("p1", "Livelo", Decimal("32000"), date(2026, 10, 20),
                           Decimal("640")),
            PontosAExpirar("p2", "Smiles", Decimal("5000"), date(2027, 6, 1)),
        ],
        HOJE,
    )
    assert len(avisos) == 1
    # numero grande com separador de milhar: e o que a pessoa le no celular
    assert "32.000 pontos Livelo" in avisos[0].title
    assert "R$ 640,00" in avisos[0].body


def test_expiracao_proxima_e_critica():
    aviso = avisos_de_pontos(
        [PontosAExpirar("p1", "Livelo", Decimal("1000"), date(2026, 9, 20))], HOJE
    )[0]
    assert aviso.severity == "CRITICO"


def test_saldo_zerado_nao_gera_aviso():
    assert avisos_de_pontos(
        [PontosAExpirar("p1", "Livelo", Decimal("0"), date(2026, 9, 15))], HOJE
    ) == []


# ------------------------------------------------- datas -------------------
def test_proximo_vencimento_pula_para_o_mes_seguinte_quando_ja_passou():
    assert proximo_vencimento(5, date(2026, 9, 10)) == date(2026, 10, 5)
    assert proximo_vencimento(20, date(2026, 9, 10)) == date(2026, 9, 20)


def test_proximo_vencimento_nao_estoura_em_fevereiro():
    assert proximo_vencimento(31, date(2026, 2, 1)) == date(2026, 2, 28)
