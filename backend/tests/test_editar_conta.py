"""Corrigir uma conta depois de cadastrada.

"Eu preciso poder EDITAR as informacoes das Contas que mando pro sistema. muitas
mudancas."

Cadastro de conta se faz uma vez e se convive com ele por anos. Sem edicao, a
unica saida era arquivar e criar outra - e o historico ficava na conta velha,
partido em duas, com o saldo de uma e os lancamentos da outra.
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
    from app.cli import seed_family

    sufixo = uuid.uuid4().hex[:8]
    email = f"felipe.conta.{sufixo}@exemplo.com"
    seed_family(
        name=f"Familia {sufixo}",
        titular="Felipe",
        titular_email=email,
        titular_password="segredo-de-teste",
        conjuge="Clarissa",
        conjuge_email=f"clarissa.conta.{sufixo}@exemplo.com",
        conjuge_password="segredo-de-teste",
        dependentes=[],
    )
    auth = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "segredo-de-teste"}
    ).json()
    return {"headers": {"Authorization": f"Bearer {auth['access_token']}"}}


def criar(client, casa, **kw):
    resposta = client.post(
        "/api/v1/accounts", json={"name": "Banco", **kw}, headers=casa["headers"]
    )
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def editar(client, casa, conta_id: str, **kw):
    return client.patch(
        f"/api/v1/accounts/{conta_id}", json=kw, headers=casa["headers"]
    )


def test_trocar_o_nome(client, casa):
    conta = criar(client, casa)
    resposta = editar(client, casa, conta["id"], name="Itau da Clarissa")
    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["name"] == "Itau da Clarissa"


def test_o_numero_da_conta_nao_entra_pelo_nome(client, casa):
    """A mesma regra do cadastro vale na edicao: o que nao e gravado nao vaza
    depois."""
    conta = criar(client, casa)
    resposta = editar(client, casa, conta["id"], name="Itau 1234-5")
    assert resposta.status_code == 200, resposta.text
    assert "1234" not in resposta.json()["name"]


def test_informar_os_dias_da_fatura_depois(client, casa):
    """O caso mais util: o cartao foi cadastrado as pressas e os dias da fatura
    ficaram para depois. Sao eles que dizem em que mes cada compra sai da
    conta."""
    cartao = criar(client, casa, type="CARTAO_CREDITO")
    assert cartao["statement_close_day"] is None

    resposta = editar(
        client, casa, cartao["id"], statement_close_day=25, statement_due_day=9
    )
    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["statement_close_day"] == 25
    assert resposta.json()["statement_due_day"] == 9


def test_so_o_que_foi_enviado_muda(client, casa):
    """Mandar o dia do vencimento nao pode apagar o limite do cartao."""
    cartao = criar(client, casa, type="CARTAO_CREDITO", credit_limit="15000.00")
    editar(client, casa, cartao["id"], statement_due_day=9)
    depois = client.get("/api/v1/accounts", headers=casa["headers"]).json()
    atualizada = next(c for c in depois if c["id"] == cartao["id"])
    assert Decimal(atualizada["credit_limit"]) == Decimal("15000.00")
    assert atualizada["name"] == "Banco"


def test_a_conta_que_era_de_um_vira_conjunta(client, casa):
    conta = criar(client, casa)
    assert conta["is_shared"] is False
    assert editar(client, casa, conta["id"], is_shared=True).json()["is_shared"] is True


def test_virar_cartao_de_credito(client, casa):
    """O tipo e o que decide se a compra espera a fatura. Cadastrar o cartao
    como conta corrente por engano era um erro sem conserto."""
    conta = criar(client, casa)
    resposta = editar(client, casa, conta["id"], type="CARTAO_CREDITO")
    assert resposta.json()["type"] == "CARTAO_CREDITO"


def test_a_conta_de_outra_familia_nao_e_minha(client, casa):
    assert editar(client, casa, str(uuid.uuid4()), name="x").status_code == 404


def test_dia_de_fatura_impossivel_e_recusado(client, casa):
    cartao = criar(client, casa, type="CARTAO_CREDITO")
    assert editar(client, casa, cartao["id"], statement_due_day=0).status_code == 422
    assert editar(client, casa, cartao["id"], statement_close_day=45).status_code == 422
