"""Categorias que o Felipe mexe, metas por categoria e o controle do cartao.

O que estes testes guardam, em uma frase cada:

  * dá para criar, renomear e apagar categoria pelo aplicativo - e apagar uma que
    tem historico nao apaga o historico;
  * a meta e uma por categoria, e salvar de novo substitui em vez de empilhar;
  * a leitura de uma categoria compara o mes com a meta, com o mesmo mes do ano
    passado e com os doze meses;
  * a mesma leitura vale para a subcategoria, que e o que permite descer no
    detalhe quando o balde grande estoura;
  * a fatura do cartao nao e contada como gasto, e a linha que parece fatura e
    esta contando aparece como suspeita.
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


@pytest.fixture(scope="module")
def casa(client):
    """Uma familia com uma conta corrente, um cartao e a arvore do Felipe."""
    from sqlalchemy import text

    from app.cli import seed_family
    from app.db.session import SessionLocal

    sufixo = uuid.uuid4().hex[:8]
    email = f"felipe.cat.{sufixo}@exemplo.com"
    family_id = seed_family(
        name=f"Familia {sufixo}",
        titular="Felipe",
        titular_email=email,
        titular_password="segredo-de-teste",
        conjuge="Clarissa",
        conjuge_email=f"clarissa.cat.{sufixo}@exemplo.com",
        conjuge_password="segredo-de-teste",
        dependentes=["Filha 1"],
    )
    auth = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "segredo-de-teste"}
    ).json()
    headers = {"Authorization": f"Bearer {auth['access_token']}"}

    conta = client.post(
        "/api/v1/accounts",
        json={"name": "Itau", "type": "CONTA_CORRENTE"},
        headers=headers,
    ).json()
    cartao = client.post(
        "/api/v1/accounts",
        json={"name": "Nubank", "type": "CARTAO_CREDITO"},
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
    return {
        "headers": headers,
        "conta": conta["id"],
        "cartao": cartao["id"],
        "cat": cats,
    }


def lancar(client, casa, conta: str, **kwargs):
    corpo = {"account_id": conta, **kwargs}
    return client.post("/api/v1/transactions", json=corpo, headers=casa["headers"])


# ------------------------------------------------------ categorias ----------
def test_da_para_criar_categoria_e_subcategoria(client, casa):
    """"deixe um caminho dentro do sistema para eu adicionar, editar ou excluir
    cada categoria" - e o mesmo caminho serve para a subcategoria."""
    nova = client.post(
        "/api/v1/categories",
        json={"name": "Pets", "kind": "DESPESA", "expense_nature": "ESTILO_VIDA"},
        headers=casa["headers"],
    )
    assert nova.status_code == 201
    pai = nova.json()

    filha = client.post(
        "/api/v1/categories",
        json={"name": "Veterinario", "kind": "DESPESA", "parent_id": pai["id"]},
        headers=casa["headers"],
    )
    assert filha.status_code == 201
    assert filha.json()["path"] == f"{pai['path']}.veterinario"


def test_renomear_nao_mexe_no_caminho(client, casa):
    """O nome e do usuario; o caminho e a coluna que amarra a arvore.

    Trocar o caminho exigiria reescrever o dos descendentes na mesma transacao,
    e o caminho nunca aparece na tela - renomear resolve o que ele quer.
    """
    criada = client.post(
        "/api/v1/categories",
        json={"name": "Hobby", "kind": "DESPESA"},
        headers=casa["headers"],
    ).json()

    mudada = client.patch(
        f"/api/v1/categories/{criada['id']}",
        json={"name": "Hobbies e lazer"},
        headers=casa["headers"],
    )
    assert mudada.status_code == 200
    assert mudada.json()["name"] == "Hobbies e lazer"
    assert mudada.json()["path"] == criada["path"]


def test_apagar_categoria_vazia_apaga_de_verdade(client, casa):
    criada = client.post(
        "/api/v1/categories",
        json={"name": "Errei ao criar", "kind": "DESPESA"},
        headers=casa["headers"],
    ).json()

    apagada = client.delete(
        f"/api/v1/categories/{criada['id']}", headers=casa["headers"]
    )
    assert apagada.status_code == 200
    assert apagada.json()["arquivada"] is False

    arvore = client.get("/api/v1/categories", headers=casa["headers"]).json()

    def nomes(nos):
        for no in nos:
            yield no["name"]
            yield from nomes(no["children"])

    assert "Errei ao criar" not in set(nomes(arvore))


def test_apagar_categoria_com_historico_arquiva_em_vez_de_apagar(client, casa):
    """Apagar de verdade transformaria gasto classificado em gasto solto - e o
    estrago apareceria no fechamento do mes, nao agora."""
    criada = client.post(
        "/api/v1/categories",
        json={"name": "Com historico", "kind": "DESPESA"},
        headers=casa["headers"],
    ).json()
    lancar(
        client, casa, casa["conta"], booked_on=date.today().isoformat(),
        amount="120.00", direction="SAIDA", description="Algo",
        category_id=criada["id"],
    )

    resposta = client.delete(
        f"/api/v1/categories/{criada['id']}", headers=casa["headers"]
    )
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["arquivada"] is True
    assert corpo["lancamentos"] == 1
    assert "continuam contando" in corpo["aviso"]

    # saiu da tela
    arvore = client.get("/api/v1/categories", headers=casa["headers"]).json()

    def nomes(nos):
        for no in nos:
            yield no["name"]
            yield from nomes(no["children"])

    assert "Com historico" not in set(nomes(arvore))


def test_apagar_leva_a_subarvore(client, casa):
    """Apagar 'Transporte' e deixar 'Gasolina' orfa nao e um estado que exista."""
    pai = client.post(
        "/api/v1/categories",
        json={"name": "Balde", "kind": "DESPESA"},
        headers=casa["headers"],
    ).json()
    client.post(
        "/api/v1/categories",
        json={"name": "Dentro", "kind": "DESPESA", "parent_id": pai["id"]},
        headers=casa["headers"],
    )

    resposta = client.delete(
        f"/api/v1/categories/{pai['id']}", headers=casa["headers"]
    ).json()
    assert resposta["subcategorias"] == 1

    arvore = client.get("/api/v1/categories", headers=casa["headers"]).json()

    def nomes(nos):
        for no in nos:
            yield no["name"]
            yield from nomes(no["children"])

    assert {"Balde", "Dentro"} & set(nomes(arvore)) == set()


# ----------------------------------------------------------- metas ----------
def test_meta_salva_de_novo_substitui_em_vez_de_empilhar(client, casa):
    """Duas metas vivas para Mercado fariam o painel escolher uma sem dizer qual
    - o tipo de numero que faz perder a confianca na tela inteira."""
    mercado = casa["cat"]["despesas.mercado"]

    primeira = client.post(
        "/api/v1/budget-caps",
        json={"category_id": mercado, "amount": 2500},
        headers=casa["headers"],
    ).json()
    assert primeira["substituiu"] is False

    segunda = client.post(
        "/api/v1/budget-caps",
        json={"category_id": mercado, "amount": 2800},
        headers=casa["headers"],
    ).json()
    assert segunda["substituiu"] is True
    assert segunda["id"] == primeira["id"]

    metas = client.get("/api/v1/budget-caps", headers=casa["headers"]).json()
    do_mercado = [m for m in metas if m["category_id"] == mercado]
    assert len(do_mercado) == 1
    assert float(do_mercado[0]["cap"]) == 2800.0


def test_meta_da_para_editar_e_apagar(client, casa):
    restaurantes = casa["cat"]["despesas.restaurantes"]
    meta = client.post(
        "/api/v1/budget-caps",
        json={"category_id": restaurantes, "amount": 900},
        headers=casa["headers"],
    ).json()

    editada = client.patch(
        f"/api/v1/budget-caps/{meta['id']}",
        json={"amount": 1100},
        headers=casa["headers"],
    )
    assert editada.status_code == 200
    assert float(editada.json()["amount"]) == 1100.0

    apagada = client.delete(
        f"/api/v1/budget-caps/{meta['id']}", headers=casa["headers"]
    )
    assert apagada.status_code == 200

    metas = client.get("/api/v1/budget-caps", headers=casa["headers"]).json()
    assert all(m["category_id"] != restaurantes for m in metas)


def test_meta_de_outra_familia_nao_e_minha(client, casa):
    resposta = client.delete(
        f"/api/v1/budget-caps/{uuid.uuid4()}", headers=casa["headers"]
    )
    assert resposta.status_code == 404


# -------------------------------------------------------- analise -----------
@pytest.fixture(scope="module")
def com_historico(client, casa):
    """Gasolina em catorze meses, com outubro do ano passado bem maior.

    Na CONTA CORRENTE, e nao no cartao, de proposito: no cartao o mes do gasto
    passou a ser o da fatura que o cobra (a compra de 15 de setembro sai da
    conta em outubro), e isso e assunto dos testes do cartao, la embaixo. Aqui o
    que esta sendo medido e a leitura da categoria - meta, mesmo mes do ano
    passado, doze meses -, e ela nao deve depender de qual conta pagou.
    """
    valores = {
        "2025-10-15": 900, "2025-11-15": 520, "2025-12-15": 610,
        "2026-01-15": 480, "2026-02-15": 500, "2026-03-15": 530,
        "2026-04-15": 470, "2026-05-15": 560, "2026-06-15": 510,
        "2026-07-15": 640, "2026-08-15": 495, "2026-09-15": 505,
        "2026-10-03": 350,
    }
    for dia, valor in valores.items():
        lancar(
            client, casa, casa["conta"], booked_on=dia, amount=str(valor),
            direction="SAIDA", description="AUTO POSTO IPIRANGA",
            category_id=casa["cat"]["despesas.transporte.gasolina"],
        )
    client.post(
        "/api/v1/budget-caps",
        json={"category_id": casa["cat"]["despesas.transporte"], "amount": 1800},
        headers=casa["headers"],
    )
    return casa


def test_a_categoria_se_compara_com_a_meta_o_ano_passado_e_os_doze_meses(
    client, com_historico
):
    casa = com_historico
    transporte = casa["cat"]["despesas.transporte"]
    dados = client.get(
        f"/api/v1/categories/{transporte}/analise",
        params={"month": "2026-10-01"},
        headers=casa["headers"],
    ).json()

    assert float(dados["spent"]) == 350.0
    assert float(dados["cap"]["amount"]) == 1800.0
    assert float(dados["remaining"]) == 1450.0

    assert float(dados["previous_month"]) == 505.0
    assert float(dados["same_month_last_year"]) == 900.0
    # 350 contra 900: caiu 61,1%
    assert round(float(dados["vs_last_year_pct"]), 3) == -0.611

    # os doze meses ANTERIORES: de out/2025 a set/2026
    assert float(dados["last_12_months"]) == 6720.0
    assert float(dados["monthly_average"]) == 560.0

    # treze pontos: o mes e os doze que o antecedem
    assert len(dados["series"]) == 13
    assert dados["series"][0]["month"].startswith("2025-10")
    assert dados["series"][-1]["month"].startswith("2026-10")


def test_a_media_nao_inclui_o_mes_que_ela_julga(client, com_historico):
    """Incluindo, a media perseguiria o numero que deveria medir: um mes muito
    alto puxaria a propria referencia para cima e pareceria menos fora da curva."""
    casa = com_historico
    transporte = casa["cat"]["despesas.transporte"]
    dados = client.get(
        f"/api/v1/categories/{transporte}/analise",
        params={"month": "2026-10-01"},
        headers=casa["headers"],
    ).json()

    doze = [float(p["total"]) for p in dados["series"][:-1]]
    assert len(doze) == 12
    assert float(dados["monthly_average"]) == round(sum(doze) / 12, 2)


def test_a_subcategoria_tem_a_mesma_leitura_da_categoria(client, com_historico):
    """"deixe as subcategorias com visibilidade de gastos, assim como as
    proprias categorias" - a mesma rota serve as duas."""
    casa = com_historico
    gasolina = casa["cat"]["despesas.transporte.gasolina"]
    dados = client.get(
        f"/api/v1/categories/{gasolina}/analise",
        params={"month": "2026-10-01"},
        headers=casa["headers"],
    ).json()

    assert dados["category"]["name"] == "Gasolina"
    assert float(dados["spent"]) == 350.0
    assert float(dados["same_month_last_year"]) == 900.0
    assert float(dados["monthly_average"]) == 560.0


def test_a_analise_mostra_de_qual_filha_veio_o_gasto(client, com_historico):
    """'Transporte estourou' nao ajuda; 'Transporte estourou por causa de
    Gasolina' ajuda."""
    casa = com_historico
    transporte = casa["cat"]["despesas.transporte"]
    dados = client.get(
        f"/api/v1/categories/{transporte}/analise",
        params={"month": "2026-10-01"},
        headers=casa["headers"],
    ).json()

    por_nome = {f["name"]: f for f in dados["children"]}
    assert float(por_nome["Gasolina"]["spent"]) == 350.0
    assert float(por_nome["Estacionamento"]["spent"]) == 0.0


def test_o_resumo_nao_soma_a_categoria_com_as_filhas_dela(client, com_historico):
    """O gasto de cada linha ja inclui a subarvore: somar as linhas entre si
    contaria Gasolina duas vezes, dentro de Transporte e sozinha."""
    casa = com_historico
    resumo = client.get(
        "/api/v1/categories/resumo",
        params={"month": "2026-10-01"},
        headers=casa["headers"],
    ).json()

    por_caminho = {c["path"]: c for c in resumo["categories"]}
    assert float(por_caminho["despesas.transporte"]["spent"]) == 350.0
    assert float(por_caminho["despesas.transporte.gasolina"]["spent"]) == 350.0

    # o total conta Transporte uma vez, nao duas
    do_nivel_1 = sum(
        float(c["spent"]) for c in resumo["categories"] if c["depth"] == 1
    )
    assert float(resumo["total_spent"]) == round(do_nivel_1, 2)


# ------------------------------------------------- cartao de credito --------
@pytest.fixture(scope="module")
def com_cartao(client, com_historico):
    """Uma compra no cartao em 20 de setembro.

    Sem dia de fechamento cadastrado, a fatura que a cobra vence em 10 de
    outubro - entao esta compra e gasto de OUTUBRO.
    """
    casa = com_historico
    lancar(
        client, casa, casa["cartao"], booked_on="2026-09-20", amount="350.00",
        direction="SAIDA", description="SUPERMERCADO NO CARTAO",
        category_id=casa["cat"]["despesas.mercado"],
    )
    return casa


def test_o_gasto_do_cartao_conta_no_mes_da_fatura_que_o_cobra(client, com_cartao):
    """"preciso saber quanto foi gasto no cartao de credito, para controle
    pessoal e para controle de pontos".

    E o mes e o da FATURA: "o valor so e contabilizado como gasto no mes em que
    ele efetivamente saiu da conta". A compra de 20 de setembro e cobrada na
    fatura que vence em outubro, entao ela pesa em outubro - que e tambem o mes
    em que o dinheiro sai da conta corrente para pagar essa fatura.
    """
    casa = com_cartao
    resumo = client.get(
        "/api/v1/cards/summary",
        params={"month": "2026-10-01"},
        headers=casa["headers"],
    ).json()

    assert len(resumo["cards"]) == 1
    nubank = resumo["cards"][0]
    assert nubank["name"] == "Nubank"
    assert float(nubank["spent"]) == 350.0
    # a base de pontos e o que foi gasto, nao o que foi faturado
    assert float(nubank["points_base"]) == 350.0

    # e em setembro, o mes da compra, o cartao nao tem gasto nenhum: nada saiu
    # da conta por causa dela naquele mes
    setembro = client.get(
        "/api/v1/cards/summary",
        params={"month": "2026-09-01"},
        headers=casa["headers"],
    ).json()
    assert float(setembro["cards"][0]["spent"]) == 0.0


def test_pagar_a_fatura_nao_soma_no_gasto_do_cartao(client, com_cartao):
    """A compra ja foi lancada no dia dela. Contando a fatura tambem, cada
    compra entraria duas vezes e o mes dobraria."""
    casa = com_cartao
    antes = client.get(
        "/api/v1/cards/summary",
        params={"month": "2026-10-01"},
        headers=casa["headers"],
    ).json()

    paga = lancar(
        client, casa, casa["conta"], booked_on="2026-10-08", amount="350.00",
        direction="SAIDA", description="PAGAMENTO FATURA CARTAO NUBANK",
    ).json()
    # a regra do catalogo reconheceu a linha
    assert paga["category_id"] == casa["cat"]["transferencias.pagamento_cartao"]

    depois = client.get(
        "/api/v1/cards/summary",
        params={"month": "2026-10-01"},
        headers=casa["headers"],
    ).json()

    assert float(depois["total_spent"]) == float(antes["total_spent"])
    assert float(depois["bill_paid"]) >= 350.0

    # e nao entrou no consumo do mes
    painel = client.get(
        "/api/v1/dashboard", params={"month": "2026-10-01"},
        headers=casa["headers"],
    ).json()["cashflow"]
    assert float(painel["consumo"]) < float(painel["outflow"])


def test_a_fatura_classificada_como_gasto_aparece_como_suspeita(client, com_historico):
    """O banco escreve a linha de um jeito que nenhuma regra reconhece, ela entra
    como gasto, e ninguem avisa. E esse silencio que o aviso quebra."""
    casa = com_historico
    lancar(
        client, casa, casa["conta"], booked_on="2026-10-09", amount="1750.00",
        direction="SAIDA", description="DEB AUT FATURA CTA 0001",
        category_id=casa["cat"]["despesas.mercado"],
    )

    resumo = client.get(
        "/api/v1/cards/summary",
        params={"month": "2026-10-01"},
        headers=casa["headers"],
    ).json()

    suspeitas = {s["description"] for s in resumo["possible_duplicates"]}
    assert "DEB AUT FATURA CTA 0001" in suspeitas
    assert resumo["aviso"] is not None

    # a linha bem classificada NAO entra na lista de suspeitas
    assert not any(
        s["category_name"] == "Pagamento de fatura"
        for s in resumo["possible_duplicates"]
    )
