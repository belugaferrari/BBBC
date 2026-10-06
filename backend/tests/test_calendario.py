"""O ano inteiro numa tela.

"Crie uma aba 'Calendario': esse sim sera o grande resumo da coisa toda."

Tres alturas de leitura: o ano mes a mes, o acumulado do ano, e o hoje
(patrimonio, reservas, gastos do ultimo mes fechado).

O que este arquivo guarda de verdade e o criterio dos dois numeros de cada mes.
"Entrou" e "saiu" NAO sao o extrato bruto: transferencia entre contas proprias e
pagamento de fatura ficam de fora dos dois lados. A fatura e a mesma despesa que
as compras dela - soma-las faria o ano inteiro parecer o dobro do que foi, e
agora que compra e fatura caem no mesmo mes isso aconteceria todo mes.
"""

from __future__ import annotations

import os
import uuid
from decimal import Decimal

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("BBBC_TEST_DATABASE_URL"),
    reason="defina BBBC_TEST_DATABASE_URL para rodar a integracao",
)


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def casa(client):
    from sqlalchemy import text

    from app.cli import seed_family
    from app.db.session import SessionLocal

    sufixo = uuid.uuid4().hex[:8]
    email = f"felipe.cal.{sufixo}@exemplo.com"
    family_id = seed_family(
        name=f"Familia {sufixo}",
        titular="Felipe",
        titular_email=email,
        titular_password="segredo-de-teste",
        conjuge="Clarissa",
        conjuge_email=f"clarissa.cal.{sufixo}@exemplo.com",
        conjuge_password="segredo-de-teste",
        dependentes=[],
    )
    auth = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "segredo-de-teste"}
    ).json()
    headers = {"Authorization": f"Bearer {auth['access_token']}"}
    corrente = client.post(
        "/api/v1/accounts", json={"name": "Itau", "type": "CONTA_CORRENTE"}, headers=headers
    ).json()
    cartao = client.post(
        "/api/v1/accounts",
        json={
            "name": "Visa",
            "type": "CARTAO_CREDITO",
            "statement_close_day": 25,
            "statement_due_day": 5,
        },
        headers=headers,
    ).json()
    with SessionLocal() as db:
        cats = {
            linha[0]: str(linha[1])
            for linha in db.execute(
                text("SELECT path::text, id FROM categories WHERE family_id = :f"),
                {"f": family_id},
            )
        }
    return {
        "headers": headers,
        "corrente": corrente["id"],
        "cartao": cartao["id"],
        "cat": cats,
    }


def lancar(client, casa, conta, **kw):
    corpo = {"account_id": conta, "status": "EFETIVADA", "description": "x", **kw}
    resposta = client.post("/api/v1/transactions", json=corpo, headers=casa["headers"])
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def calendario(client, casa, ano: int = 2026) -> dict:
    resposta = client.get(
        "/api/v1/calendario", params={"year": ano}, headers=casa["headers"]
    )
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def test_vem_sempre_com_os_doze_meses(client, casa):
    """Calendario com buraco obriga quem le a contar nos dedos qual mes e qual."""
    dados = calendario(client, casa)
    assert len(dados["months"]) == 12
    assert dados["months"][0]["month"] == "2026-01-01"
    assert dados["months"][11]["month"] == "2026-12-01"
    assert all(Decimal(m["entrou"]) == 0 for m in dados["months"])


def test_cada_mes_mostra_o_que_entrou_e_o_que_saiu(client, casa):
    lancar(
        client, casa, casa["corrente"], booked_on="2026-03-05", amount="10000.00",
        direction="ENTRADA", category_id=casa["cat"]["receitas.ativa_fixa.pro_labore"],
    )
    lancar(
        client, casa, casa["corrente"], booked_on="2026-03-20", amount="2500.00",
        direction="SAIDA", category_id=casa["cat"]["despesas.mercado"],
    )
    marco = calendario(client, casa)["months"][2]
    assert Decimal(marco["entrou"]) == Decimal("10000.00")
    assert Decimal(marco["saiu"]) == Decimal("2500.00")
    assert Decimal(marco["net"]) == Decimal("7500.00")


def test_o_pagamento_da_fatura_nao_conta_de_novo(client, casa):
    """O erro que este teste existe para impedir, e que e silencioso: a compra
    no cartao e a fatura que a paga caem no MESMO mes desde que o mes passou a
    ser o do caixa. Somando as duas, todo mes com cartao apareceria com o dobro
    do gasto - e o ano inteiro junto."""
    lancar(
        client, casa, casa["cartao"], booked_on="2026-04-10", amount="3000.00",
        direction="SAIDA", category_id=casa["cat"]["despesas.mercado"],
    )
    lancar(
        client, casa, casa["corrente"], booked_on="2026-05-05", amount="3000.00",
        direction="SAIDA", description="PAGAMENTO FATURA CARTAO",
        category_id=casa["cat"]["transferencias.pagamento_cartao"],
    )
    maio = calendario(client, casa)["months"][4]
    assert Decimal(maio["saiu"]) == Decimal("3000.00")


def test_o_acumulado_do_ano_soma_os_doze(client, casa):
    lancar(
        client, casa, casa["corrente"], booked_on="2026-02-05", amount="8000.00",
        direction="ENTRADA", category_id=casa["cat"]["receitas.ativa_fixa.pro_labore"],
    )
    lancar(
        client, casa, casa["corrente"], booked_on="2026-07-05", amount="5000.00",
        direction="ENTRADA", category_id=casa["cat"]["receitas.ativa_fixa.pro_labore"],
    )
    lancar(
        client, casa, casa["corrente"], booked_on="2026-07-20", amount="1200.00",
        direction="SAIDA", category_id=casa["cat"]["despesas.mercado"],
    )
    dados = calendario(client, casa)
    assert Decimal(dados["ano"]["entrou"]) == Decimal("13000.00")
    assert Decimal(dados["ano"]["saiu"]) == Decimal("1200.00")
    assert Decimal(dados["ano"]["net"]) == Decimal("11800.00")


def test_o_ano_passado_nao_entra_no_deste_ano(client, casa):
    lancar(
        client, casa, casa["corrente"], booked_on="2025-12-20", amount="900.00",
        direction="SAIDA", category_id=casa["cat"]["despesas.mercado"],
    )
    assert Decimal(calendario(client, casa, 2026)["ano"]["saiu"]) == Decimal("0.00")
    assert Decimal(calendario(client, casa, 2025)["ano"]["saiu"]) == Decimal("900.00")


def test_o_resumo_de_hoje_vem_junto(client, casa):
    """Patrimonio, reservas e o ultimo mes FECHADO - o mes corrente nao serve de
    comparacao, porque no dia 3 ele esta vazio."""
    dados = calendario(client, casa)
    assert "patrimonio" in dados["hoje"]
    assert "reservas" in dados["hoje"]
    assert "gastos_mes_anterior" in dados["hoje"]
    # o mes anterior e sempre o primeiro dia de um mes, e nunca o mes de hoje
    from datetime import date

    anterior = date.fromisoformat(dados["hoje"]["mes_anterior"])
    assert anterior.day == 1
    assert (anterior.year, anterior.month) != (date.today().year, date.today().month)


def test_a_compra_no_cartao_aparece_no_mes_da_fatura(client, casa):
    """O calendario usa o mesmo mes do resto do sistema: o do caixa."""
    lancar(
        client, casa, casa["cartao"], booked_on="2026-06-26", amount="400.00",
        direction="SAIDA", category_id=casa["cat"]["despesas.mercado"],
    )
    meses = calendario(client, casa)["months"]
    # comprou dia 26 com fechamento no 25: so e cobrada na fatura de agosto
    assert Decimal(meses[6]["saiu"]) == Decimal("0.00")
    assert Decimal(meses[7]["saiu"]) == Decimal("400.00")
