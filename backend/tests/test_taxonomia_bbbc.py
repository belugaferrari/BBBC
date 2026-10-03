"""A taxonomia que a familia definiu, e as regras que vem com ela.

Estes testes olham para o catalogo como ele e usado de verdade: um extrato
brasileiro chegando com nomes de fornecedor reais, e as marcacoes de IR que
decidem quanto imposto se paga.

A arvore conferida aqui e a do Felipe, a que ele usa no Excel ha anos - as
quinze categorias da lista dele, com os nomes dele. A 0009 trocou a taxonomia
que eu havia proposto por essa, e estes testes trocaram junto: um teste que
afirma a arvore errada e pior que teste nenhum, porque da a impressao de que
alguem conferiu.
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

    # As quinze da lista dele, com os nomes dele. A ordem tambem e a dele: a
    # arvore volta na sequencia em que ele escreveu as categorias.
    esperadas = [
        "Gastos mensais", "Condominio", "Financiamentos", "Educacao", "Saude",
        "Transporte", "Mercado", "Restaurantes", "Market places",
        "Delivery de comida", "Limpeza", "Gastos anuais", "Gastos unicos",
        "Criacao", "Cla PJ",
    ]
    assert set(esperadas) <= nomes, f"faltando: {set(esperadas) - nomes}"
    assert [f["name"] for f in despesas["children"]] == esperadas


def test_transporte_guarda_as_subcategorias_que_ele_citou(client, familia):
    """"as subcategorias de transporte: Transporte por aplicativo; Gasolina;
    Estacionamento" - palavras dele. Antes eram tres categorias soltas de
    primeiro nivel, e a meta nao tinha onde morar: ele poe o teto em Transporte
    e quer ver o detalhe por dentro."""
    arvore = client.get("/api/v1/categories", headers=familia["headers"]).json()
    despesas = next(n for n in arvore if n["name"] == "Despesas")
    transporte = next(f for f in despesas["children"] if f["name"] == "Transporte")

    nomes = {f["name"] for f in transporte["children"]}
    assert {"Transporte por aplicativo", "Gasolina", "Estacionamento"} <= nomes
    # a tag do Sem Parar, que ele citou e nao existia
    assert "Pedagio e tag" in nomes

    # as tres sairam do primeiro nivel: no primeiro nivel elas duplicariam o
    # gasto de Transporte na soma da tela de categorias
    primeiro_nivel = {f["name"] for f in despesas["children"]}
    assert not {"Combustivel", "Estacionamento", "Transportes"} & primeiro_nivel


def test_pagamento_de_fatura_nao_conta_como_gasto(client, familia):
    """A compra no cartao JA e a despesa, lancada no dia dela. Se o pagamento da
    fatura tambem contasse, cada compra entraria duas vezes e o mes dobraria."""
    arvore = client.get("/api/v1/categories", headers=familia["headers"]).json()
    transferencias = next(n for n in arvore if n["name"] == "Transferencias")

    assert transferencias["counts_as_expense"] is False
    for filha in transferencias["children"]:
        assert filha["counts_as_expense"] is False, filha["name"]


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
    assert por_nome["Farmacia"]["ir_deduction_type"] == "NENHUMA"
    assert por_nome["Plano de saude"]["ir_deduction_type"] == "SAUDE"


def test_material_escolar_nao_e_dedutivel_mas_a_mensalidade_e(client, familia):
    arvore = client.get("/api/v1/categories", headers=familia["headers"]).json()
    despesas = next(n for n in arvore if n["name"] == "Despesas")
    educacao = next(f for f in despesas["children"] if f["name"] == "Educacao")

    por_nome = {f["name"]: f for f in educacao["children"]}
    assert por_nome["Materiais"]["ir_deduction_type"] == "NENHUMA"
    assert por_nome["Escola"]["ir_deduction_type"] == "EDUCACAO"


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
        category_id=familia["cat"]["despesas.gastos_unicos"],
    )
    assert resposta.status_code == 422
    assert "comentario" in resposta.json()["detail"].lower()


def test_unicos_passa_com_comentario(client, familia):
    resposta = lancar(
        client, familia, booked_on=date.today().isoformat(), amount="3400.00",
        direction="SAIDA", description="Compra avulsa",
        category_id=familia["cat"]["despesas.gastos_unicos"],
        notes="Conserto do telhado depois do temporal de agosto",
    )
    assert resposta.status_code == 201


def test_o_app_sabe_quando_pedir_o_comentario(client, familia):
    arvore = client.get("/api/v1/categories", headers=familia["headers"]).json()
    despesas = next(n for n in arvore if n["name"] == "Despesas")
    por_nome = {f["name"]: f for f in despesas["children"]}

    assert por_nome["Gastos unicos"]["requires_note"] is True
    assert por_nome["Mercado"]["requires_note"] is False


# ------------------------------------------------- regras de fornecedor -----
@pytest.mark.parametrize(
    ("descricao", "categoria_esperada"),
    [
        ("IFOOD *PEDIDO 4821", "Delivery de comida"),
        ("UBER   *TRIP HELP.UBER.COM", "Transporte por aplicativo"),
        ("POSTO IPIRANGA LTDA", "Gasolina"),
        ("ESTAPAR ESTACIONAMENTO", "Estacionamento"),
        ("SEM PARAR MENSALIDADE", "Pedagio e tag"),
        ("SUPERMERCADO ANGELONI 023", "Mercado"),
        ("PADARIA SAO JOSE", "Padaria e lanchonete"),
        ("MERCADOLIVRE*COMPRA", "Market places"),
        ("AMAZON BR SERVICOS", "Market places"),
        ("NETFLIX.COM", "Streaming"),
        ("OPENAI *CHATGPT SUBSCR", "IA e softwares"),
        ("DROGARIA SAO PAULO", "Farmacia"),
        ("UNIMED SEGUROS SAUDE", "Plano de saude"),
        ("COLEGIO SAO JOSE MENSALIDADE", "Escola"),
        ("ENEL DISTRIBUICAO SP", "Luz"),
        ("COMGAS SP", "Gas"),
        ("CONDOMINIO EDIFICIO", "Condominio"),
        ("IPVA 2026 DETRAN", "IPVA"),
        ("RI HAPPY BRINQUEDOS", "Brinquedos"),
        ("DARF SIMPLES NACIONAL", "DARF e impostos"),
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
    """A regra mais especifica tem que vencer a generica."""
    tx = lancar(
        client, familia, booked_on=date.today().isoformat(), amount="70.00",
        direction="SAIDA", description="UBER EATS PEDIDO",
    ).json()

    assert tx["category_id"] == familia["cat"]["despesas.delivery"]


@pytest.mark.parametrize(
    "descricao",
    [
        "IFOOD *RESTAURANTE SAO JOSE",
        "IFOOD *PADARIA DO ZE",
        "UBER EATS *BURGER KING",
        "99FOOD PEDIDO 123",
    ],
)
def test_o_aplicativo_de_entrega_vence_o_nome_do_estabelecimento(
    client, familia, descricao
):
    """O nome do restaurante vem de brinde na descricao do iFood.

    O desempate normal e por tamanho do padrao, e isso errava aqui: 'restaurante'
    tem 11 letras e 'ifood' tem 5, entao o jantar entregue em casa entrava como
    refeicao fora. Quem paga a conta e o aplicativo, e e ele que define a
    natureza do gasto - uma padaria pedida pelo iFood continua sendo delivery.
    """
    tx = lancar(
        client, familia, booked_on=date.today().isoformat(), amount="70.00",
        direction="SAIDA", description=descricao,
    ).json()

    assert tx["category_id"] == familia["cat"]["despesas.delivery"], descricao


def test_pagamento_de_fatura_e_reconhecido_no_extrato(client, familia):
    """A linha que, contada como gasto, dobraria todo o cartao do mes.

    `normalize` apaga 'pagamento de fatura' de proposito - e ruido quando se
    procura o fornecedor de uma compra. So que e justamente essa frase que diz
    que a linha NAO e uma compra. Por isso a regra e testada tambem contra a
    descricao com o ruido preservado.
    """
    tx = lancar(
        client, familia, booked_on=date.today().isoformat(), amount="4300.00",
        direction="SAIDA", description="PAGAMENTO FATURA CARTAO MERCADO PAGO",
    ).json()

    assert tx["category_id"] == familia["cat"]["transferencias.pagamento_cartao"]


def test_a_correcao_do_usuario_vence_a_regra_do_catalogo(client, familia):
    """As regras que vem prontas sao ponto de partida, nao verdade absoluta.

    O fornecedor usado aqui so aparece neste teste de proposito: a regra
    aprendida fica gravada na familia, que e compartilhada pelo modulo, e
    ensinar algo sobre um fornecedor que outro teste tambem usa faria um
    depender da ordem do outro.
    """
    cat = familia["cat"]
    tx = lancar(
        client, familia, booked_on=date.today().isoformat(), amount="220.00",
        direction="SAIDA", description="HORTIFRUTI DA ESQUINA",
    ).json()
    assert tx["category_id"] == cat["despesas.mercado"]  # a regra 'hortifruti' pegou

    client.patch(
        f"/api/v1/transactions/{tx['id']}",
        json={"category_id": cat["despesas.restaurantes"], "learn_rule": True},
        headers=familia["headers"],
    )

    seguinte = lancar(
        client, familia, booked_on=date.today().isoformat(), amount="180.00",
        direction="SAIDA", description="HORTIFRUTI DA ESQUINA",
    ).json()
    assert seguinte["category_id"] == cat["despesas.restaurantes"]


def test_a_correcao_do_usuario_vence_ate_a_regra_de_plataforma(client, familia):
    """A prioridade da plataforma esta acima do catalogo e abaixo do usuario.

    Se fosse acima dele, o Felipe perderia a palavra final sobre o proprio
    extrato - e a regra de plataforma e uma heuristica minha, nao um fato."""
    cat = familia["cat"]
    tx = lancar(
        client, familia, booked_on=date.today().isoformat(), amount="90.00",
        direction="SAIDA", description="AIQFOME PEDIDO NOTURNO",
    ).json()
    assert tx["category_id"] == cat["despesas.delivery"]

    client.patch(
        f"/api/v1/transactions/{tx['id']}",
        json={"category_id": cat["despesas.restaurantes"], "learn_rule": True},
        headers=familia["headers"],
    )

    seguinte = lancar(
        client, familia, booked_on=date.today().isoformat(), amount="90.00",
        direction="SAIDA", description="AIQFOME PEDIDO NOTURNO",
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
           category_id=cat["despesas.financiamentos.amortizacao"])
    lancar(client, familia, booked_on=hoje.isoformat(), amount="700.00",
           direction="SAIDA", description="Juros do financiamento",
           category_id=cat["despesas.financiamentos.juros"])

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
    assert "Financiamentos" in nomes   # os juros continuam la


# --------------------------------- comentario herdado pelos filhos ----------
def test_filho_de_unicos_herda_a_exigencia_de_comentario(client, familia):
    """Sem heranca, bastava criar uma subcategoria para escapar da regra."""
    resposta = lancar(
        client, familia, booked_on=date.today().isoformat(), amount="2200.00",
        direction="SAIDA", description="Geladeira nova",
        category_id=familia["cat"]["despesas.gastos_unicos.moveis_eletro"],
    )
    assert resposta.status_code == 422
    assert "Gastos unicos" in resposta.json()["detail"]


def test_filho_de_unicos_passa_com_comentario(client, familia):
    resposta = lancar(
        client, familia, booked_on=date.today().isoformat(), amount="2200.00",
        direction="SAIDA", description="Geladeira nova",
        category_id=familia["cat"]["despesas.gastos_unicos.moveis_eletro"],
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
    anuais = next(f for f in despesas["children"] if f["name"] == "Gastos anuais")

    nomes = {f["name"] for f in anuais["children"]}
    assert {"IPVA", "IPTU", "Licenciamento", "Seguro do carro"} <= nomes


def test_financiamento_separa_juros_de_amortizacao(client, familia):
    arvore = client.get("/api/v1/categories", headers=familia["headers"]).json()
    despesas = next(n for n in arvore if n["name"] == "Despesas")
    financiamento = next(
        f for f in despesas["children"] if f["name"] == "Financiamentos"
    )

    por_nome = {f["name"]: f for f in financiamento["children"]}
    assert por_nome["Juros"]["counts_as_expense"] is True
    assert por_nome["Amortizacao"]["counts_as_expense"] is False
