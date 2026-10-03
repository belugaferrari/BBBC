"""A meta muda de um mes para o outro, e o passado fica como estava.

"se eu mudar os valores das metas, a informacao nao pode retroagir nos graficos
de meses anteriores" - palavras dele, e o pedido tem razao de ser: um grafico de
setembro julgado por uma meta criada em outubro mente sobre setembro. Numero que
muda sozinho no passado e pior que numero ausente, porque ninguem desconfia dele.

A rota ja fez o contrario: substituia a meta no lugar e ainda puxava o
`starts_on` para tras, entao mudar o teto hoje reescrevia todos os meses
fechados. Estes testes guardam a correcao.
"""

from __future__ import annotations

import os
import uuid
from datetime import date

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
    """Familia nova a cada teste: metas sao estado, e estado vaza entre testes."""
    from sqlalchemy import text

    from app.cli import seed_family
    from app.db.session import SessionLocal

    sufixo = uuid.uuid4().hex[:8]
    email = f"felipe.meta.{sufixo}@exemplo.com"
    family_id = seed_family(
        name=f"Familia {sufixo}",
        titular="Felipe",
        titular_email=email,
        titular_password="segredo-de-teste",
        conjuge="Clarissa",
        conjuge_email=f"clarissa.meta.{sufixo}@exemplo.com",
        conjuge_password="segredo-de-teste",
        dependentes=["Filha"],
    )
    auth = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "segredo-de-teste"}
    ).json()
    headers = {"Authorization": f"Bearer {auth['access_token']}"}
    conta = client.post(
        "/api/v1/accounts", json={"name": "Itau", "type": "CONTA_CORRENTE"},
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
    return {"headers": headers, "conta": conta["id"], "cat": cats}


def por_meta(client, casa, categoria: str, valor, mes: str):
    return client.post(
        "/api/v1/budget-caps",
        json={"category_id": categoria, "amount": valor, "starts_on": mes},
        headers=casa["headers"],
    ).json()


def meta_de(client, casa, mes: str, categoria_nome: str = "Mercado"):
    metas = client.get(
        "/api/v1/budget-caps", params={"month": mes}, headers=casa["headers"]
    ).json()
    achada = [m for m in metas if m["category_name"] == categoria_nome]
    return achada[0]["cap"] if achada else None


# ---------------------------------------------------------------- versao ----
def test_mudar_a_meta_em_outubro_nao_mexe_em_setembro(client, casa):
    mercado = casa["cat"]["despesas.mercado"]
    por_meta(client, casa, mercado, 2500, "2026-09-01")
    resposta = por_meta(client, casa, mercado, 2800, "2026-10-01")

    assert resposta["versionou"] is True
    assert float(resposta["valia_antes"]) == 2500.0
    assert resposta["ate"] == "2026-09-30"

    assert float(meta_de(client, casa, "2026-09-01")) == 2500.0
    assert float(meta_de(client, casa, "2026-10-01")) == 2800.0


def test_a_meta_nova_vale_para_frente(client, casa):
    mercado = casa["cat"]["despesas.mercado"]
    por_meta(client, casa, mercado, 2500, "2026-09-01")
    por_meta(client, casa, mercado, 2800, "2026-10-01")

    assert float(meta_de(client, casa, "2026-11-01")) == 2800.0
    assert float(meta_de(client, casa, "2027-03-01")) == 2800.0


def test_antes_da_primeira_meta_nao_ha_meta(client, casa):
    """Agosto aconteceu sem meta nenhuma, e tem de continuar assim."""
    mercado = casa["cat"]["despesas.mercado"]
    por_meta(client, casa, mercado, 2500, "2026-09-01")

    assert meta_de(client, casa, "2026-08-01") is None


def test_corrigir_no_mesmo_mes_nao_cria_versao(client, casa):
    """Digitar 280 em vez de 2.800 e arrumar em seguida e correcao, nao mudanca:
    nao ha passado daquela meta para preservar."""
    mercado = casa["cat"]["despesas.mercado"]
    primeira = por_meta(client, casa, mercado, 280, "2026-10-01")
    segunda = por_meta(client, casa, mercado, 2800, "2026-10-01")

    assert segunda["versionou"] is False
    assert segunda["id"] == primeira["id"]
    assert float(meta_de(client, casa, "2026-10-01")) == 2800.0

    # e continua havendo UMA meta, nao duas
    metas = client.get(
        "/api/v1/budget-caps", params={"month": "2026-10-01"}, headers=casa["headers"]
    ).json()
    assert len([m for m in metas if m["category_name"] == "Mercado"]) == 1


def test_salvar_o_mesmo_valor_nao_cria_versao(client, casa):
    mercado = casa["cat"]["despesas.mercado"]
    por_meta(client, casa, mercado, 2500, "2026-09-01")
    de_novo = por_meta(client, casa, mercado, 2500, "2026-10-01")

    assert de_novo["versionou"] is False
    assert float(meta_de(client, casa, "2026-09-01")) == 2500.0


def test_tres_versoes_seguidas_cada_mes_com_a_sua(client, casa):
    mercado = casa["cat"]["despesas.mercado"]
    por_meta(client, casa, mercado, 2000, "2026-08-01")
    por_meta(client, casa, mercado, 2500, "2026-09-01")
    por_meta(client, casa, mercado, 2800, "2026-10-01")

    assert float(meta_de(client, casa, "2026-08-01")) == 2000.0
    assert float(meta_de(client, casa, "2026-09-01")) == 2500.0
    assert float(meta_de(client, casa, "2026-10-01")) == 2800.0


# --------------------------------------------------------------- apagar -----
def test_apagar_a_meta_encerra_em_vez_de_sumir_com_o_passado(client, casa):
    """Apagar a linha inteira reescreveria o passado pelo outro lado: os meses em
    que a meta existiu de verdade apareceriam sem meta nenhuma."""
    mercado = casa["cat"]["despesas.mercado"]
    criada = por_meta(client, casa, mercado, 2500, "2026-09-01")

    resposta = client.delete(
        f"/api/v1/budget-caps/{criada['id']}",
        params={"month": "2026-10-01"},
        headers=casa["headers"],
    ).json()

    assert resposta["encerrada"] is True
    assert resposta["valeu_ate"] == "2026-09-30"
    assert float(meta_de(client, casa, "2026-09-01")) == 2500.0
    assert meta_de(client, casa, "2026-10-01") is None


def test_apagar_meta_criada_neste_mes_some_de_vez(client, casa):
    mercado = casa["cat"]["despesas.mercado"]
    criada = por_meta(client, casa, mercado, 2500, "2026-10-01")

    resposta = client.delete(
        f"/api/v1/budget-caps/{criada['id']}",
        params={"month": "2026-10-01"},
        headers=casa["headers"],
    ).json()

    assert resposta["apagada"] is True
    assert meta_de(client, casa, "2026-10-01") is None


# ------------------------------------------------- o grafico do mes ---------
def lancar(client, casa, dia: str, valor: str, categoria: str):
    return client.post(
        "/api/v1/transactions",
        json={
            "account_id": casa["conta"], "booked_on": dia, "amount": valor,
            "direction": "SAIDA", "description": "SUPERMERCADO",
            "category_id": categoria,
        },
        headers=casa["headers"],
    )


def test_o_grafico_de_cada_mes_usa_a_meta_daquele_mes(client, casa):
    """O teste que fecha o pedido: o grafico de setembro mostra a meta de
    setembro, mesmo depois de a meta ter mudado em outubro."""
    mercado = casa["cat"]["despesas.mercado"]
    por_meta(client, casa, mercado, 2500, "2026-09-01")
    por_meta(client, casa, mercado, 2800, "2026-10-01")

    setembro = client.get(
        "/api/v1/dashboard/evolucao", params={"month": "2026-09-01"},
        headers=casa["headers"],
    ).json()
    outubro = client.get(
        "/api/v1/dashboard/evolucao", params={"month": "2026-10-01"},
        headers=casa["headers"],
    ).json()

    assert float(setembro["current"]["cap"]) == 2500.0
    assert float(outubro["current"]["cap"]) == 2800.0
    # e o mes passado, visto de outubro, carrega a meta que valia nele
    assert float(outubro["previous_month"]["cap"]) == 2500.0


def test_o_acumulado_sobe_e_nunca_desce(client, casa):
    mercado = casa["cat"]["despesas.mercado"]
    lancar(client, casa, "2026-09-02", "150.00", mercado)
    lancar(client, casa, "2026-09-15", "410.00", mercado)
    lancar(client, casa, "2026-09-29", "190.00", mercado)

    dados = client.get(
        "/api/v1/dashboard/evolucao", params={"month": "2026-09-01"},
        headers=casa["headers"],
    ).json()
    serie = dados["current"]["series"]

    assert len(serie) == 30, "setembro tem 30 dias, e todos entram na curva"
    valores = [float(p["total"]) for p in serie]
    assert valores == sorted(valores), "acumulado nao pode descer"
    assert valores[0] == 0.0          # dia 1 sem gasto
    assert valores[1] == 150.0        # dia 2
    assert valores[-1] == 750.0
    assert float(dados["current"]["total"]) == 750.0


def test_dia_sem_gasto_mantem_o_valor_do_dia_anterior(client, casa):
    """A curva tem de ser continua. Pular o dia 7 porque ninguem gastou nada nele
    faria o grafico subir em degraus que nao existiram."""
    mercado = casa["cat"]["despesas.mercado"]
    lancar(client, casa, "2026-09-02", "150.00", mercado)

    serie = client.get(
        "/api/v1/dashboard/evolucao", params={"month": "2026-09-01"},
        headers=casa["headers"],
    ).json()["current"]["series"]

    assert [p["day"] for p in serie] == list(range(1, 31))
    assert all(float(p["total"]) == 150.0 for p in serie[1:])


def test_o_mes_corrente_diz_ate_que_dia_a_curva_e_real(client, casa):
    """Em mes fechado a curva vale o mes inteiro; no corrente, so ate hoje -
    desenhar reto ate o dia 31 faria o mes parecer estagnado."""
    hoje = date.today()
    corrente = client.get(
        "/api/v1/dashboard/evolucao",
        params={"month": hoje.replace(day=1).isoformat()},
        headers=casa["headers"],
    ).json()
    fechado = client.get(
        "/api/v1/dashboard/evolucao", params={"month": "2025-01-01"},
        headers=casa["headers"],
    ).json()

    assert corrente["today"] == hoje.day
    assert fechado["today"] is None


def test_amortizacao_nao_entra_na_curva_de_gasto(client, casa):
    """O que nao e consumo nao conta: amortizacao e divida virando patrimonio."""
    lancar(client, casa, "2026-09-05", "1800.00",
           casa["cat"]["despesas.financiamentos.amortizacao"])
    lancar(client, casa, "2026-09-05", "700.00",
           casa["cat"]["despesas.financiamentos.juros"])

    dados = client.get(
        "/api/v1/dashboard/evolucao", params={"month": "2026-09-01"},
        headers=casa["headers"],
    ).json()

    assert float(dados["current"]["total"]) == 700.0
