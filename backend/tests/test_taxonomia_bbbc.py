"""A taxonomia que a familia definiu, e as regras que vem com ela.

Estes testes olham para o catalogo como ele e usado de verdade: um extrato
brasileiro chegando com nomes de fornecedor reais, e as marcacoes de IR que
decidem quanto imposto se paga.
"""

from __future__ import annotations

import os
import uuid
from datetime import date
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


@pytest.fixture(scope="module")
def familia(client):
    from sqlalchemy import text

    from app.cli import seed_family
    from app.db.session import SessionLocal

    suffix = uuid.uuid4().hex[:8]
    email = f"felipe.tax.{suffix}@exemplo.com"
    family_id = seed_family(
        name=f"Familia {suffix}",
        titular="Felipe",
        titular_email=email,
        titular_password="segredo-de-teste",
        conjuge="Clarissa",
        conjuge_email=f"clarissa.tax.{suffix}@exemplo.com",
        conjuge_password="segredo-de-teste",
        dependentes=["Filha 1", "Filha 2"],
    )
    auth = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "segredo-de-teste"}
    ).json()
    headers = {"Authorization": f"Bearer {auth['access_token']}"}
    conta = client.post(
        "/api/v1/accounts", json={"name": "Conta", "type": "CONTA_CORRENTE"},
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
        filhas = [
            str(linha[0])
            for linha in db.execute(
                text(
                    "SELECT id FROM members WHERE family_id = :f AND is_ir_dependent"
                    " ORDER BY full_name"
                ),
                {"f": family_id},
            )
        ]
    return {"headers": headers, "account_id": conta["id"], "cat": cats, "filhas": filhas}


def lancar(client, familia, **kwargs):
    corpo = {"account_id": familia["account_id"], **kwargs}
    return client.post("/api/v1/transactions", json=corpo, headers=familia["headers"])


# --------------------------------------------------------- estrutura -------
def test_a_arvore_tem_as_categorias_que_a_familia_pediu(client, familia):
    resposta = client.get("/api/v1/categories", headers=familia["headers"])
    arvore = resposta.json()

    despesas = next(n for n in arvore if n["name"] == "Despesas")
    nomes = {filho["name"] for filho in despesas["children"]}

    esperadas = {
        "Financiamento", "Condominio e manutencao", "Mensais fixos", "Educacao",
        "Saude", "Mercado", "Faxina", "Criacao", "Combustivel", "Estacionamento",
        "Transportes", "Restaurantes", "Aplicativo de comida", "Market places",
        "Assinaturas", "Anuais", "Unicos",
    }
    assert esperadas <= nomes, f"faltando: {esperadas - nomes}"


def test_investimento_nao_e_despesa(client, familia):
    """Aporte nao e dinheiro que sai da familia - e dinheiro que muda de bolso.
    Como despesa, estragaria o 'sobrou no mes' e a taxa de poupanca."""
    arvore = client.get("/api/v1/categories", headers=familia["headers"]).json()
    investimentos = next(n for n in arvore if n["name"] == "Investimentos")
    assert investimentos["kind"] == "INVESTIMENTO"

    despesas = next(n for n in arvore if n["name"] == "Despesas")
    assert "Investimentos" not in {f["name"] for f in despesas["children"]}


# ------------------------------------------------------------- IR ----------
def test_farmacia_fica_dentro_de_saude_mas_nao_e_dedutivel(client, familia):
    """A lista original juntava farmacia com plano de saude. Remedio nao e
    dedutivel; plano e. Sem a separacao, o IR sairia errado."""
    arvore = client.get("/api/v1/categories", headers=familia["headers"]).json()
    despesas = next(n for n in arvore if n["name"] == "Despesas")
    saude = next(f for f in despesas["children"] if f["name"] == "Saude")

    por_nome = {f["name"]: f for f in saude["children"]}
    assert por_nome["Farmacia (nao dedutivel)"]["ir_deduction_type"] == "NENHUMA"
    assert por_nome["Plano de saude (dedutivel)"]["ir_deduction_type"] == "SAUDE"


def test_material_escolar_nao_e_dedutivel_mas_a_mensalidade_e(client, familia):
    arvore = client.get("/api/v1/categories", headers=familia["headers"]).json()
    despesas = next(n for n in arvore if n["name"] == "Despesas")
    educacao = next(f for f in despesas["children"] if f["name"] == "Educacao")

    por_nome = {f["name"]: f for f in educacao["children"]}
    assert por_nome["Materiais (nao dedutivel)"]["ir_deduction_type"] == "NENHUMA"
    assert por_nome["Escola (dedutivel)"]["ir_deduction_type"] == "EDUCACAO"


def test_o_ir_separa_o_que_e_dedutivel_do_que_nao_e(client, familia):
    """Farmacia e material escolar entram no mes, mas nao na deducao."""
    hoje = date.today().replace(day=10)
    cat = familia["cat"]

    lancar(client, familia, booked_on=hoje.isoformat(), amount="28000.00",
           direction="ENTRADA", description="Pro-labore",
           category_id=cat["receitas.ativa_fixa.pro_labore"])
    lancar(client, familia, booked_on=hoje.isoformat(), amount="2400.00",
           direction="SAIDA", description="Plano de saude",
           category_id=cat["despesas.saude.plano_de_saude"])
    lancar(client, familia, booked_on=hoje.isoformat(), amount="380.00",
           direction="SAIDA", description="Drogaria",
           category_id=cat["despesas.saude.farmacia"])
    lancar(client, familia, booked_on=hoje.isoformat(), amount="900.00",
           direction="SAIDA", description="Material escolar",
           category_id=cat["despesas.educacao.materiais"])
    lancar(client, familia, booked_on=hoje.isoformat(), amount="2000.00",
           direction="SAIDA", description="Escola",
           category_id=cat["despesas.educacao.escola"],
           ir_deduction_member_id=familia["filhas"][0])

    ir = client.get(f"/api/v1/tax/{hoje.year}", headers=familia["headers"]).json()
    deducoes = ir["completo"]["deductions_breakdown"]

    # so o plano entra em saude; a farmacia fica de fora
    assert float(deducoes["saude"]) == 2400.0
    # so a mensalidade entra em educacao; o material fica de fora
    assert float(deducoes["educacao"]) == 2000.0


# ------------------------------------------------- comentario obrigatorio ---
def test_unicos_exige_comentario(client, familia):
    """'Unicos (com comentarios)': daqui a seis meses ninguem lembra o que foi."""
    resposta = lancar(
        client, familia, booked_on=date.today().isoformat(), amount="3400.00",
        direction="SAIDA", description="Compra avulsa",
        category_id=familia["cat"]["despesas.unicos"],
    )
    assert resposta.status_code == 422
    assert "comentario" in resposta.json()["detail"].lower()


def test_unicos_passa_com_comentario(client, familia):
    resposta = lancar(
        client, familia, booked_on=date.today().isoformat(), amount="3400.00",
        direction="SAIDA", description="Compra avulsa",
        category_id=familia["cat"]["despesas.unicos"],
        notes="Conserto do telhado depois do temporal de agosto",
    )
    assert resposta.status_code == 201


def test_o_app_sabe_quando_pedir_o_comentario(client, familia):
    arvore = client.get("/api/v1/categories", headers=familia["headers"]).json()
    despesas = next(n for n in arvore if n["name"] == "Despesas")
    por_nome = {f["name"]: f for f in despesas["children"]}

    assert por_nome["Unicos"]["requires_note"] is True
    assert por_nome["Mercado"]["requires_note"] is False


# ------------------------------------------------- regras de fornecedor -----
@pytest.mark.parametrize(
    ("descricao", "categoria_esperada"),
    [
        ("IFOOD *PEDIDO 4821", "Aplicativo de comida"),
        ("UBER   *TRIP HELP.UBER.COM", "Transportes"),
        ("POSTO IPIRANGA LTDA", "Combustivel"),
        ("ESTAPAR ESTACIONAMENTO", "Estacionamento"),
        ("SUPERMERCADO ANGELONI 023", "Mercado"),
        ("MERCADOLIVRE*COMPRA", "Market places"),
        ("AMAZON BR SERVICOS", "Market places"),
        ("NETFLIX.COM", "Streaming"),
        ("OPENAI *CHATGPT SUBSCR", "IA e softwares"),
        ("DROGARIA SAO PAULO", "Farmacia (nao dedutivel)"),
        ("UNIMED SEGUROS SAUDE", "Plano de saude (dedutivel)"),
        ("COLEGIO SAO JOSE MENSALIDADE", "Escola (dedutivel)"),
        ("ENEL DISTRIBUICAO SP", "Luz"),
        ("COMGAS SP", "Gas"),
        ("CONDOMINIO EDIFICIO", "Condominio e manutencao"),
        ("IPVA 2026 DETRAN", "IPVA"),
    ],
)
def test_extrato_real_chega_ja_categorizado(client, familia, descricao, categoria_esperada):
    """O primeiro extrato importado nao deve chegar com 200 linhas em branco."""
    tx = lancar(
        client, familia, booked_on=date.today().isoformat(), amount="100.00",
        direction="SAIDA", description=descricao,
    ).json()

    assert tx["category_id"] is not None, f"{descricao} ficou sem categoria"

    arvore = client.get("/api/v1/categories", headers=familia["headers"]).json()

    def achar(nos):
        for no in nos:
            if no["id"] == tx["category_id"]:
                return no["name"]
            achado = achar(no["children"])
            if achado:
                return achado
        return None

    assert achar(arvore) == categoria_esperada


def test_uber_eats_nao_vira_transporte(client, familia):
    """A regra mais especifica tem que ser avaliada antes da generica."""
    tx = lancar(
        client, familia, booked_on=date.today().isoformat(), amount="70.00",
        direction="SAIDA", description="UBER EATS PEDIDO",
    ).json()

    arvore = client.get("/api/v1/categories", headers=familia["headers"]).json()
    despesas = next(n for n in arvore if n["name"] == "Despesas")
    comida = next(f for f in despesas["children"] if f["name"] == "Aplicativo de comida")
    assert tx["category_id"] == comida["id"]


def test_a_correcao_do_usuario_vence_a_regra_do_catalogo(client, familia):
    """As regras que vem prontas sao ponto de partida, nao verdade absoluta."""
    cat = familia["cat"]
    tx = lancar(
        client, familia, booked_on=date.today().isoformat(), amount="220.00",
        direction="SAIDA", description="MERCADO MUNICIPAL RESTAURANTE",
    ).json()
    assert tx["category_id"] == cat["despesas.mercado"]  # a regra 'mercado' pegou

    client.patch(
        f"/api/v1/transactions/{tx['id']}",
        json={"category_id": cat["despesas.restaurantes"], "learn_rule": True},
        headers=familia["headers"],
    )

    seguinte = lancar(
        client, familia, booked_on=date.today().isoformat(), amount="180.00",
        direction="SAIDA", description="MERCADO MUNICIPAL RESTAURANTE",
    ).json()
    assert seguinte["category_id"] == cat["despesas.restaurantes"]


def test_gastos_por_categoria_usa_a_arvore_nova(client, familia):
    hoje = date.today().replace(day=10)
    resposta = client.get(
        "/api/v1/transactions/by-category",
        params={"start": hoje.replace(day=1).isoformat(),
                "end": hoje.replace(day=28).isoformat(), "depth": 2},
        headers=familia["headers"],
    )
    assert resposta.status_code == 200
    nomes = {g["name"] for g in resposta.json()["categories"]}
    assert {"Saude", "Educacao", "Mercado"} & nomes
    assert Decimal(resposta.json()["total"]) > 0


# ------------------------------------ patrimonio nao e consumo --------------
def test_amortizacao_sai_da_conta_mas_nao_e_gasto(client, familia):
    """Amortizacao e divida virando patrimonio. Contada como gasto, faria o mes
    parecer pior do que foi - e a taxa de poupanca, menor."""
    hoje = date.today().replace(day=12)
    cat = familia["cat"]

    lancar(client, familia, booked_on=hoje.isoformat(), amount="1800.00",
           direction="SAIDA", description="Amortizacao do financiamento",
           category_id=cat["despesas.financiamento.amortizacao"])
    lancar(client, familia, booked_on=hoje.isoformat(), amount="700.00",
           direction="SAIDA", description="Juros do financiamento",
           category_id=cat["despesas.financiamento.juros"])

    painel = client.get(
        "/api/v1/dashboard", params={"month": hoje.replace(day=1).isoformat()},
        headers=familia["headers"],
    ).json()["cashflow"]

    # os dois saem da conta
    assert float(painel["outflow"]) >= 2500.0
    # mas so os juros sao consumo
    assert float(painel["patrimonio"]) >= 1800.0
    assert float(painel["consumo"]) == float(painel["outflow"]) - float(painel["patrimonio"])


def test_aporte_em_investimento_tambem_nao_e_gasto(client, familia):
    """O mesmo erro estava presente antes: aporte era somado como saida."""
    hoje = date.today().replace(day=12)
    antes = client.get(
        "/api/v1/dashboard", params={"month": hoje.replace(day=1).isoformat()},
        headers=familia["headers"],
    ).json()["cashflow"]

    lancar(client, familia, booked_on=hoje.isoformat(), amount="5000.00",
           direction="SAIDA", description="Aporte mensal",
           category_id=familia["cat"]["investimentos.aporte"])

    depois = client.get(
        "/api/v1/dashboard", params={"month": hoje.replace(day=1).isoformat()},
        headers=familia["headers"],
    ).json()["cashflow"]

    assert float(depois["outflow"]) == float(antes["outflow"]) + 5000.0
    assert float(depois["consumo"]) == float(antes["consumo"])   # consumo nao mudou
    assert float(depois["patrimonio"]) == float(antes["patrimonio"]) + 5000.0


def test_patrimonio_nao_polui_o_gasto_por_categoria(client, familia):
    hoje = date.today().replace(day=12)
    resposta = client.get(
        "/api/v1/transactions/by-category",
        params={"start": hoje.replace(day=1).isoformat(),
                "end": hoje.replace(day=28).isoformat(), "depth": 2},
        headers=familia["headers"],
    ).json()

    nomes = {g["name"] for g in resposta["categories"]}
    assert "Amortizacao" not in nomes
    assert "Aporte" not in nomes
    assert "Financiamento" in nomes   # os juros continuam la


# --------------------------------- comentario herdado pelos filhos ----------
def test_filho_de_unicos_herda_a_exigencia_de_comentario(client, familia):
    """Sem heranca, bastava criar uma subcategoria para escapar da regra."""
    resposta = lancar(
        client, familia, booked_on=date.today().isoformat(), amount="2200.00",
        direction="SAIDA", description="Geladeira nova",
        category_id=familia["cat"]["despesas.unicos.moveis_eletro"],
    )
    assert resposta.status_code == 422
    assert "Unicos" in resposta.json()["detail"]


def test_filho_de_unicos_passa_com_comentario(client, familia):
    resposta = lancar(
        client, familia, booked_on=date.today().isoformat(), amount="2200.00",
        direction="SAIDA", description="Geladeira nova",
        category_id=familia["cat"]["despesas.unicos.moveis_eletro"],
        notes="A antiga parou de gelar depois de 11 anos",
    )
    assert resposta.status_code == 201


def test_categoria_normal_nao_pede_comentario(client, familia):
    resposta = lancar(
        client, familia, booked_on=date.today().isoformat(), amount="180.00",
        direction="SAIDA", description="Compra da semana",
        category_id=familia["cat"]["despesas.mercado"],
    )
    assert resposta.status_code == 201


# --------------------------------------- filhos de anuais -------------------
def test_anuais_agora_distingue_o_que_tem_dentro(client, familia):
    arvore = client.get("/api/v1/categories", headers=familia["headers"]).json()
    despesas = next(n for n in arvore if n["name"] == "Despesas")
    anuais = next(f for f in despesas["children"] if f["name"] == "Anuais")

    nomes = {f["name"] for f in anuais["children"]}
    assert {"IPVA", "IPTU", "Licenciamento", "Seguros"} <= nomes


def test_financiamento_separa_juros_de_amortizacao(client, familia):
    arvore = client.get("/api/v1/categories", headers=familia["headers"]).json()
    despesas = next(n for n in arvore if n["name"] == "Despesas")
    financiamento = next(f for f in despesas["children"] if f["name"] == "Financiamento")

    por_nome = {f["name"]: f for f in financiamento["children"]}
    assert por_nome["Juros"]["counts_as_expense"] is True
    assert por_nome["Amortizacao"]["counts_as_expense"] is False
