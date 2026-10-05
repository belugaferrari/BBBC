"""A compra parcelada, que aparece em todos os meses em que ainda esta viva.

"Contas parceladas devem aparecer em todos os meses em que ainda estao vigentes
as parcelas (nao apenas no mes de contratacao). (...) a parcela e paga junto ao
cartao, entao ela conta efetivamente como saida de dinheiro no mes seguinte."

Cada fatura cobra uma parcela, e cada parcela sai da conta no vencimento da SUA
fatura. Importando fatura a fatura, as parcelas se distribuem pelos meses sozinhas
- e as que ainda nao foram cobradas existem como PREVISTA, para o compromisso
aparecer antes de a fatura chegar.

O perigo mora no encontro das duas coisas: quando a fatura de novembro traz a
parcela 03/10, ela e a mesma parcela que ja estava prevista para novembro. Se o
sistema nao reconhecer, novembro conta a parcela duas vezes - e o erro aparece
exatamente no mes em que ninguem esta mais olhando para aquela compra.
"""

from __future__ import annotations

import os
import uuid
from decimal import Decimal

import pytest

from app.services.parcelas import Parcela, ler_parcela, numerar, raiz_da_descricao

pytestmark = pytest.mark.skipif(
    not os.getenv("BBBC_TEST_DATABASE_URL"),
    reason="defina BBBC_TEST_DATABASE_URL para rodar a integracao",
)


# ---------------------------------------------------------------------------
# Ler a parcela sem confundir com data
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "descricao,esperado",
    [
        ("MAGAZINE LUIZA PARCELA 02/10", (2, 10)),
        ("CASAS BAHIA PARC 01 DE 12", (1, 12)),
        ("AMERICANAS PARC. 3/6", (3, 6)),
        ("MOVEIS (2/10)", (2, 10)),
        ("DECOLAR 03/18", (3, 18)),
    ],
)
def test_le_a_parcela_escrita_de_varios_jeitos(descricao, esperado):
    parcela = ler_parcela(descricao)
    assert (parcela.numero, parcela.total) == esperado


@pytest.mark.parametrize(
    "descricao",
    [
        "IFOOD 02/10",        # dia 2 de outubro
        "UBER TRIP 25/12",    # dia 25 de dezembro
        "POSTO SHELL",
        "LOJA PARCELA 11/10",  # numero maior que o total
        "LOJA PARCELA 1/1",    # parcela unica nao e parcelamento
    ],
)
def test_nao_inventa_parcela_onde_ha_uma_data(descricao):
    """Errar para menos custa uma informacao na tela. Errar para mais inventa
    uma compra de dez vezes o valor - e mais oito gastos futuros."""
    assert ler_parcela(descricao) is None


def test_o_valor_da_compra_sai_da_parcela_e_do_total():
    assert Parcela(2, 10).valor_da_compra(Decimal("300.00")) == Decimal("3000.00")


def test_as_parcelas_da_mesma_compra_se_reconhecem():
    """E o que permite a parcela que chega encontrar a previsao que ela ocupa."""
    assert raiz_da_descricao("MAGAZINE PARCELA 02/10") == raiz_da_descricao(
        numerar("MAGAZINE PARCELA 02/10", Parcela(3, 10))
    )


# ---------------------------------------------------------------------------
# O caminho inteiro: duas faturas seguidas
# ---------------------------------------------------------------------------
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
    email = f"felipe.parc.{sufixo}@exemplo.com"
    family_id = seed_family(
        name=f"Familia {sufixo}",
        titular="Felipe",
        titular_email=email,
        titular_password="segredo-de-teste",
        conjuge="Clarissa",
        conjuge_email=f"clarissa.parc.{sufixo}@exemplo.com",
        conjuge_password="segredo-de-teste",
        dependentes=[],
    )
    auth = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "segredo-de-teste"}
    ).json()
    headers = {"Authorization": f"Bearer {auth['access_token']}"}
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
    return {
        "family_id": family_id,
        "headers": headers,
        "cartao": cartao["id"],
        "cat": cats,
    }


def importar(client, casa, texto: str, nome: str) -> dict:
    resposta = client.post(
        "/api/v1/imports",
        data={"account_id": casa["cartao"]},
        files={"file": (nome, texto.encode("utf-8"), "text/csv")},
        headers=casa["headers"],
    )
    assert resposta.status_code == 201, resposta.text
    lote = resposta.json()
    confirmado = client.post(
        f"/api/v1/imports/{lote['id']}/confirm", json={}, headers=casa["headers"]
    )
    assert confirmado.status_code == 200, confirmado.text
    return lote


def consumo(client, casa, mes: str) -> Decimal:
    return Decimal(
        client.get(
            "/api/v1/dashboard", params={"month": mes}, headers=casa["headers"]
        ).json()["cashflow"]["consumo"]
    )


def previstas(casa) -> list:
    from sqlalchemy import text

    from app.db.session import SessionLocal

    with SessionLocal() as db:
        return db.execute(
            text(
                """
                SELECT description, paid_on, amount, installment_no, installment_total
                  FROM transactions
                 WHERE family_id = :f AND status = 'PREVISTA'
                 ORDER BY installment_no
                """
            ),
            {"f": casa["family_id"]},
        ).mappings().all()


# A fatura que vence em 05/10: compras ate 25/09.
FATURA_DE_OUTUBRO = (
    "Data;Lancamento;Valor\n"
    "10/09/2026;MAGAZINE LUIZA PARCELA 01/03;-300,00\n"
    "12/09/2026;POSTO SHELL;-200,00\n"
)
# A de novembro traz a parcela seguinte da mesma compra.
FATURA_DE_NOVEMBRO = (
    "Data;Lancamento;Valor\n"
    "10/09/2026;MAGAZINE LUIZA PARCELA 02/03;-300,00\n"
    "14/10/2026;IFOOD;-80,00\n"
)


def test_a_primeira_fatura_ja_mostra_as_parcelas_que_faltam(client, casa):
    importar(client, casa, FATURA_DE_OUTUBRO, "out.csv")

    futuras = previstas(casa)
    assert [p["installment_no"] for p in futuras] == [2, 3]
    # cada uma no mes em que vai sair: a fatura vence dia 5
    assert [p["paid_on"].isoformat() for p in futuras] == ["2026-11-05", "2026-12-05"]
    assert all(p["amount"] == Decimal("300.00") for p in futuras)


def test_a_parcela_prevista_nao_conta_como_gasto(client, casa):
    """Compromisso nao e gasto. A parcela de novembro ainda nao saiu da conta -
    e o mes de novembro nao pode ja estar gasto por causa dela."""
    importar(client, casa, FATURA_DE_OUTUBRO, "out.csv")

    assert consumo(client, casa, "2026-10-01") == Decimal("500.00")
    assert consumo(client, casa, "2026-11-01") == Decimal("0.00")


def test_a_parcela_que_chega_ocupa_o_lugar_da_prevista(client, casa):
    """O erro que este teste existe para impedir: novembro contando a parcela
    duas vezes - a prevista e a que veio na fatura."""
    importar(client, casa, FATURA_DE_OUTUBRO, "out.csv")
    importar(client, casa, FATURA_DE_NOVEMBRO, "nov.csv")

    # novembro: a parcela 2 (300) e o IFOOD (80), e nada repetido
    assert consumo(client, casa, "2026-11-01") == Decimal("380.00")

    futuras = previstas(casa)
    assert [p["installment_no"] for p in futuras] == [3]
    assert futuras[0]["paid_on"].isoformat() == "2026-12-05"


def test_a_compra_parcelada_aparece_em_todos_os_meses(client, casa):
    """"Contas parceladas devem aparecer em todos os meses em que ainda estao
    vigentes as parcelas (nao apenas no mes de contratacao)."

    Outubro, novembro e dezembro: a mesma compra, uma parcela por mes. Os dois
    primeiros ja aconteceram (vieram nas faturas); o terceiro e compromisso.
    """
    importar(client, casa, FATURA_DE_OUTUBRO, "out.csv")
    importar(client, casa, FATURA_DE_NOVEMBRO, "nov.csv")

    from sqlalchemy import text

    from app.db.session import SessionLocal

    with SessionLocal() as db:
        meses = db.execute(
            text(
                """
                SELECT to_char(paid_on, 'YYYY-MM') AS mes, status::text, amount
                  FROM transactions
                 WHERE family_id = :f AND installment_total = 3
                 ORDER BY paid_on
                """
            ),
            {"f": casa["family_id"]},
        ).mappings().all()

    assert [(m["mes"], m["status"]) for m in meses] == [
        ("2026-10", "EFETIVADA"),
        ("2026-11", "EFETIVADA"),
        ("2026-12", "PREVISTA"),
    ]
    assert all(m["amount"] == Decimal("300.00") for m in meses)


def test_a_conferencia_diz_quanto_foi_a_compra_inteira(client, casa):
    """"indica qual foi o valor de aquisicao (inclusive com quantidade de
    parcelas e valor efetivo total)". Uma parcela de R$ 300 solta nao conta que
    a compra foi de R$ 900."""
    resposta = client.post(
        "/api/v1/imports",
        data={"account_id": casa["cartao"]},
        files={"file": ("out.csv", FATURA_DE_OUTUBRO.encode("utf-8"), "text/csv")},
        headers=casa["headers"],
    )
    linha = next(
        linha
        for linha in resposta.json()["preview"]
        if "MAGAZINE" in linha["description"]
    )
    assert linha["installment_no"] == 1
    assert linha["installment_total"] == 3
    assert Decimal(linha["valor_da_compra"]) == Decimal("900.00")
    assert linha["parcelas_faltando"] == 2
    # e o mes em que ela vai pesar, antes de confirmar
    assert linha["paid_on"] == "2026-10-05"


def test_desfazer_leva_as_parcelas_previstas_junto(client, casa):
    """A previsao nasceu daquela importacao. Desfeita a importacao, ela nao pode
    ficar orfa prometendo um gasto que ninguem mais reconhece."""
    lote = importar(client, casa, FATURA_DE_OUTUBRO, "out.csv")
    assert len(previstas(casa)) == 2

    client.post(
        f"/api/v1/imports/{lote['id']}/desfazer", headers=casa["headers"]
    ).raise_for_status()
    assert previstas(casa) == []


def test_a_parcela_que_falta_aparece_na_previsao(client, casa):
    """"todo mes ela deve aparecer (nao so no primeiro)".

    O mes em que a parcela ainda nao chegou nao tem gasto nenhum por causa dela
    - e nao pode ter, porque o dinheiro nao saiu. Mas o compromisso existe, e e
    na Previsao que compromisso aparece: la ela esta, no mes em que vai cair,
    com o rotulo dizendo de que parcela se trata.
    """
    importar(client, casa, FATURA_DE_OUTUBRO, "out.csv")

    previsao = client.get(
        "/api/v1/forecast",
        params={"start": "2026-10-01", "months": 4},
        headers=casa["headers"],
    ).json()

    por_mes = {p["month"]: p for p in previsao["projection"]}
    rotulos = {
        mes: [item["label"] for item in dados["items"]] for mes, dados in por_mes.items()
    }

    # novembro e dezembro, uma parcela em cada
    assert any("2/3" in rotulo for rotulo in rotulos.get("2026-11-01", []))
    assert any("3/3" in rotulo for rotulo in rotulos.get("2026-12-01", []))
    # e janeiro, que ja passou da ultima, nao tem nenhuma
    assert not any("/3" in rotulo for rotulo in rotulos.get("2027-01-01", []))
