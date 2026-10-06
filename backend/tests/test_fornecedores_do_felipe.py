"""Os fornecedores que so ele sabe quem sao.

"Nos gastos, alguns comecam com ACM - e minha academia. (...) quase todo
delivery meu e no cartao e pelo ifood: o cartao identifica o inicio da fatura
com 'ifd*'. (...) 'Sam S' e supermercado; 'Beep' e consulta e exames;
'Casottisouzaltda' e restaurante."

Sao regras de catalogo, nao de banco: ficam em app/services/default_rules.py e
sao refeitas a cada partida do sistema. Qualquer correcao que ele faca na tela
vira regra aprendida, com prioridade melhor, e passa a mandar sobre estas.

Quatro delas casam pelo COMECO da descricao, e isso importa: no extrato dele
existe "Acm Alphaville" (a academia) e existe "Alphaville Sao Paulo", que e
outra coisa. Procurar "acm" no meio do texto encontraria as duas.
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


@pytest.fixture(scope="module")
def casa(client):
    from sqlalchemy import text

    from app.cli import seed_family
    from app.db.session import SessionLocal

    sufixo = uuid.uuid4().hex[:8]
    email = f"felipe.forn.{sufixo}@exemplo.com"
    family_id = seed_family(
        name=f"Familia {sufixo}",
        titular="Felipe",
        titular_email=email,
        titular_password="segredo-de-teste",
        conjuge="Clarissa",
        conjuge_email=f"clarissa.forn.{sufixo}@exemplo.com",
        conjuge_password="segredo-de-teste",
        dependentes=[],
    )
    auth = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "segredo-de-teste"}
    ).json()
    headers = {"Authorization": f"Bearer {auth['access_token']}"}
    conta = client.post(
        "/api/v1/accounts",
        json={"name": "Cartao", "type": "CARTAO_CREDITO"},
        headers=headers,
    ).json()
    with SessionLocal() as db:
        por_id = {
            str(linha[1]): linha[0]
            for linha in db.execute(
                text("SELECT path::text, id FROM categories WHERE family_id = :f"),
                {"f": family_id},
            )
        }
    return {"headers": headers, "conta": conta["id"], "caminho_de": por_id}


def caminho_sugerido(client, casa, descricao: str) -> str | None:
    """Lanca a descricao e devolve o CAMINHO da categoria que o sistema escolheu."""
    criado = client.post(
        "/api/v1/transactions",
        json={
            "account_id": casa["conta"],
            "booked_on": "2026-01-10",
            "amount": "100.00",
            "direction": "SAIDA",
            "description": descricao,
            "status": "EFETIVADA",
        },
        headers=casa["headers"],
    )
    assert criado.status_code == 201, criado.text
    return casa["caminho_de"].get(str(criado.json()["category_id"]))


@pytest.mark.parametrize(
    "descricao,caminho",
    [
        # como o extrato dele escreve, com o ruido e tudo
        ("Acm Alphaville         Barueri       Bra", "despesas.gastos_mensais.academia"),
        ("Ifd*camarada Administr Barueri       Bra", "despesas.delivery"),
        ("Ifd*organizacao Farmac Sao Paulo     Bra", "despesas.delivery"),
        ("Sam S Tambore Lj 4932  Barueri       Bra", "despesas.mercado"),
        ("Beep Saude        Rio De Janeir Bra", "despesas.saude.consultas_exames"),
        ("Casottisouzaltda       Barueri       Bra", "despesas.restaurantes.restaurante"),
    ],
)
def test_o_extrato_dele_chega_categorizado(client, casa, descricao, caminho):
    assert caminho_sugerido(client, casa, descricao) == caminho


def test_academia_nao_pega_o_resto_do_bairro(client, casa):
    """No mesmo extrato existe "Alphaville Sao Paulo Bra", que nao e academia.

    E a razao de a regra casar pelo COMECO: o nome do bairro aparece nas duas
    linhas, e so uma delas e a academia.
    """
    assert caminho_sugerido(client, casa, "Alphaville             Sao Paulo     Bra") != (
        "despesas.gastos_mensais.academia"
    )


def test_a_farmacia_pedida_pelo_ifood_continua_sendo_delivery(client, casa):
    """"Ifd*organizacao Farmac" tem "farmac" no meio, e farmacia e uma regra do
    catalogo. Ganha o prefixo: quem define a natureza do gasto e o aplicativo
    pelo qual ele foi feito."""
    assert caminho_sugerido(
        client, casa, "Ifd*organizacao Farmac Sao Paulo     Bra"
    ) == "despesas.delivery"


def test_a_academia_existe_como_categoria(client, casa):
    arvore = client.get("/api/v1/categories", headers=casa["headers"]).json()
    caminhos: list[str] = []

    def descer(nos):
        for no in nos:
            caminhos.append(no["path"])
            descer(no["children"])

    descer(arvore)
    assert "despesas.gastos_mensais.academia" in caminhos
