"""O dinheiro que volta.

"Temos que por algum tipo de reembolso tambem. Quando eu pago algo e os amigos
passam a parte deles."

Ele paga R$ 300 do jantar e tres amigos devolvem R$ 75 cada. Sem um lugar para
isso, o mes conta os R$ 300 como gasto da casa E os R$ 225 como RENDA - erra duas
vezes, e nas duas para o lado de parecer melhor do que foi.

E a mesma familia de problema da doacao, com uma diferenca que importa: a doacao
e dinheiro de OUTRA PESSOA que chega; o reembolso e dinheiro DELE que volta. Por
isso nao pode cair no mesmo balde - no relatorio de doacoes, o reembolso do
jantar apareceria como doacao de alguem, e o limite de isencao do ITCMD passaria
a contar dinheiro que nunca foi doado.
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

MES = "2026-03-01"
MES_ANTERIOR = "2026-02-10"
# A lista de "reembolsaveis" olha os ultimos dois meses, porque e para a tela de
# lancamento: gasto de um ano atras nao e o que esta esperando dinheiro voltar.
# Por isso estes testes lancam hoje, e nao no mes fixo dos outros.
HOJE = date.today().isoformat()


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


def _casa(client):
    from sqlalchemy import text

    from app.cli import seed_family
    from app.db.session import SessionLocal

    sufixo = uuid.uuid4().hex[:8]
    email = f"felipe.reemb.{sufixo}@exemplo.com"
    family_id = seed_family(
        name=f"Familia {sufixo}",
        titular="Felipe Ferrari",
        titular_email=email,
        titular_password="segredo-de-teste",
        conjuge="Clarissa Ferrari",
        conjuge_email=f"clarissa.reemb.{sufixo}@exemplo.com",
        conjuge_password="segredo-de-teste",
        dependentes=[],
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
        cats = {
            linha[0]: str(linha[1])
            for linha in db.execute(
                text("SELECT path::text, id FROM categories WHERE family_id = :f"),
                {"f": family_id},
            )
        }
        # Uma receita que E renda, escolhida do catalogo: o teste nao deve
        # depender do nome da categoria de trabalho, que pode mudar.
        renda = db.execute(
            text(
                """
                SELECT path::text FROM categories
                 WHERE family_id = :f AND kind = 'RECEITA' AND counts_as_income
                   AND nlevel(path) > 1
                 ORDER BY sort_order LIMIT 1
                """
            ),
            {"f": family_id},
        ).scalar_one()
    return {
        "family_id": family_id,
        "headers": headers,
        "conta": conta["id"],
        "cat": cats,
        "renda": renda,
    }


@pytest.fixture
def casa(client):
    """Familia nova a cada teste: lancamento e estado, e estado vaza."""
    return _casa(client)


def lancar(
    client,
    casa,
    *,
    direction: str,
    amount: str,
    categoria: str,
    descricao: str = "Lancamento",
    dia: str = MES,
    reembolso_de: str | None = None,
    espera: int = 201,
):
    corpo = {
        "account_id": casa["conta"],
        "direction": direction,
        "amount": amount,
        "booked_on": dia,
        "description": descricao,
        "category_id": casa["cat"][categoria],
        "status": "EFETIVADA",
    }
    if reembolso_de:
        corpo["reembolso_de_id"] = reembolso_de
    resposta = client.post("/api/v1/transactions", json=corpo, headers=casa["headers"])
    assert resposta.status_code == espera, resposta.text
    return resposta.json()


def resumo_do_mes(client, casa, mes: str = MES) -> dict:
    resposta = client.get(
        "/api/v1/dashboard", params={"month": mes}, headers=casa["headers"]
    )
    assert resposta.status_code == 200, resposta.text
    return resposta.json()["cashflow"]


def jantar(client, casa, valor: str = "300.00", dia: str = MES) -> dict:
    return lancar(
        client,
        casa,
        direction="SAIDA",
        amount=valor,
        categoria="despesas.restaurantes.jantar_fora"
        if "despesas.restaurantes.jantar_fora" in casa["cat"]
        else "despesas.restaurantes",
        descricao="Jantar com os amigos",
        dia=dia,
    )


# ---------------------------------------------------------------------------
# A categoria
# ---------------------------------------------------------------------------
def test_familia_nova_nasce_com_a_categoria_de_reembolso_fora_da_renda(client, casa):
    """A marca tem de atravessar a copia do catalogo.

    A familia usa uma COPIA do catalogo global. A copia que esquecesse
    `counts_as_income` pegaria o DEFAULT da tabela, que e true - e o reembolso
    voltaria a ser renda em silencio, sem erro nenhum na tela. Foi exatamente o
    que aconteceu com a doacao na primeira versao.
    """
    from sqlalchemy import text

    from app.db.session import SessionLocal

    with SessionLocal() as db:
        linhas = db.execute(
            text(
                """
                SELECT path::text, counts_as_income, ir_treatment::text
                  FROM categories
                 WHERE family_id = :f AND path <@ 'receitas.reembolsos'::ltree
                """
            ),
            {"f": casa["family_id"]},
        ).all()
    assert linhas, "a familia nova precisa ter a categoria de reembolso"
    for _, conta_como_renda, ir in linhas:
        assert conta_como_renda is False
        # Reembolso nao e rendimento: nao entra em lugar nenhum da declaracao,
        # nem como isento. Marcar como ISENTO o levaria para o quadro de
        # rendimentos isentos, inflando um numero que o Leao confere.
        assert ir == "NAO_APLICAVEL"


def test_a_arvore_que_o_aplicativo_recebe_separa_reembolso_de_doacao(client, casa):
    """A tela escolhe o que perguntar pelo CAMINHO, nao por "nao e renda".

    Hoje tres coisas diferentes carregam `counts_as_income = false`: doacao,
    reembolso e transferencia. Se a arvore nao trouxesse o caminho, a tela
    perguntaria "quem doou?" num reembolso de jantar - e gravar o amigo como
    doador estragaria o relatorio do ITCMD do ano.
    """
    arvore = client.get("/api/v1/categories", headers=casa["headers"]).json()

    achatada: dict[str, dict] = {}

    def descer(nos):
        for no in nos:
            achatada[no["path"]] = no
            descer(no["children"])

    descer(arvore)
    reembolso = achatada["receitas.reembolsos"]
    assert reembolso["counts_as_income"] is False
    assert reembolso["kind"] == "RECEITA"
    # os dois caminhos sao irmaos, e nenhum esta dentro do outro
    assert not reembolso["path"].startswith("receitas.doacoes")
    assert not achatada["receitas.doacoes"]["path"].startswith("receitas.reembolsos")


# ---------------------------------------------------------------------------
# O reembolso nao e renda, e nao e doacao
# ---------------------------------------------------------------------------
def test_reembolso_nao_entra_na_renda_do_mes(client, casa):
    salario = "10000.00"
    lancar(client, casa, direction="ENTRADA", amount=salario, categoria=casa["renda"])
    gasto = jantar(client, casa)
    lancar(
        client,
        casa,
        direction="ENTRADA",
        amount="225.00",
        categoria="receitas.reembolsos",
        descricao="Parte dos amigos",
        reembolso_de=gasto["id"],
    )

    cashflow = resumo_do_mes(client, casa)
    assert Decimal(cashflow["renda"]) == Decimal(salario)
    assert Decimal(cashflow["reembolsos"]) == Decimal("225.00")
    # entrou na conta: o `inflow` e o extrato, e o extrato nao mente
    assert Decimal(cashflow["inflow"]) == Decimal("10225.00")


def test_reembolso_nao_aparece_como_doacao(client, casa):
    """O balde proprio existe por causa do ITCMD.

    No relatorio de doacoes, o reembolso do jantar apareceria como doacao de
    alguem - e o limite de isencao estadual passaria a contar dinheiro que nunca
    foi doado, avisando de um limite que nao foi chegado.
    """
    gasto = jantar(client, casa)
    lancar(
        client,
        casa,
        direction="ENTRADA",
        amount="225.00",
        categoria="receitas.reembolsos",
        reembolso_de=gasto["id"],
    )

    cashflow = resumo_do_mes(client, casa)
    assert Decimal(cashflow["doacoes"]) == Decimal("0")
    assert Decimal(cashflow["doacoes_aplicadas"]) == Decimal("0")

    resumo = client.get(
        "/api/v1/doacoes/resumo", params={"year": 2026}, headers=casa["headers"]
    ).json()
    assert Decimal(resumo["total"]) == Decimal("0")

    # e tambem nao pode cair no balde generico de "outras entradas", ou os dois
    # numeros do Resumo diriam a mesma coisa duas vezes
    assert Decimal(cashflow["outras_entradas"]) == Decimal("0")


# ---------------------------------------------------------------------------
# O que a casa gastou de verdade
# ---------------------------------------------------------------------------
def test_o_que_voltou_sai_do_consumo_da_familia(client, casa):
    lancar(client, casa, direction="ENTRADA", amount="10000.00", categoria=casa["renda"])
    gasto = jantar(client, casa)
    for _ in range(3):
        lancar(
            client,
            casa,
            direction="ENTRADA",
            amount="75.00",
            categoria="receitas.reembolsos",
            reembolso_de=gasto["id"],
        )

    cashflow = resumo_do_mes(client, casa)
    # o gasto continua inteiro: o jantar custou R$ 300
    assert Decimal(cashflow["consumo"]) == Decimal("300.00")
    assert Decimal(cashflow["reembolsos_aplicados"]) == Decimal("225.00")
    # a casa gastou a parte dela
    assert Decimal(cashflow["consumo_proprio"]) == Decimal("75.00")


def test_reembolso_maior_que_a_conta_nao_abate_mais_do_que_foi_gasto(client, casa):
    """Amigo que devolve mais do que a conta nao esta reembolsando.

    Sem o teto por lancamento, um deposito de R$ 500 contra um jantar de R$ 300
    faria o mes parecer R$ 200 mais barato do que foi - e, com dois ou tres
    desses, o consumo da casa ficaria negativo.
    """
    gasto = jantar(client, casa, valor="300.00")
    lancar(
        client,
        casa,
        direction="ENTRADA",
        amount="500.00",
        categoria="receitas.reembolsos",
        reembolso_de=gasto["id"],
    )

    cashflow = resumo_do_mes(client, casa)
    assert Decimal(cashflow["reembolsos_aplicados"]) == Decimal("300.00")
    assert Decimal(cashflow["consumo_proprio"]) == Decimal("0")


def test_o_desconto_sai_do_mes_do_gasto_e_nao_do_mes_do_reembolso(client, casa):
    """O jantar de fevereiro custou o que custou em fevereiro.

    Se o desconto caisse no mes em que o dinheiro voltou, marco ficaria mais
    barato do que foi e fevereiro mais caro - dois meses errados por um
    lancamento certo.
    """
    gasto = jantar(client, casa, valor="300.00", dia=MES_ANTERIOR)
    lancar(
        client,
        casa,
        direction="ENTRADA",
        amount="225.00",
        categoria="receitas.reembolsos",
        reembolso_de=gasto["id"],
        dia=MES,
    )

    fevereiro = resumo_do_mes(client, casa, mes="2026-02-01")
    marco = resumo_do_mes(client, casa, mes=MES)

    assert Decimal(fevereiro["consumo_proprio"]) == Decimal("75.00")
    assert Decimal(fevereiro["reembolsos_aplicados"]) == Decimal("225.00")
    # em marco o dinheiro entrou, mas nao havia gasto para abater
    assert Decimal(marco["reembolsos"]) == Decimal("225.00")
    assert Decimal(marco["reembolsos_aplicados"]) == Decimal("0")
    assert Decimal(marco["consumo_proprio"]) == Decimal("0")


# ---------------------------------------------------------------------------
# A ligacao com o gasto
# ---------------------------------------------------------------------------
def test_reembolso_sem_gasto_apontado_continua_fora_da_renda(client, casa):
    """Nao da para exigir o apontamento.

    O deposito do amigo chega pelo extrato antes de alguem dizer de que foi. Se o
    apontamento fosse obrigatorio, a importacao pararia - entao ele e opcional, e
    o que se perde e so o desconto do consumo, nao a honestidade da renda.
    """
    lancar(client, casa, direction="ENTRADA", amount="10000.00", categoria=casa["renda"])
    jantar(client, casa)
    lancar(
        client,
        casa,
        direction="ENTRADA",
        amount="225.00",
        categoria="receitas.reembolsos",
    )

    cashflow = resumo_do_mes(client, casa)
    assert Decimal(cashflow["renda"]) == Decimal("10000.00")
    assert Decimal(cashflow["reembolsos"]) == Decimal("225.00")
    assert Decimal(cashflow["reembolsos_aplicados"]) == Decimal("0")
    assert Decimal(cashflow["consumo_proprio"]) == Decimal("300.00")


def test_reembolso_nao_pode_apontar_para_uma_entrada(client, casa):
    """Apontar para outra entrada nao quer dizer nada.

    E passaria despercebido ate alguem estranhar o consumo do mes - por isso a
    recusa e na hora de gravar, com uma frase, e nao no relatorio.
    """
    salario = lancar(
        client, casa, direction="ENTRADA", amount="10000.00", categoria=casa["renda"]
    )
    resposta = lancar(
        client,
        casa,
        direction="ENTRADA",
        amount="225.00",
        categoria="receitas.reembolsos",
        reembolso_de=salario["id"],
        espera=422,
    )
    assert "gasto" in resposta["detail"].lower()


def test_reembolso_nao_alcanca_o_gasto_de_outra_familia(client, casa):
    """O id de um gasto e um uuid, mas nao e um segredo.

    Sem a checagem de familia, um lancamento desta casa poderia abater o consumo
    da casa de outra pessoa - e o erro apareceria no Resumo DELA.
    """
    vizinha = _casa(client)
    gasto_da_vizinha = jantar(client, vizinha)

    resposta = lancar(
        client,
        casa,
        direction="ENTRADA",
        amount="225.00",
        categoria="receitas.reembolsos",
        reembolso_de=gasto_da_vizinha["id"],
        espera=404,
    )
    assert resposta["detail"]


# ---------------------------------------------------------------------------
# A lista que a tela mostra
# ---------------------------------------------------------------------------
def test_a_lista_de_gastos_diz_quanto_ja_voltou_de_cada_um(client, casa):
    gasto = jantar(client, casa, valor="300.00", dia=HOJE)
    lancar(
        client,
        casa,
        direction="ENTRADA",
        amount="75.00",
        categoria="receitas.reembolsos",
        reembolso_de=gasto["id"],
        dia=HOJE,
    )

    lista = client.get(
        "/api/v1/transactions/reembolsaveis", headers=casa["headers"]
    ).json()
    linha = next(item for item in lista if item["id"] == gasto["id"])
    assert Decimal(linha["amount"]) == Decimal("300.00")
    assert Decimal(linha["reembolsado"]) == Decimal("75.00")
    assert Decimal(linha["falta"]) == Decimal("225.00")

    # a propria entrada de reembolso nao pode aparecer na lista de gastos
    assert all(Decimal(item["amount"]) != Decimal("75.00") for item in lista)


def test_a_lista_nao_mostra_numero_de_conta_na_descricao(client, casa):
    """A regra da casa: nada de agencia e conta corrente na tela.

    A descricao vem do extrato, e extrato brasileiro traz numero de conta no meio
    do texto. A lista passa pela mascara como todo o resto.
    """
    gasto = lancar(
        client,
        casa,
        direction="SAIDA",
        amount="300.00",
        categoria="despesas.restaurantes",
        descricao="PIX AG 1234 CC 56789-0 JANTAR",
        dia=HOJE,
    )
    lista = client.get(
        "/api/v1/transactions/reembolsaveis", headers=casa["headers"]
    ).json()
    linha = next(item for item in lista if item["id"] == gasto["id"])
    assert "56789" not in linha["description"]


# ---------------------------------------------------------------------------
# A categoria continua mostrando o gasto inteiro
# ---------------------------------------------------------------------------
def test_a_categoria_mostra_o_gasto_inteiro_com_o_que_voltou_ao_lado(client, casa):
    """Dois criterios para a mesma pergunta seriam piores que um numero bruto.

    A meta de 'Restaurantes' mede o que foi gasto ali; descontar o reembolso do
    total faria a meta medir outra coisa, e a soma das categorias pararia de
    fechar com o extrato. Quem desconta e o consumo da familia, no Resumo.
    """
    gasto = jantar(client, casa, valor="300.00")
    lancar(
        client,
        casa,
        direction="ENTRADA",
        amount="225.00",
        categoria="receitas.reembolsos",
        reembolso_de=gasto["id"],
    )

    resumo = client.get(
        "/api/v1/categories/resumo",
        params={"month": MES, "depth": 2},
        headers=casa["headers"],
    ).json()
    linha = next(
        item for item in resumo["categories"] if item["path"] == "despesas.restaurantes"
    )
    assert Decimal(linha["spent"]) == Decimal("300.00")
    assert Decimal(linha["reembolsado"]) == Decimal("225.00")
    assert Decimal(resumo["total_spent"]) == Decimal("300.00")
