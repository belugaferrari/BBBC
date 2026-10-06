"""O mes em que o dinheiro sai da conta.

"O extrato do cartao vem com a data da efetivacao da compra, nao com a data do
pagamento do cartao. (...) ele mostra na data da compra (...) mas o valor so e
contabilizado como gasto no mes em que ele efetivamente saiu da conta."

Duas datas por lancamento: `booked_on` e quando aconteceu, `paid_on` e quando o
dinheiro saiu. O MES de tudo que fala de dinheiro e o do `paid_on` - e assim o
Resumo fecha com o extrato bancario, que e o documento contra o qual ele confere.
"""

from __future__ import annotations

import calendar
import itertools
import os
import uuid
from datetime import date
from decimal import Decimal

import pytest

from app.services.caixa import data_de_caixa, fatura_que_cobra


# ---------------------------------------------------------------------------
# A regra, sozinha
# ---------------------------------------------------------------------------
def test_em_conta_corrente_o_dinheiro_sai_no_dia():
    assert data_de_caixa(date(2026, 9, 25), e_cartao=False) == date(2026, 9, 25)


def test_sem_os_dias_da_fatura_a_compra_cai_no_mes_seguinte():
    """E como ele descreveu o proprio cartao: "aparece contabilmente so no mes
    seguinte". Sem o dia de fechamento cadastrado, a suposicao e essa - a mais
    comum, e a que nao antecipa gasto nenhum."""
    assert data_de_caixa(date(2026, 9, 1), e_cartao=True) == date(2026, 10, 10)
    assert data_de_caixa(date(2026, 9, 30), e_cartao=True) == date(2026, 10, 10)


def test_o_dia_do_fechamento_separa_duas_compras_quase_iguais():
    """Comprou dia 24, entra na fatura deste mes; dia 26, ja e a do mes que vem.
    Um dia de diferenca, um mes de diferenca no caixa - e e assim mesmo."""
    antes = fatura_que_cobra(date(2026, 9, 24), fechamento=25, vencimento=5)
    depois = fatura_que_cobra(date(2026, 9, 26), fechamento=25, vencimento=5)
    assert antes == date(2026, 10, 5)
    assert depois == date(2026, 11, 5)


def test_vencimento_depois_do_fechamento_vence_no_mesmo_mes():
    """Fecha dia 5, vence dia 15: a fatura nao atravessa o mes."""
    assert fatura_que_cobra(date(2026, 9, 3), fechamento=5, vencimento=15) == date(
        2026, 9, 15
    )


def test_dia_31_em_fevereiro_vira_o_ultimo_dia():
    """Cartao que fecha dia 31 existe, e fevereiro tambem. Sem o corte, a conta
    levantaria ValueError no meio de uma importacao."""
    assert fatura_que_cobra(date(2026, 1, 15), fechamento=31, vencimento=31) == date(
        2026, 2, 28
    )


def test_a_virada_do_ano_nao_quebra():
    assert fatura_que_cobra(date(2026, 12, 20), fechamento=25, vencimento=5) == date(
        2027, 1, 5
    )


# ---------------------------------------------------------------------------
# A regra existe duas vezes - e as duas tem de concordar
# ---------------------------------------------------------------------------
@pytest.mark.skipif(
    not os.getenv("BBBC_TEST_DATABASE_URL"),
    reason="defina BBBC_TEST_DATABASE_URL para rodar a integracao",
)
def test_a_regra_em_sql_concorda_com_a_regra_em_python():
    """A migration 0017 carrega as linhas antigas com uma gemea em SQL da conta
    que vive em `caixa.py`. Duas implementacoes da mesma regra divergem com o
    tempo - a nao ser que alguem compare. Este teste compara."""
    from sqlalchemy import text

    from app.db.session import SessionLocal

    datas = [
        date(ano, mes, dia)
        for ano in (2025, 2026)
        for mes in (1, 2, 6, 12)
        for dia in sorted({1, 5, 25, 26, calendar.monthrange(ano, mes)[1]})
    ]
    configuracoes = [(None, None), *itertools.product([1, 5, 25, 31], [1, 10, 25, 31])]

    with SessionLocal() as db:
        for compra, (fecha, vence) in itertools.product(datas, configuracoes):
            em_sql = db.execute(
                text(
                    "SELECT bbbc_fatura_que_cobra("
                    "CAST(:compra AS date), CAST(:fecha AS smallint), "
                    "CAST(:vence AS smallint))"
                ),
                {"compra": compra, "fecha": fecha, "vence": vence},
            ).scalar_one()
            em_python = fatura_que_cobra(compra, fechamento=fecha, vencimento=vence)
            assert em_sql == em_python, (compra, fecha, vence, em_sql, em_python)


# ---------------------------------------------------------------------------
# O sistema inteiro, do lancamento ao Resumo
# ---------------------------------------------------------------------------
pytestmark_integracao = pytest.mark.skipif(
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
    from sqlalchemy import text

    from app.cli import seed_family
    from app.db.session import SessionLocal

    sufixo = uuid.uuid4().hex[:8]
    email = f"felipe.caixa.{sufixo}@exemplo.com"
    family_id = seed_family(
        name=f"Familia {sufixo}",
        titular="Felipe",
        titular_email=email,
        titular_password="segredo-de-teste",
        conjuge="Clarissa",
        conjuge_email=f"clarissa.caixa.{sufixo}@exemplo.com",
        conjuge_password="segredo-de-teste",
        dependentes=[],
    )
    auth = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "segredo-de-teste"}
    ).json()
    headers = {"Authorization": f"Bearer {auth['access_token']}"}
    corrente = client.post(
        "/api/v1/accounts", json={"name": "Itau", "type": "CONTA_CORRENTE"},
        headers=headers,
    ).json()
    cartao = client.post(
        "/api/v1/accounts",
        json={
            "name": "Itau Visa",
            "type": "CARTAO_CREDITO",
            "statement_close_day": 25,
            "statement_due_day": 5,
        },
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
    return {"headers": headers, "corrente": corrente["id"], "cartao": cartao["id"], "cat": cats}


def lancar(client, casa, conta, **kw):
    corpo = {
        "account_id": conta,
        "direction": "SAIDA",
        "status": "EFETIVADA",
        "description": "Compra",
        **kw,
    }
    resposta = client.post("/api/v1/transactions", json=corpo, headers=casa["headers"])
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def consumo(client, casa, mes: str) -> Decimal:
    return Decimal(
        client.get(
            "/api/v1/dashboard", params={"month": mes}, headers=casa["headers"]
        ).json()["cashflow"]["consumo"]
    )


@pytestmark_integracao
def test_a_compra_no_cartao_guarda_as_duas_datas(client, casa):
    criado = lancar(
        client, casa, casa["cartao"], booked_on="2026-09-20", amount="300.00",
        category_id=casa["cat"]["despesas.restaurantes"],
    )
    # o dia da compra, que e o que ele lembra
    assert criado["booked_on"] == "2026-09-20"
    # e o dia em que o dinheiro sai: fecha 25/09, vence 05/10
    assert criado["paid_on"] == "2026-10-05"


@pytestmark_integracao
def test_a_compra_no_cartao_pesa_no_mes_da_fatura(client, casa):
    lancar(
        client, casa, casa["cartao"], booked_on="2026-09-20", amount="300.00",
        category_id=casa["cat"]["despesas.restaurantes"],
    )
    assert consumo(client, casa, "2026-09-01") == Decimal("0.00")
    assert consumo(client, casa, "2026-10-01") == Decimal("300.00")


@pytestmark_integracao
def test_na_conta_corrente_nada_muda(client, casa):
    """A regra e so do cartao. Mexer no resto seria trocar um erro por outro."""
    criado = lancar(
        client, casa, casa["corrente"], booked_on="2026-09-20", amount="300.00",
        category_id=casa["cat"]["despesas.restaurantes"],
    )
    assert criado["paid_on"] == criado["booked_on"] == "2026-09-20"
    assert consumo(client, casa, "2026-09-01") == Decimal("300.00")


@pytestmark_integracao
def test_a_compra_depois_do_fechamento_pula_uma_fatura(client, casa):
    """Dia 26, com fechamento no 25: so e cobrada na fatura de novembro."""
    lancar(
        client, casa, casa["cartao"], booked_on="2026-09-26", amount="300.00",
        category_id=casa["cat"]["despesas.restaurantes"],
    )
    assert consumo(client, casa, "2026-10-01") == Decimal("0.00")
    assert consumo(client, casa, "2026-11-01") == Decimal("300.00")


@pytestmark_integracao
def test_a_lista_do_mes_mostra_a_compra_com_a_data_dela(client, casa):
    """A lista e o Resumo vistos de perto: aparecem no MESMO mes, e a linha
    carrega a data da compra para ele reconhecer o gasto."""
    lancar(
        client, casa, casa["cartao"], booked_on="2026-09-20", amount="300.00",
        description="JANTAR COM AMIGOS",
        category_id=casa["cat"]["despesas.restaurantes"],
    )
    setembro = client.get(
        "/api/v1/transactions",
        params={"start": "2026-09-01", "end": "2026-09-30"},
        headers=casa["headers"],
    ).json()
    assert all(t["description"] != "JANTAR COM AMIGOS" for t in setembro)

    outubro = client.get(
        "/api/v1/transactions",
        params={"start": "2026-10-01", "end": "2026-10-31"},
        headers=casa["headers"],
    ).json()
    jantar = next(t for t in outubro if t["description"] == "JANTAR COM AMIGOS")
    assert jantar["booked_on"] == "2026-09-20"
    assert jantar["paid_on"] == "2026-10-05"


@pytestmark_integracao
def test_a_categoria_tambem_segue_o_mes_do_caixa(client, casa):
    """Resumo e categorias tem de contar a mesma coisa. Duas respostas para a
    mesma pergunta e pior que uma resposta incomoda."""
    lancar(
        client, casa, casa["cartao"], booked_on="2026-09-20", amount="300.00",
        category_id=casa["cat"]["despesas.restaurantes"],
    )
    def restaurantes(mes: str) -> Decimal:
        resumo = client.get(
            "/api/v1/categories/resumo", params={"month": mes, "depth": 2},
            headers=casa["headers"],
        ).json()
        linha = next(
            c for c in resumo["categories"] if c["path"] == "despesas.restaurantes"
        )
        return Decimal(linha["spent"])

    assert restaurantes("2026-09-01") == Decimal("0.00")
    assert restaurantes("2026-10-01") == Decimal("300.00")


@pytestmark_integracao
def test_o_sobrou_do_mes_nao_conta_o_cartao_duas_vezes(client, casa):
    """O numero mais visivel do app, e o que a mudanca de mes poe em risco.

    A compra no cartao e a fatura que a paga passaram a cair no MESMO mes - e as
    duas sao saida de dinheiro no extrato. Somando as duas, todo mes com cartao
    mostraria o dobro do gasto em "sobrou no mes". O que mudou de lugar (a
    fatura paga, a transferencia entre contas) sai dos dois lados da conta.
    """
    lancar(
        client, casa, casa["corrente"], booked_on="2026-10-05", amount="10000.00",
        direction="ENTRADA", description="PRO LABORE",
        category_id=casa["cat"]["receitas.ativa_fixa.pro_labore"],
    )
    # a compra de setembro: cobrada na fatura que vence em 05/10
    lancar(
        client, casa, casa["cartao"], booked_on="2026-09-20", amount="3000.00",
        category_id=casa["cat"]["despesas.mercado"],
    )
    # e a fatura sendo paga, no mesmo mes
    lancar(
        client, casa, casa["corrente"], booked_on="2026-10-05", amount="3000.00",
        description="PAGAMENTO FATURA CARTAO",
        category_id=casa["cat"]["transferencias.pagamento_cartao"],
    )

    painel = client.get(
        "/api/v1/dashboard", params={"month": "2026-10-01"}, headers=casa["headers"]
    ).json()["cashflow"]

    assert Decimal(painel["consumo"]) == Decimal("3000.00")
    assert Decimal(painel["saiu_do_bolso"]) == Decimal("3000.00")
    # 10.000 de entrada menos 3.000 de gasto - e nao menos 6.000
    assert Decimal(painel["net"]) == Decimal("7000.00")
