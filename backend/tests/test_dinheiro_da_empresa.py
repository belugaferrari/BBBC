"""O dinheiro da empresa nao e o dinheiro da familia.

"Eu criei varias contas para entender de onde vem o dinheiro que estou
contabilizando. Mas o sistema esta somando todas na hora de me apresentar os
numeros?"

Estava - e uma delas nao podia entrar. A migration 0007 ja dizia isso no
proprio banco, no comentario da coluna: "true para conta da empresa: o saldo nao
entra no patrimonio da familia". Nunca tinha sido implementado.

O erro ficava escondido enquanto a conta da empresa fosse cadastrada com o tipo
"PJ", porque PJ nao cai em nenhum dos baldes que o patrimonio soma. Bastava
cadastra-la como CONTA CORRENTE - que e o que ela e - para o saldo inteiro
entrar no patrimonio da familia. E a tela de Contas, que sempre somou so as
pessoais, mostrava outro numero: duas respostas para a mesma pergunta.

O dinheiro da empresa tem socio, tem imposto para sair de la, e some no dia em
que a empresa gastar. Somado ao patrimonio, inflava justamente o numero que
serve para decidir se da para comprar alguma coisa.
"""

from __future__ import annotations

import os
import uuid
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


@pytest.fixture
def casa(client):
    from app.cli import seed_family

    sufixo = uuid.uuid4().hex[:8]
    email = f"felipe.emp.{sufixo}@exemplo.com"
    seed_family(
        name=f"Familia {sufixo}",
        titular="Felipe",
        titular_email=email,
        titular_password="segredo-de-teste",
        conjuge="Clarissa",
        conjuge_email=f"clarissa.emp.{sufixo}@exemplo.com",
        conjuge_password="segredo-de-teste",
        dependentes=[],
    )
    auth = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "segredo-de-teste"}
    ).json()
    return {"headers": {"Authorization": f"Bearer {auth['access_token']}"}}


def conta(client, casa, **kw):
    resposta = client.post("/api/v1/accounts", json=kw, headers=casa["headers"])
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def saldos(client, casa) -> dict:
    return client.get("/api/v1/dashboard", headers=casa["headers"]).json()["balances"]


def test_a_conta_da_empresa_fica_fora_do_patrimonio(client, casa):
    """O caso que acontece: a conta da empresa cadastrada como conta corrente."""
    conta(client, casa, name="Itau", type="CONTA_CORRENTE", current_balance="10000.00")
    conta(
        client, casa, name="Conta PJ", type="CONTA_CORRENTE",
        current_balance="250000.00", is_business=True,
    )

    numeros = saldos(client, casa)
    assert Decimal(numeros["liquid"]) == Decimal("10000.00")
    assert Decimal(numeros["net_worth"]) == Decimal("10000.00")


def test_o_dinheiro_da_empresa_nao_some_da_tela(client, casa):
    """Saldo que desaparece e o jeito mais rapido de alguem achar que o sistema
    perdeu dinheiro. Ele volta em linha propria."""
    conta(client, casa, name="Itau", type="CONTA_CORRENTE", current_balance="10000.00")
    conta(
        client, casa, name="Conta PJ", type="CONTA_CORRENTE",
        current_balance="250000.00", is_business=True,
    )
    assert Decimal(saldos(client, casa)["na_empresa"]) == Decimal("250000.00")


def test_sem_conta_de_empresa_o_numero_e_zero(client, casa):
    conta(client, casa, name="Itau", type="CONTA_CORRENTE", current_balance="10000.00")
    numeros = saldos(client, casa)
    assert Decimal(numeros["na_empresa"]) == Decimal("0.00")
    assert Decimal(numeros["net_worth"]) == Decimal("10000.00")


def test_a_tela_de_patrimonio_concorda_com_o_resumo(client, casa):
    """Duas telas somando contas diferentes era o sintoma original."""
    conta(client, casa, name="Itau", type="CONTA_CORRENTE", current_balance="10000.00")
    conta(client, casa, name="Corretora", type="INVESTIMENTO", current_balance="40000.00")
    conta(
        client, casa, name="Conta PJ", type="CONTA_CORRENTE",
        current_balance="250000.00", is_business=True,
    )

    resumo = saldos(client, casa)
    patrimonio = client.get("/api/v1/net-worth", headers=casa["headers"])
    assert patrimonio.status_code == 200, patrimonio.text
    assert Decimal(patrimonio.json()["liquid"]) == Decimal(resumo["liquid"])
    assert Decimal(patrimonio.json()["invested"]) == Decimal(resumo["invested"])


def test_varias_contas_pessoais_somam_normalmente(client, casa):
    """A pergunta dele tinha duas partes, e esta e a que esta certa: as contas
    pessoais SOMAM mesmo - e e para isso que elas existem. Separar por conta e
    para saber de onde o dinheiro veio, nao para contar menos."""
    conta(client, casa, name="Itau", type="CONTA_CORRENTE", current_balance="10000.00")
    conta(client, casa, name="Nubank", type="CONTA_CORRENTE", current_balance="3000.00")
    conta(client, casa, name="Carteira", type="DINHEIRO", current_balance="200.00")
    assert Decimal(saldos(client, casa)["liquid"]) == Decimal("13200.00")
