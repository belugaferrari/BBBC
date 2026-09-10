"""Patrimonio, avisos, extratos e pontos ponta a ponta."""

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
    from app.cli import seed_family

    suffix = uuid.uuid4().hex[:8]
    email = f"felipe.av.{suffix}@exemplo.com"
    family_id = seed_family(
        name=f"Familia {suffix}", titular="Felipe", titular_email=email,
        titular_password="segredo-de-teste", conjuge="Clarissa",
        conjuge_email=f"clarissa.av.{suffix}@exemplo.com",
        conjuge_password="segredo-de-teste", dependentes=[],
    )
    auth = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "segredo-de-teste"}
    ).json()
    headers = {"Authorization": f"Bearer {auth['access_token']}"}
    return {"family_id": family_id, "headers": headers, "member_id": auth["member_id"]}


# ------------------------------------------------------- patrimonio --------
def test_cadastra_apartamento_e_terreno(client, familia):
    apto = client.post(
        "/api/v1/holdings",
        json={
            "kind": "IMOVEL", "name": "Apartamento", "acquired_on": "2019-03-15",
            "acquisition_value": "620000.00", "current_value": "850000.00",
            "ir_declared_value": "620000.00", "address": "Rua X, 100",
        },
        headers=familia["headers"],
    )
    assert apto.status_code == 201, apto.text
    assert float(apto.json()["unrealized_gain"]) == 230000.0
    # a Receita declara pelo custo de aquisicao, nao pelo valor de mercado
    assert float(apto.json()["ir_declared_value"]) == 620000.0

    terreno = client.post(
        "/api/v1/holdings",
        json={"kind": "TERRENO", "name": "Terreno", "current_value": "180000.00"},
        headers=familia["headers"],
    )
    assert terreno.status_code == 201

    lista = client.get("/api/v1/holdings", headers=familia["headers"]).json()
    assert {h["name"] for h in lista} == {"Apartamento", "Terreno"}


def test_participacao_precisa_do_percentual(client, familia):
    resposta = client.post(
        "/api/v1/holdings",
        json={"kind": "PARTICIPACAO", "name": "Checkmotor", "current_value": "400000"},
        headers=familia["headers"],
    )
    assert resposta.status_code == 422
    assert "percentual" in resposta.json()["detail"]


def test_participacao_fica_na_sua_propria_lista(client, familia):
    client.post(
        "/api/v1/holdings",
        json={"kind": "IMOVEL", "name": "Apartamento", "current_value": "850000"},
        headers=familia["headers"],
    )
    client.post(
        "/api/v1/holdings",
        json={
            "kind": "PARTICIPACAO", "name": "Checkmotor", "current_value": "400000",
            "ownership_percentage": "60.0", "company_cnpj": "12345678000199",
        },
        headers=familia["headers"],
    )

    participacoes = client.get(
        "/api/v1/holdings", params={"kind": "PARTICIPACAO"}, headers=familia["headers"]
    ).json()
    assert len(participacoes) == 1
    assert float(participacoes[0]["ownership_percentage"]) == 60.0


def test_reavaliacao_atualiza_o_valor_e_guarda_o_historico(client, familia):
    bem = client.post(
        "/api/v1/holdings",
        json={
            "kind": "IMOVEL", "name": "Apartamento", "acquired_on": "2024-01-01",
            "acquisition_value": "620000", "current_value": "620000",
        },
        headers=familia["headers"],
    ).json()

    client.post(
        f"/api/v1/holdings/{bem['id']}/valuations",
        json={"valued_on": "2026-01-01", "value": "850000", "source": "avaliacao"},
        headers=familia["headers"],
    )

    historico = client.get(
        f"/api/v1/holdings/{bem['id']}/valuations", headers=familia["headers"]
    ).json()
    assert float(historico["holding"]["current_value"]) == 850000.0
    assert len(historico["series"]) == 2
    assert float(historico["series"][1]["change"]) == pytest.approx(0.3710, abs=1e-3)


def test_patrimonio_total_soma_contas_e_bens(client, familia):
    client.post(
        "/api/v1/accounts",
        json={"name": "Conta", "type": "CONTA_CORRENTE", "current_balance": "30000.00"},
        headers=familia["headers"],
    )
    client.post(
        "/api/v1/holdings",
        json={"kind": "IMOVEL", "name": "Apartamento", "current_value": "850000"},
        headers=familia["headers"],
    )

    total = client.get("/api/v1/net-worth", headers=familia["headers"]).json()
    assert float(total["liquid"]) == 30000.0
    assert float(total["holdings"]) == 850000.0
    assert float(total["total"]) == 880000.0
    # a maior parte do patrimonio nao paga a escola no mes que vem
    assert float(total["illiquid_share"]) > 0.9


def test_bem_de_outra_familia_nao_aparece(client, familia):
    from app.cli import seed_family

    suffix = uuid.uuid4().hex[:8]
    email = f"outro.av.{suffix}@exemplo.com"
    seed_family(
        name=f"Outra {suffix}", titular="Outro", titular_email=email,
        titular_password="segredo-de-teste", conjuge=None, conjuge_email=None,
        conjuge_password=None, dependentes=[],
    )
    outro = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "segredo-de-teste"}
    ).json()

    client.post(
        "/api/v1/holdings",
        json={"kind": "IMOVEL", "name": "Apartamento", "current_value": "850000"},
        headers=familia["headers"],
    )
    lista = client.get(
        "/api/v1/holdings",
        headers={"Authorization": f"Bearer {outro['access_token']}"},
    ).json()
    assert lista == []


# ------------------------------------------------- extratos ----------------
def test_checklist_mostra_de_quais_bancos_falta_extrato(client, familia):
    client.post(
        "/api/v1/accounts",
        json={"name": "Itau", "type": "CONTA_CORRENTE"},
        headers=familia["headers"],
    )
    client.post(
        "/api/v1/accounts",
        json={"name": "Nubank", "type": "CARTAO_CREDITO"},
        headers=familia["headers"],
    )

    resultado = client.get(
        "/api/v1/statements/checklist", headers=familia["headers"]
    ).json()
    assert resultado["expected"] == 2
    assert resultado["received"] == 0
    assert not resultado["complete"]
    assert {c["name"] for c in resultado["pending_list"]} == {"Itau", "Nubank"}


# ------------------------------------------------- pontos ------------------
def test_cadastra_programa_e_lanca_pontos(client, familia):
    programa = client.post(
        "/api/v1/card-programs",
        json={
            "name": "Livelo", "card_name": "Itau Visa Infinite",
            "points_per_currency": "2.2", "currency_basis": "USD",
            "point_value_brl": "0.02",
        },
        headers=familia["headers"],
    ).json()

    client.post(
        f"/api/v1/card-programs/{programa['id']}/movements",
        json={"moved_on": date.today().isoformat(), "kind": "ACUMULO", "points": "32000"},
        headers=familia["headers"],
    )
    depois = client.post(
        f"/api/v1/card-programs/{programa['id']}/movements",
        json={"moved_on": date.today().isoformat(), "kind": "RESGATE", "points": "-12000"},
        headers=familia["headers"],
    ).json()

    assert float(depois["balance"]) == 20000.0
    assert float(depois["balance_value_brl"]) == 400.0


def test_estimativa_de_pontos_de_uma_compra(client, familia):
    programa = client.post(
        "/api/v1/card-programs",
        json={"name": "Livelo", "points_per_currency": "2.2", "currency_basis": "USD"},
        headers=familia["headers"],
    ).json()

    estimativa = client.post(
        f"/api/v1/card-programs/{programa['id']}/estimate",
        json={"amount_brl": "1000.00", "usd_rate": "5.00"},
        headers=familia["headers"],
    ).json()
    assert float(estimativa["points"]) == 440.0

    sem_cotacao = client.post(
        f"/api/v1/card-programs/{programa['id']}/estimate",
        json={"amount_brl": "1000.00"},
        headers=familia["headers"],
    )
    assert sem_cotacao.status_code == 422


# ------------------------------------------------- avisos ------------------
def test_conta_a_vencer_gera_aviso(client, familia):
    from sqlalchemy import text

    from app.db.session import SessionLocal

    conta = client.post(
        "/api/v1/accounts",
        json={"name": "Conta", "type": "CONTA_CORRENTE"},
        headers=familia["headers"],
    ).json()

    with SessionLocal() as db:
        db.execute(
            text(
                """
                INSERT INTO recurring_transactions
                    (family_id, account_id, owner_member_id, description, amount,
                     direction, rrule, next_run_on, is_bill, remind_days_before)
                VALUES (:f, :a, :m, 'Conta de luz', 450.00, 'SAIDA',
                        'FREQ=MONTHLY', :vence, true, 3)
                """
            ),
            {
                "f": familia["family_id"], "a": conta["id"], "m": familia["member_id"],
                "vence": date.today() + timedelta(days=2),
            },
        )
        db.commit()

    resultado = client.post("/api/v1/alerts/refresh", headers=familia["headers"]).json()
    assert resultado["novos"] >= 1

    avisos = client.get("/api/v1/alerts", headers=familia["headers"]).json()
    luz = next(a for a in avisos if "luz" in a["title"].lower())
    assert "vence em 2 dias" in luz["title"]
    assert "R$ 450,00" in luz["body"]


def test_refresh_repetido_nao_duplica_o_aviso(client, familia):
    from sqlalchemy import text

    from app.db.session import SessionLocal

    with SessionLocal() as db:
        db.execute(
            text(
                """
                INSERT INTO recurring_transactions
                    (family_id, owner_member_id, description, amount, direction,
                     rrule, next_run_on, is_bill)
                VALUES (:f, :m, 'Escola', 6800.00, 'SAIDA', 'FREQ=MONTHLY', :vence, true)
                """
            ),
            {
                "f": familia["family_id"], "m": familia["member_id"],
                "vence": date.today() + timedelta(days=1),
            },
        )
        db.commit()

    primeiro = client.post("/api/v1/alerts/refresh", headers=familia["headers"]).json()
    segundo = client.post("/api/v1/alerts/refresh", headers=familia["headers"]).json()

    assert primeiro["novos"] >= 1
    assert segundo["novos"] == 0        # o mesmo aviso nao nasce duas vezes


def test_registrar_aparelho_para_receber_push(client, familia):
    resposta = client.post(
        "/api/v1/notification-targets",
        json={
            "channel": "PUSH", "address": "ExponentPushToken[abc123def456]",
            "device_name": "iPhone do Felipe", "platform": "ios",
        },
        headers=familia["headers"],
    )
    assert resposta.status_code == 201
    assert resposta.json()["created"] is True

    # registrar de novo o mesmo aparelho nao cria destino duplicado
    repetido = client.post(
        "/api/v1/notification-targets",
        json={"channel": "PUSH", "address": "ExponentPushToken[abc123def456]"},
        headers=familia["headers"],
    )
    assert repetido.json()["created"] is False

    destinos = client.get("/api/v1/notification-targets", headers=familia["headers"]).json()
    assert len(destinos) == 1
    # o token nao serve para o usuario ler, e nao deve vazar inteiro na tela
    assert destinos[0]["address"].endswith("…")


def test_aviso_novo_entra_na_fila_de_cada_destino(client, familia):
    from sqlalchemy import text

    from app.db.session import SessionLocal

    client.post(
        "/api/v1/notification-targets",
        json={"channel": "EMAIL", "address": "felipe@exemplo.com"},
        headers=familia["headers"],
    )
    with SessionLocal() as db:
        db.execute(
            text(
                """
                INSERT INTO recurring_transactions
                    (family_id, owner_member_id, description, amount, direction,
                     rrule, next_run_on, is_bill)
                VALUES (:f, :m, 'Plano de saude', 2400.00, 'SAIDA', 'FREQ=MONTHLY',
                        :vence, true)
                """
            ),
            {
                "f": familia["family_id"], "m": familia["member_id"],
                "vence": date.today() + timedelta(days=1),
            },
        )
        db.commit()

    client.post("/api/v1/alerts/refresh", headers=familia["headers"])

    with SessionLocal() as db:
        pendentes = db.execute(
            text(
                """
                SELECT count(*) FROM notification_deliveries d
                  JOIN alerts a ON a.id = d.alert_id
                 WHERE a.family_id = :f AND d.status = 'PENDENTE'
                """
            ),
            {"f": familia["family_id"]},
        ).scalar_one()
    assert pendentes >= 1
