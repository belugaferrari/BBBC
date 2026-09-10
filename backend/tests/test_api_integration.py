"""Teste ponta a ponta contra um PostgreSQL de verdade.

E pulado quando nao ha banco disponivel, para o `pytest` continuar rapido no
dia a dia. Para rodar:

    createdb bbbc_test && \
    BBBC_TEST_DATABASE_URL=postgresql+psycopg://user:pass@localhost/bbbc_test \
    pytest tests/test_api_integration.py
"""

from __future__ import annotations

import os
import uuid
from datetime import date

import pytest

# A variavel e propagada para DATABASE_URL no conftest, antes dos imports de app.
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
def family(client):
    """Cria uma familia isolada por execucao e devolve o token do titular."""
    from sqlalchemy import text

    from app.cli import seed_family
    from app.db.session import SessionLocal

    suffix = uuid.uuid4().hex[:8]
    email = f"felipe.{suffix}@exemplo.com"
    family_id = seed_family(
        name=f"Familia Teste {suffix}",
        titular="Felipe",
        titular_email=email,
        titular_password="segredo-de-teste",
        conjuge="Clarissa",
        conjuge_email=f"clarissa.{suffix}@exemplo.com",
        conjuge_password="segredo-de-teste",
        dependentes=["Filha 1", "Filha 2"],
    )

    response = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "segredo-de-teste"}
    )
    assert response.status_code == 200, response.text
    auth = response.json()

    with SessionLocal() as db:
        categories = {
            row[0]: str(row[1])
            for row in db.execute(
                text("SELECT path::text, id FROM categories WHERE family_id = :f"),
                {"f": family_id},
            )
        }
        filhas = [
            str(row[0])
            for row in db.execute(
                text(
                    "SELECT id FROM members WHERE family_id = :f AND is_ir_dependent"
                    " ORDER BY full_name"
                ),
                {"f": family_id},
            )
        ]

    return {
        "family_id": family_id,
        "headers": {"Authorization": f"Bearer {auth['access_token']}"},
        "categories": categories,
        "filhas": filhas,
    }


def post_tx(client, family, **kwargs) -> dict:
    payload = {
        "account_id": family["account_id"],
        "booked_on": kwargs.pop("booked_on", date.today().replace(day=5).isoformat()),
        **kwargs,
    }
    response = client.post("/api/v1/transactions", json=payload, headers=family["headers"])
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture(scope="module")
def account(client, family):
    response = client.post(
        "/api/v1/accounts",
        json={"name": "Conta corrente", "type": "CONTA_CORRENTE", "is_shared": True},
        headers=family["headers"],
    )
    assert response.status_code == 201, response.text
    family["account_id"] = response.json()["id"]
    return response.json()


def test_arvore_de_categorias_vem_montada(client, family):
    response = client.get("/api/v1/categories", headers=family["headers"])
    assert response.status_code == 200
    roots = response.json()
    nomes = {node["name"] for node in roots}
    assert {"Receitas", "Despesas"} <= nomes

    despesas = next(node for node in roots if node["name"] == "Despesas")
    saude = next(n for n in despesas["children"] if n["name"] == "Saude")
    assert saude["ir_deduction_type"] == "SAUDE"
    assert saude["depth"] == 1
    # a farmacia fica dentro de Saude, mas remedio nao e dedutivel
    farmacia = next(n for n in saude["children"] if n["name"].startswith("Farmacia"))
    assert farmacia["ir_deduction_type"] == "NENHUMA"


def test_dashboard_reflete_os_lancamentos(client, family, account):
    cats = family["categories"]
    post_tx(
        client, family, amount="28000.00", direction="ENTRADA",
        description="Pro-labore Checkmotor", category_id=cats["receitas.ativa_fixa.pro_labore"],
    )
    post_tx(
        client, family, amount="15000.00", direction="ENTRADA",
        description="Distribuicao de lucros Checkmotor",
        category_id=cats["receitas.ativa_variavel.lucros"],
    )
    post_tx(
        client, family, amount="4200.00", direction="SAIDA", description="Supermercado Angeloni",
        category_id=cats["despesas.mercado"],
    )
    post_tx(
        client, family, amount="6800.00", direction="SAIDA", description="Mensalidade escolar",
        category_id=cats["despesas.educacao.escola"],
        ir_deduction_member_id=family["filhas"][0],
    )

    response = client.get("/api/v1/dashboard", headers=family["headers"])
    assert response.status_code == 200, response.text
    data = response.json()

    assert float(data["cashflow"]["inflow"]) == 43000.0
    assert float(data["cashflow"]["outflow"]) == 11000.0
    assert float(data["cashflow"]["net"]) == 32000.0

    # o Sankey tem que fechar: o que sai do no central e a receita total
    sankey = data["sankey"]
    saindo = sum(
        float(link["value"]) for link in sankey["links"] if link["source"] == "Renda do mes"
    )
    assert saindo == float(sankey["total_income"]) == 43000.0


def test_ir_separa_tributavel_de_isento_e_deduz_educacao(client, family, account):
    year = date.today().year
    response = client.get(f"/api/v1/tax/{year}", headers=family["headers"])
    if response.status_code == 404:
        pytest.skip(f"parametros fiscais de {year} nao cadastrados")
    assert response.status_code == 200, response.text

    data = response.json()
    # pro-labore e tributavel; distribuicao de lucros e isenta
    assert float(data["taxable_income"]) == 28000.0
    assert float(data["exempt_income"]) == 15000.0

    deducoes = data["completo"]["deductions_breakdown"]
    # 6.800 de escola, limitado ao teto anual por pessoa
    assert float(deducoes["educacao"]) == pytest.approx(3561.50)
    assert float(data["completo"]["capped_amounts"]["educacao"]) == pytest.approx(3238.50)
    assert float(deducoes["dependentes"]) == pytest.approx(4550.16)

    # 28.000 - (3.561,50 de escola + 4.550,16 das duas filhas)
    assert float(data["completo"]["calculation_base"]) == pytest.approx(19888.34)
    # a base fica abaixo da primeira faixa: nada a pagar neste cenario
    assert float(data["completo"]["tax_due"]) == 0.0
    # o completo deduz mais que os 20% do simplificado (5.600), entao vence
    assert float(data["simplificado"]["total_deductions"]) == pytest.approx(5600.00)
    assert data["recommended_model"] == "COMPLETO"
    if data["table_status"] == "PROVISORIO":
        assert "provisorio" in data["aviso"].lower()


def test_correcao_manual_ensina_o_motor_de_categorizacao(client, family, account):
    cats = family["categories"]
    hobby = cats["despesas.marketplaces"]

    criada = post_tx(
        client, family, amount="890.00", direction="SAIDA",
        description="COMPRA CARTAO BAMBU LAB FILAMENTO",
    )
    assert criada["category_id"] is None  # nenhuma regra existia ainda

    corrigida = client.patch(
        f"/api/v1/transactions/{criada['id']}",
        json={"category_id": hobby, "learn_rule": True},
        headers=family["headers"],
    )
    assert corrigida.status_code == 200, corrigida.text
    assert corrigida.json()["category_id"] == hobby

    # a proxima compra do mesmo fornecedor entra ja categorizada
    seguinte = post_tx(
        client, family, amount="240.00", direction="SAIDA",
        description="COMPRA CARTAO BAMBU LAB FILAMENTO PETG",
    )
    assert seguinte["category_id"] == hobby
    assert float(seguinte["auto_confidence"]) >= 0.7


def test_filtro_de_categoria_inclui_a_subarvore(client, family, account):
    cats = family["categories"]
    hoje = date.today()
    response = client.get(
        "/api/v1/transactions",
        params={
            "start": hoje.replace(day=1).isoformat(),
            "end": hoje.replace(day=28).isoformat(),
            "category_id": cats["despesas.educacao"],
        },
        headers=family["headers"],
    )
    assert response.status_code == 200, response.text
    descricoes = {item["description"] for item in response.json()}
    # o filtro desce a subarvore: 'Escola' esta abaixo de 'Educacao'
    assert "Mensalidade escolar" in descricoes
    assert "Supermercado Angeloni" not in descricoes   # esta em Mercado
    assert all("BAMBU" not in d for d in descricoes)
