"""Autenticar nao e autorizar.

Estes testes criam DUAS familias e verificam que o token de uma nao alcanca
nada da outra, mesmo conhecendo os UUIDs.
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


def _nova_familia(client) -> dict:
    from sqlalchemy import text

    from app.cli import seed_family
    from app.db.session import SessionLocal

    suffix = uuid.uuid4().hex[:8]
    email = f"titular.{suffix}@exemplo.com"
    family_id = seed_family(
        name=f"Familia {suffix}",
        titular="Titular",
        titular_email=email,
        titular_password="segredo-de-teste",
        conjuge=None,
        conjuge_email=None,
        conjuge_password=None,
        dependentes=["Filha"],
    )
    auth = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "segredo-de-teste"}
    ).json()
    headers = {"Authorization": f"Bearer {auth['access_token']}"}

    conta = client.post(
        "/api/v1/accounts",
        json={"name": "Conta", "type": "CONTA_CORRENTE"},
        headers=headers,
    ).json()

    with SessionLocal() as db:
        categoria = str(
            db.execute(
                text(
                    "SELECT id FROM categories WHERE family_id = :f"
                    " AND path = 'despesas.mercado'"
                ),
                {"f": family_id},
            ).scalar_one()
        )
        dependente = str(
            db.execute(
                text("SELECT id FROM members WHERE family_id = :f AND is_ir_dependent LIMIT 1"),
                {"f": family_id},
            ).scalar_one()
        )

    return {
        "family_id": family_id,
        "member_id": auth["member_id"],
        "headers": headers,
        "account_id": conta["id"],
        "category_id": categoria,
        "dependente_id": dependente,
    }


@pytest.fixture(scope="module")
def familias(client) -> tuple[dict, dict]:
    return _nova_familia(client), _nova_familia(client)


def test_nao_da_para_lancar_na_conta_de_outra_familia(client, familias):
    nossa, outra = familias
    response = client.post(
        "/api/v1/transactions",
        json={
            "account_id": outra["account_id"],
            "booked_on": date.today().isoformat(),
            "amount": "100.00",
            "direction": "SAIDA",
            "description": "Tentativa",
        },
        headers=nossa["headers"],
    )
    assert response.status_code == 404


def test_nao_da_para_usar_categoria_de_outra_familia(client, familias):
    nossa, outra = familias
    response = client.post(
        "/api/v1/transactions",
        json={
            "account_id": nossa["account_id"],
            "booked_on": date.today().isoformat(),
            "amount": "100.00",
            "direction": "SAIDA",
            "description": "Tentativa",
            "category_id": outra["category_id"],
        },
        headers=nossa["headers"],
    )
    assert response.status_code == 404


def test_nao_da_para_ler_o_ir_de_outra_familia(client, familias):
    """O furo mais serio antes da correcao: bastava adivinhar o UUID do membro."""
    nossa, outra = familias
    response = client.get(
        f"/api/v1/tax/{date.today().year}",
        params={"member_id": outra["member_id"]},
        headers=nossa["headers"],
    )
    assert response.status_code == 404
    # e o proprio continua funcionando
    assert client.get(
        f"/api/v1/tax/{date.today().year}", headers=nossa["headers"]
    ).status_code == 200


def test_nao_da_para_marcar_deducao_no_dependente_de_outra_familia(client, familias):
    nossa, outra = familias
    response = client.post(
        "/api/v1/transactions",
        json={
            "account_id": nossa["account_id"],
            "booked_on": date.today().isoformat(),
            "amount": "500.00",
            "direction": "SAIDA",
            "description": "Consulta",
            "ir_deduction_member_id": outra["dependente_id"],
        },
        headers=nossa["headers"],
    )
    assert response.status_code == 404


def test_nao_da_para_criar_teto_em_categoria_de_outra_familia(client, familias):
    nossa, outra = familias
    response = client.post(
        "/api/v1/budget-caps",
        json={"category_id": outra["category_id"], "amount": "1000.00"},
        headers=nossa["headers"],
    )
    assert response.status_code == 404


def test_nao_da_para_simular_meta_de_outra_familia(client, familias):
    nossa, outra = familias
    criada = client.post(
        "/api/v1/goals",
        json={
            "name": "Disney",
            "target_amount": "100000.00",
            "target_date": "2030-01-01",
        },
        headers=outra["headers"],
    ).json()

    response = client.post(
        f"/api/v1/goals/{criada['id']}/simulate",
        json={"monthly_contribution": 1000},
        headers=nossa["headers"],
    )
    assert response.status_code == 404


def test_sem_token_nada_responde(client, familias):
    for path in ("/api/v1/dashboard", "/api/v1/accounts", "/api/v1/categories"):
        assert client.get(path).status_code == 401


def test_token_adulterado_e_recusado(client, familias):
    nossa, _ = familias
    quebrado = nossa["headers"]["Authorization"] + "x"
    assert client.get(
        "/api/v1/dashboard", headers={"Authorization": quebrado}
    ).status_code == 401
