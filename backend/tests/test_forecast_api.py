"""Evolutivo e segmentacao por categoria, ponta a ponta contra o banco."""

from __future__ import annotations

import os
import uuid
from datetime import date, timedelta

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
def familia(client):
    from sqlalchemy import text

    from app.cli import seed_family
    from app.db.session import SessionLocal

    suffix = uuid.uuid4().hex[:8]
    email = f"felipe.fc.{suffix}@exemplo.com"
    family_id = seed_family(
        name=f"Familia {suffix}",
        titular="Felipe",
        titular_email=email,
        titular_password="segredo-de-teste",
        conjuge="Clarissa",
        conjuge_email=f"clarissa.fc.{suffix}@exemplo.com",
        conjuge_password="segredo-de-teste",
        dependentes=[],
    )
    auth = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "segredo-de-teste"}
    ).json()
    headers = {"Authorization": f"Bearer {auth['access_token']}"}

    conta = client.post(
        "/api/v1/accounts",
        json={"name": "Conta", "type": "CONTA_CORRENTE", "is_shared": True,
              "current_balance": "10000.00"},
        headers=headers,
    ).json()

    with SessionLocal() as db:
        categorias = {
            linha[0]: str(linha[1])
            for linha in db.execute(
                text("SELECT path::text, id FROM categories WHERE family_id = :f"),
                {"f": family_id},
            )
        }
        clarissa = str(
            db.execute(
                text("SELECT id FROM members WHERE family_id = :f AND role = 'CONJUGE'"),
                {"f": family_id},
            ).scalar_one()
        )

    return {
        "family_id": family_id,
        "headers": headers,
        "account_id": conta["id"],
        "felipe": auth["member_id"],
        "clarissa": clarissa,
        "cat": categorias,
    }


def lancar(client, familia, **kwargs):
    corpo = {"account_id": familia["account_id"], **kwargs}
    r = client.post("/api/v1/transactions", json=corpo, headers=familia["headers"])
    assert r.status_code == 201, r.text
    return r.json()


# ------------------------------------------------------- responsavel --------
def test_responsavel_e_opcional_e_assume_o_dono_da_conta(client, familia):
    tx = lancar(
        client, familia, booked_on=date.today().isoformat(), amount="120.00",
        direction="SAIDA", description="Padaria",
    )
    assert tx["owner_member_id"] == familia["felipe"]


def test_da_para_dizer_que_o_gasto_e_da_clarissa(client, familia):
    tx = lancar(
        client, familia, booked_on=date.today().isoformat(), amount="300.00",
        direction="SAIDA", description="Farmácia",
        owner_member_id=familia["clarissa"],
    )
    assert tx["owner_member_id"] == familia["clarissa"]


def test_responsavel_pode_ser_corrigido_depois(client, familia):
    tx = lancar(
        client, familia, booked_on=date.today().isoformat(), amount="80.00",
        direction="SAIDA", description="Uber",
    )
    corrigido = client.patch(
        f"/api/v1/transactions/{tx['id']}",
        json={"owner_member_id": familia["clarissa"]},
        headers=familia["headers"],
    )
    assert corrigido.status_code == 200
    assert corrigido.json()["owner_member_id"] == familia["clarissa"]


def test_nao_da_para_apontar_para_membro_de_outra_familia(client, familia):
    resposta = client.post(
        "/api/v1/transactions",
        json={
            "account_id": familia["account_id"],
            "booked_on": date.today().isoformat(),
            "amount": "10.00", "direction": "SAIDA", "description": "x",
            "owner_member_id": str(uuid.uuid4()),
        },
        headers=familia["headers"],
    )
    assert resposta.status_code == 404


# -------------------------------------------------- gastos por categoria ----
def test_gastos_agrupados_por_categoria(client, familia):
    hoje = date.today().replace(day=10)
    cat = familia["cat"]
    lancar(client, familia, booked_on=hoje.isoformat(), amount="4200.00",
           direction="SAIDA", description="Mercado",
           category_id=cat["despesas.mercado"])
    lancar(client, familia, booked_on=hoje.isoformat(), amount="6800.00",
           direction="SAIDA", description="Escola",
           category_id=cat["despesas.educacao.escola"])
    lancar(client, familia, booked_on=hoje.isoformat(), amount="890.00",
           direction="SAIDA", description="Bambu Lab",
           category_id=cat["despesas.marketplaces"])

    resposta = client.get(
        "/api/v1/transactions/by-category",
        params={"start": hoje.replace(day=1).isoformat(), "end": hoje.isoformat(), "depth": 2},
        headers=familia["headers"],
    )
    assert resposta.status_code == 200, resposta.text
    dados = resposta.json()

    grupos = {g["name"]: g for g in dados["categories"]}
    assert float(grupos["Mercado"]["total"]) == 4200.0
    assert float(grupos["Educacao"]["total"]) == 6800.0
    assert float(grupos["Market places"]["total"]) == 890.0
    # participacao de cada grupo no total de 11.890
    assert float(grupos["Educacao"]["share"]) == pytest.approx(0.5719, abs=1e-3)


def test_profundidade_muda_o_nivel_do_agrupamento(client, familia):
    hoje = date.today().replace(day=10)
    cat = familia["cat"]
    lancar(client, familia, booked_on=hoje.isoformat(), amount="4200.00",
           direction="SAIDA", description="Mercado",
           category_id=cat["despesas.mercado"])
    lancar(client, familia, booked_on=hoje.isoformat(), amount="6800.00",
           direction="SAIDA", description="Escola",
           category_id=cat["despesas.educacao.escola"])

    def nomes(depth):
        r = client.get(
            "/api/v1/transactions/by-category",
            params={"start": hoje.replace(day=1).isoformat(),
                    "end": hoje.isoformat(), "depth": depth},
            headers=familia["headers"],
        )
        return {g["name"] for g in r.json()["categories"]}

    # na arvore da familia, Mercado e Educacao ja sao filhos diretos de Despesas
    assert nomes(1) == {"Despesas"}
    assert nomes(2) == {"Mercado", "Educacao"}
    assert nomes(3) == {"Mercado", "Escola (dedutivel)"}


def test_lancamento_sem_categoria_nao_some_do_agrupamento(client, familia):
    hoje = date.today().replace(day=10)
    lancar(client, familia, booked_on=hoje.isoformat(), amount="55.00",
           direction="SAIDA", description="Débito desconhecido")

    resposta = client.get(
        "/api/v1/transactions/by-category",
        params={"start": hoje.replace(day=1).isoformat(), "end": hoje.isoformat()},
        headers=familia["headers"],
    )
    grupos = {g["name"] for g in resposta.json()["categories"]}
    assert "Sem categoria" in grupos


def test_quanto_cada_um_gastou(client, familia):
    hoje = date.today().replace(day=10)
    lancar(client, familia, booked_on=hoje.isoformat(), amount="1000.00",
           direction="SAIDA", description="Do Felipe")
    lancar(client, familia, booked_on=hoje.isoformat(), amount="400.00",
           direction="SAIDA", description="Da Clarissa",
           owner_member_id=familia["clarissa"])

    resposta = client.get(
        "/api/v1/transactions/by-category",
        params={"start": hoje.replace(day=1).isoformat(), "end": hoje.isoformat()},
        headers=familia["headers"],
    )
    por_pessoa = {p["name"]: float(p["total"]) for p in resposta.json()["by_member"]}
    assert por_pessoa["Felipe"] == 1000.0
    assert por_pessoa["Clarissa"] == 400.0


# ------------------------------------------------------------- evolutivo ----
def test_evolutivo_projeta_os_meses_pedidos(client, familia):
    resposta = client.get(
        "/api/v1/forecast", params={"months": 6}, headers=familia["headers"]
    )
    assert resposta.status_code == 200, resposta.text
    dados = resposta.json()

    assert len(dados["projection"]) == 6
    assert dados["summary"]["months"] == 6
    # o saldo de abertura vem das contas
    assert float(dados["projection"][0]["opening_balance"]) == 10000.0


def test_evolutivo_traz_o_lancamento_futuro_como_esperado(client, familia):
    proximo_mes = (date.today().replace(day=1) + timedelta(days=40)).replace(day=10)
    lancar(client, familia, booked_on=proximo_mes.isoformat(), amount="890.00",
           direction="SAIDA", description="Parcela cartão",
           installment_no=2, installment_total=3)

    dados = client.get(
        "/api/v1/forecast", params={"months": 3}, headers=familia["headers"]
    ).json()

    mes = next(
        m for m in dados["projection"]
        if m["month"].startswith(proximo_mes.strftime("%Y-%m"))
    )
    assert float(mes["outflow_by_kind"]["ESPERADO"]) == 890.0
    assert any("2/3" in item["label"] for item in mes["items"])


def test_evolutivo_separa_as_tres_origens(client, familia):
    dados = client.get(
        "/api/v1/forecast", params={"months": 4}, headers=familia["headers"]
    ).json()
    assert set(dados["sources"]) == {
        "recurring_rules", "scheduled_transactions", "estimated_categories", "history_months"
    }
    for mes in dados["projection"]:
        for origem in mes["outflow_by_kind"]:
            assert origem in {"FIXO", "ESPERADO", "ESTIMADO"}
