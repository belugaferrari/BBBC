"""Fluxo completo de importacao pela API: enviar, conferir, confirmar.

O caso que mais importa: importar o MESMO extrato duas vezes, e em formatos
diferentes, sem duplicar um unico lancamento.
"""

from __future__ import annotations

import os
import pathlib
import uuid
from datetime import date

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("BBBC_TEST_DATABASE_URL"),
    reason="defina BBBC_TEST_DATABASE_URL para rodar a integracao",
)

SAMPLES = pathlib.Path(__file__).resolve().parent.parent / "db" / "samples"


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def conta(client):
    """Familia nova a cada teste, para os lotes nao se contaminarem."""
    from app.cli import seed_family

    suffix = uuid.uuid4().hex[:8]
    email = f"felipe.imp.{suffix}@exemplo.com"
    seed_family(
        name=f"Familia {suffix}",
        titular="Felipe",
        titular_email=email,
        titular_password="segredo-de-teste",
        conjuge=None,
        conjuge_email=None,
        conjuge_password=None,
        dependentes=[],
    )
    auth = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "segredo-de-teste"}
    ).json()
    headers = {"Authorization": f"Bearer {auth['access_token']}"}
    account = client.post(
        "/api/v1/accounts",
        json={"name": "Conta corrente", "type": "CONTA_CORRENTE"},
        headers=headers,
    ).json()
    return {"headers": headers, "account_id": account["id"]}


def enviar(client, conta, nome: str):
    conteudo = (SAMPLES / nome).read_bytes()
    return client.post(
        "/api/v1/imports",
        data={"account_id": conta["account_id"]},
        files={"file": (nome, conteudo, "application/octet-stream")},
        headers=conta["headers"],
    )


def transacoes(client, conta) -> list[dict]:
    return client.get(
        "/api/v1/transactions",
        params={"start": "2026-01-01", "end": "2026-12-31"},
        headers=conta["headers"],
    ).json()


@pytest.mark.parametrize(
    "nome", ["extrato-exemplo.ofx", "extrato-exemplo.csv", "extrato-exemplo.pdf"]
)
def test_enviar_extrato_devolve_previsualizacao_sem_gravar(client, conta, nome):
    resposta = enviar(client, conta, nome)
    assert resposta.status_code == 201, resposta.text

    lote = resposta.json()
    assert lote["status"] == "CRIADO"
    assert lote["rows_detected"] == 5
    assert lote["rows_duplicated"] == 0
    assert lote["period_start"] == "2026-08-05"
    assert len(lote["preview"]) == 5
    assert all(item["selected"] for item in lote["preview"])

    # o passo de conferencia existe justamente para nada ser gravado antes
    assert transacoes(client, conta) == []


def test_confirmar_grava_e_atualiza_o_saldo(client, conta):
    lote = enviar(client, conta, "extrato-exemplo.ofx").json()

    confirmado = client.post(
        f"/api/v1/imports/{lote['id']}/confirm", json={}, headers=conta["headers"]
    )
    assert confirmado.status_code == 200, confirmado.text
    assert confirmado.json()["rows_imported"] == 5
    assert confirmado.json()["status"] == "CONFIRMADO"

    lancamentos = transacoes(client, conta)
    assert len(lancamentos) == 5
    assert {t["source"] for t in lancamentos} == {"IMPORT_OFX"}

    # 43.000 de entrada - 11.925,90 de saida
    contas = client.get("/api/v1/accounts", headers=conta["headers"]).json()
    assert float(contas[0]["current_balance"]) == 31074.10


def test_reenviar_o_mesmo_arquivo_nao_duplica(client, conta):
    primeiro = enviar(client, conta, "extrato-exemplo.ofx").json()
    client.post(f"/api/v1/imports/{primeiro['id']}/confirm", json={}, headers=conta["headers"])

    segundo = enviar(client, conta, "extrato-exemplo.ofx").json()
    assert segundo["rows_detected"] == 5
    assert segundo["rows_duplicated"] == 5
    assert not any(item["selected"] for item in segundo["preview"])
    assert any("ja foi importado" in aviso for aviso in segundo["warnings"])

    client.post(f"/api/v1/imports/{segundo['id']}/confirm", json={}, headers=conta["headers"])
    assert len(transacoes(client, conta)) == 5


def test_mesmo_extrato_em_formato_diferente_tambem_nao_duplica(client, conta):
    """Voce importou o OFX; depois envia o CSV do mesmo periodo por engano."""
    ofx = enviar(client, conta, "extrato-exemplo.ofx").json()
    client.post(f"/api/v1/imports/{ofx['id']}/confirm", json={}, headers=conta["headers"])

    csv_lote = enviar(client, conta, "extrato-exemplo.csv").json()
    # o OFX traz FITID e o CSV nao, entao a digital muda; o que salva aqui e a
    # deteccao de lancamento equivalente ja existente
    assert csv_lote["rows_duplicated"] == 5
    assert all(
        item["duplicate_reason"] == "ja importado em outro formato"
        for item in csv_lote["preview"]
    )

    client.post(f"/api/v1/imports/{csv_lote['id']}/confirm", json={}, headers=conta["headers"])
    assert len(transacoes(client, conta)) == 5


def test_da_para_escolher_quais_linhas_entram(client, conta):
    lote = enviar(client, conta, "extrato-exemplo.csv").json()

    resposta = client.post(
        f"/api/v1/imports/{lote['id']}/confirm",
        json={"selected_indexes": [0, 2]},
        headers=conta["headers"],
    )
    assert resposta.json()["rows_imported"] == 2
    assert len(transacoes(client, conta)) == 2


def _categoria(client, conta, caminho: str) -> str:
    """Acha uma categoria da familia percorrendo a arvore devolvida pela API."""
    def buscar(nos, alvo):
        for no in nos:
            if no["path"] == alvo:
                return no["id"]
            achado = buscar(no["children"], alvo)
            if achado:
                return achado
        return None

    arvore = client.get("/api/v1/categories", headers=conta["headers"]).json()
    encontrado = buscar(arvore, caminho)
    assert encontrado, f"categoria {caminho} nao encontrada"
    return encontrado


def test_categoria_pode_ser_corrigida_na_conferencia(client, conta):
    categoria = _categoria(client, conta, "despesas.essenciais.educacao.escola")

    lote = enviar(client, conta, "extrato-exemplo.csv").json()
    escola = next(i for i in lote["preview"] if "COLEGIO" in i["description"].upper())

    client.post(
        f"/api/v1/imports/{lote['id']}/confirm",
        json={
            "selected_indexes": [escola["index"]],
            "category_overrides": {str(escola["index"]): categoria},
        },
        headers=conta["headers"],
    )
    lancamentos = transacoes(client, conta)
    assert len(lancamentos) == 1
    assert lancamentos[0]["category_id"] == categoria


def test_arquivo_ilegivel_explica_o_motivo(client, conta):
    resposta = client.post(
        "/api/v1/imports",
        data={"account_id": conta["account_id"]},
        files={"file": ("foto.jpg", b"\xff\xd8\xff\xe0nao sou extrato", "image/jpeg")},
        headers=conta["headers"],
    )
    assert resposta.status_code == 422
    assert "OFX" in resposta.json()["detail"]


def test_lote_descartado_nao_grava_nada(client, conta):
    lote = enviar(client, conta, "extrato-exemplo.ofx").json()

    descartado = client.post(
        f"/api/v1/imports/{lote['id']}/discard", headers=conta["headers"]
    )
    assert descartado.json()["status"] == "DESCARTADO"
    assert transacoes(client, conta) == []


def test_confirmar_duas_vezes_e_recusado(client, conta):
    lote = enviar(client, conta, "extrato-exemplo.ofx").json()
    client.post(f"/api/v1/imports/{lote['id']}/confirm", json={}, headers=conta["headers"])

    repetido = client.post(
        f"/api/v1/imports/{lote['id']}/confirm", json={}, headers=conta["headers"]
    )
    assert repetido.status_code == 409
    assert len(transacoes(client, conta)) == 5


def test_extrato_de_outra_familia_e_recusado(client, conta):
    from app.cli import seed_family

    suffix = uuid.uuid4().hex[:8]
    email = f"outro.{suffix}@exemplo.com"
    seed_family(
        name=f"Outra {suffix}",
        titular="Outro",
        titular_email=email,
        titular_password="segredo-de-teste",
        conjuge=None, conjuge_email=None, conjuge_password=None, dependentes=[],
    )
    outro = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "segredo-de-teste"}
    ).json()

    resposta = client.post(
        "/api/v1/imports",
        data={"account_id": conta["account_id"]},   # conta da PRIMEIRA familia
        files={"file": ("e.ofx", (SAMPLES / "extrato-exemplo.ofx").read_bytes(), "text/plain")},
        headers={"Authorization": f"Bearer {outro['access_token']}"},
    )
    assert resposta.status_code == 404


def test_importado_alimenta_o_dashboard_e_o_ir(client, conta):
    lote = enviar(client, conta, "extrato-exemplo.ofx").json()
    client.post(f"/api/v1/imports/{lote['id']}/confirm", json={}, headers=conta["headers"])

    painel = client.get(
        "/api/v1/dashboard", params={"month": "2026-08-01"}, headers=conta["headers"]
    ).json()
    assert float(painel["cashflow"]["inflow"]) == 43000.0
    assert float(painel["cashflow"]["outflow"]) == 11925.90

    # sem categoria os lancamentos ainda nao entram na apuracao de IR
    ir = client.get(f"/api/v1/tax/{date.today().year}", headers=conta["headers"])
    assert ir.status_code == 200
