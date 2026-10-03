"""A categoria do que ainda nao se sabe o que e.

"Nem sempre pelo nome dos gastos vou saber o que e." - e o pedido conserta um
erro que ja existia.

A analise por categoria ja juntava os lancamentos sem categoria num balde
chamado "Sem categoria". Mas aquele balde e um ROTULO CALCULADO, nao uma
categoria: a tela de Categorias nasce da arvore, entao o gasto sem categoria nao
tinha linha nenhuma la - e o total daquela tela ficava menor que o "Gastou" do
Resumo, sem uma linha explicando a diferenca. Rotulo calculado tambem nao abre,
nao recebe meta, e nao da para escolher ao lancar a mao.

Estes testes guardam as duas pontas: o que o sistema nao reconhece vai para um
lugar visivel, e esse lugar nao desaparece nem pode ser apagado.
"""

from __future__ import annotations

import os
import pathlib
import uuid
from datetime import date
from decimal import Decimal

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
def casa(client):
    from sqlalchemy import text

    from app.cli import seed_family
    from app.db.session import SessionLocal

    sufixo = uuid.uuid4().hex[:8]
    email = f"felipe.adef.{sufixo}@exemplo.com"
    family_id = seed_family(
        name=f"Familia {sufixo}",
        titular="Felipe Ferrari",
        titular_email=email,
        titular_password="segredo-de-teste",
        conjuge=None,
        conjuge_email=None,
        conjuge_password=None,
        dependentes=["Cecilia Ferrari"],
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
    return {
        "family_id": family_id,
        "headers": headers,
        "conta": conta["id"],
        "cat": cats,
        "mes": date.today().replace(day=1).isoformat(),
    }


def lancar(client, casa, **kw):
    corpo = {
        "account_id": casa["conta"],
        "direction": "SAIDA",
        "booked_on": date.today().replace(day=10).isoformat(),
        "status": "EFETIVADA",
        **kw,
    }
    resposta = client.post("/api/v1/transactions", json=corpo, headers=casa["headers"])
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


# ---------------------------------------------------------------------------
# A arvore
# ---------------------------------------------------------------------------
def test_a_familia_nasce_com_a_definir_nos_dois_lados(casa):
    assert "despesas.a_definir" in casa["cat"]
    assert "receitas.a_definir" in casa["cat"]


def test_a_definir_nao_pode_ser_excluida(client, casa):
    """Ela e o destino do que o sistema nao soube classificar. Sem ela, o
    lancamento volta a entrar sem categoria e a desaparecer da tela de
    Categorias - o problema que ela existe para resolver."""
    resposta = client.delete(
        f"/api/v1/categories/{casa['cat']['despesas.a_definir']}", headers=casa["headers"]
    )
    assert resposta.status_code == 409, resposta.text
    assert "nao foi classificado" in resposta.json()["detail"]


# ---------------------------------------------------------------------------
# O lancamento a mao
# ---------------------------------------------------------------------------
def test_lancamento_sem_categoria_cai_em_a_definir(client, casa):
    criado = lancar(client, casa, amount="88.00", description="Nao lembro o que foi")
    assert criado["category_id"] == casa["cat"]["despesas.a_definir"]


def test_entrada_sem_categoria_cai_na_a_definir_de_receita(client, casa):
    criado = lancar(
        client, casa, amount="500.00", direction="ENTRADA", description="TED de alguem"
    )
    assert criado["category_id"] == casa["cat"]["receitas.a_definir"]


def test_a_entrada_a_definir_continua_contando_como_renda(client, casa):
    """Decisao, nao descuido: entrada que ninguem classificou ainda e dinheiro
    que esta na conta. Marcar como "nao e renda" a esconderia - e pior, ela
    apareceria somada ao balde de doacoes, que e onde moram as entradas que de
    fato nao sao renda. Rotulo errado e pior que rotulo faltando."""
    lancar(client, casa, amount="500.00", direction="ENTRADA", description="TED de alguem")
    painel = client.get(
        "/api/v1/dashboard", params={"month": casa["mes"]}, headers=casa["headers"]
    ).json()
    assert Decimal(painel["cashflow"]["renda"]) == Decimal("500.00")
    assert Decimal(painel["cashflow"]["doacoes"]) == Decimal("0.00")


# ---------------------------------------------------------------------------
# A importacao
# ---------------------------------------------------------------------------
def test_a_conferencia_distingue_sugestao_de_palpite(client, casa):
    """A tela precisa das duas coisas separadas: "MERCADO X -> Mercado" e um
    palpite com base em algo; "A definir" e a ausencia de palpite. Mostradas
    iguais, a segunda passaria por sugestao e seria confirmada sem ninguem
    olhar."""
    conteudo = (SAMPLES / "extrato-exemplo.csv").read_bytes()
    lote = client.post(
        "/api/v1/imports",
        data={"account_id": casa["conta"]},
        files={"file": ("extrato-exemplo.csv", conteudo, "application/octet-stream")},
        headers=casa["headers"],
    ).json()

    por_descricao = {i["description"].upper(): i for i in lote["preview"]}
    mercado = next(i for d, i in por_descricao.items() if "SUPERMERCADO" in d)
    assert mercado["suggested_is_pending"] is False
    assert mercado["suggested_category_name"]

    bambu = next(i for d, i in por_descricao.items() if "BAMBU" in d)
    assert bambu["suggested_is_pending"] is True
    assert bambu["suggested_category_id"] == casa["cat"]["despesas.a_definir"]
    assert bambu["suggested_category_name"] == "A definir"


def test_corrigir_a_categoria_antes_de_salvar(client, casa):
    """O que ele nao achava na tela: trocar a categoria na conferencia, sem
    precisar gravar primeiro e corrigir depois."""
    conteudo = (SAMPLES / "extrato-exemplo.csv").read_bytes()
    lote = client.post(
        "/api/v1/imports",
        data={"account_id": casa["conta"]},
        files={"file": ("extrato-exemplo.csv", conteudo, "application/octet-stream")},
        headers=casa["headers"],
    ).json()
    bambu = next(i for i in lote["preview"] if "BAMBU" in i["description"].upper())
    escolhida = casa["cat"]["despesas.market_places"]

    client.post(
        f"/api/v1/imports/{lote['id']}/confirm",
        json={
            "selected_indexes": [bambu["index"]],
            "category_overrides": {str(bambu["index"]): escolhida},
        },
        headers=casa["headers"],
    )
    lancamentos = client.get(
        "/api/v1/transactions",
        params={"start": "2026-01-01", "end": "2026-12-31"},
        headers=casa["headers"],
    ).json()
    assert len(lancamentos) == 1
    assert lancamentos[0]["category_id"] == escolhida


# ---------------------------------------------------------------------------
# O pendente nao desaparece
# ---------------------------------------------------------------------------
def test_a_definir_aparece_na_tela_de_categorias(client, casa):
    """A diferenca entre categoria de verdade e rotulo calculado: a tela de
    Categorias nasce da arvore. Antes, este gasto nao tinha linha nenhuma la, e o
    total da tela ficava menor que o do Resumo sem explicacao."""
    lancar(client, casa, amount="820.00", description="Debito que ninguem reconhece")

    resumo = client.get(
        "/api/v1/categories/resumo", params={"month": casa["mes"]}, headers=casa["headers"]
    ).json()
    linhas = {c["name"]: c for c in resumo["categories"]}
    assert "A definir" in linhas
    assert Decimal(linhas["A definir"]["spent"]) == Decimal("820.00")


def test_o_painel_cobra_o_que_esta_a_definir(client, casa):
    """"Salvo agora, arrumo depois" so funciona se o depois aparecer em algum
    lugar."""
    lancar(client, casa, amount="820.00", description="Debito que ninguem reconhece")
    lancar(client, casa, amount="30.00", description="Outro que ninguem reconhece")
    lancar(
        client, casa, amount="100.00", description="Mercado",
        category_id=casa["cat"]["despesas.mercado"],
    )

    painel = client.get(
        "/api/v1/dashboard", params={"month": casa["mes"]}, headers=casa["headers"]
    ).json()
    assert painel["pendentes"]["quantos"] == 2
    assert Decimal(painel["pendentes"]["total"]) == Decimal("850.00")


def test_resolver_a_categoria_tira_do_pendente(client, casa):
    criado = lancar(client, casa, amount="820.00", description="Debito desconhecido")
    client.patch(
        f"/api/v1/transactions/{criado['id']}",
        json={"category_id": casa["cat"]["despesas.mercado"]},
        headers=casa["headers"],
    )
    painel = client.get(
        "/api/v1/dashboard", params={"month": casa["mes"]}, headers=casa["headers"]
    ).json()
    assert painel["pendentes"]["quantos"] == 0


def test_a_lista_de_gastos_sabe_filtrar_os_pendentes(client, casa):
    lancar(client, casa, amount="820.00", description="Debito desconhecido")
    lancar(
        client, casa, amount="100.00", description="Mercado",
        category_id=casa["cat"]["despesas.mercado"],
    )
    hoje = date.today()
    pendentes = client.get(
        "/api/v1/transactions",
        params={
            "start": hoje.replace(day=1).isoformat(),
            "end": hoje.replace(day=28).isoformat(),
            "only_uncategorized": True,
        },
        headers=casa["headers"],
    ).json()
    assert [t["description"] for t in pendentes] == ["Debito desconhecido"]
