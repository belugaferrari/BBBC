"""Lancamento criado no celular com o PC desligado, e subido depois.

Subir uma fila nao e operacao confiavel: a conexao cai no meio, o aplicativo e
fechado, o usuario tenta de novo. Sem identidade propria cada retentativa
criaria um gasto novo - e duplicata em base financeira so aparece no fim do mes,
quando o total nao bate e ninguem lembra por que.
"""

from __future__ import annotations

import os
import uuid

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
def conta(client):
    from app.cli import seed_family

    sufixo = uuid.uuid4().hex[:8]
    email = f"felipe.fila.{sufixo}@exemplo.com"
    seed_family(
        name=f"Familia {sufixo}", titular="Felipe", titular_email=email,
        titular_password="segredo-de-teste", conjuge=None, conjuge_email=None,
        conjuge_password=None, dependentes=[],
    )
    auth = client.post("/api/v1/auth/login",
                       json={"email": email, "password": "segredo-de-teste"}).json()
    headers = {"Authorization": f"Bearer {auth['access_token']}"}
    conta = client.post("/api/v1/accounts",
                        json={"name": "Carteira", "type": "DINHEIRO"},
                        headers=headers).json()
    return {"headers": headers, "account_id": conta["id"]}


def gasto_em_dinheiro(conta, client_key=None):
    """O caso que motivou tudo: dinheiro em especie nunca aparece em extrato."""
    corpo = {
        "account_id": conta["account_id"],
        "booked_on": "2026-10-01",
        "amount": "45.00",
        "direction": "SAIDA",
        "description": "Feira da praca",
    }
    if client_key:
        corpo["client_key"] = client_key
    return corpo


def lancar(client, conta, corpo):
    return client.post("/api/v1/transactions", json=corpo, headers=conta["headers"])


def quantos(client, conta) -> int:
    linhas = client.get("/api/v1/transactions",
                        params={"start": "2026-01-01", "end": "2026-12-31"},
                        headers=conta["headers"]).json()
    return len(linhas)


def test_mesma_chave_nao_duplica(client, conta):
    """A fila subindo duas vezes - conexao caiu, usuario tentou de novo."""
    chave = str(uuid.uuid4())
    primeira = lancar(client, conta, gasto_em_dinheiro(conta, chave))
    assert primeira.status_code == 201, primeira.text

    segunda = lancar(client, conta, gasto_em_dinheiro(conta, chave))
    assert segunda.status_code == 201, segunda.text

    assert quantos(client, conta) == 1
    assert primeira.json()["id"] == segunda.json()["id"], (
        "o reenvio tem que devolver o MESMO lancamento, nao um parecido"
    )


def test_tres_tentativas_seguidas_tambem_nao_duplicam(client, conta):
    chave = str(uuid.uuid4())
    ids = {lancar(client, conta, gasto_em_dinheiro(conta, chave)).json()["id"]
           for _ in range(3)}
    assert len(ids) == 1
    assert quantos(client, conta) == 1


def test_chaves_diferentes_criam_lancamentos_diferentes(client, conta):
    """Dois cafes de R$ 45 no mesmo dia sao dois gastos, nao um repetido."""
    for _ in range(2):
        resposta = lancar(client, conta, gasto_em_dinheiro(conta, str(uuid.uuid4())))
        assert resposta.status_code == 201
    assert quantos(client, conta) == 2


def test_sem_chave_segue_como_sempre(client, conta):
    """O lancamento feito direto no app, com conexao, nao precisa de chave."""
    for _ in range(2):
        assert lancar(client, conta, gasto_em_dinheiro(conta)).status_code == 201
    assert quantos(client, conta) == 2


def test_a_chave_de_uma_familia_nao_alcanca_a_outra(client, conta):
    """O indice e por familia. Chave igual em familias diferentes e coincidencia,
    nao reenvio - e esconder o lancamento da segunda seria perder dado."""
    chave = str(uuid.uuid4())
    assert lancar(client, conta, gasto_em_dinheiro(conta, chave)).status_code == 201

    from app.cli import seed_family
    sufixo = uuid.uuid4().hex[:8]
    email = f"outra.familia.{sufixo}@exemplo.com"
    seed_family(name=f"Outra {sufixo}", titular="Outro", titular_email=email,
                titular_password="segredo-de-teste", conjuge=None, conjuge_email=None,
                conjuge_password=None, dependentes=[])
    auth = client.post("/api/v1/auth/login",
                       json={"email": email, "password": "segredo-de-teste"}).json()
    outra = {"headers": {"Authorization": f"Bearer {auth['access_token']}"}}
    outra["account_id"] = client.post(
        "/api/v1/accounts", json={"name": "Carteira", "type": "DINHEIRO"},
        headers=outra["headers"]).json()["id"]

    resposta = lancar(client, outra, gasto_em_dinheiro(outra, chave))
    assert resposta.status_code == 201, resposta.text
    assert quantos(client, outra) == 1
