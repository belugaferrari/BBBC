"""O que o servidor nao manda para o aplicativo.

Com o aplicativo guardando uma copia dos dados no celular para funcionar
offline, o que o servidor envia e o que fica gravado no aparelho - e o que fica
gravado e o que vaza se o celular for perdido. Esconder na hora de desenhar a
tela nao bastaria: o valor sensivel ficaria em texto puro no armazenamento
local. Por isso o corte e na borda, e por isso estes testes olham a RESPOSTA da
API, nao a tela.
"""

from __future__ import annotations

import os
import uuid

import pytest

from app.services.mascara import nome_curto, sem_digitos_sensiveis, sigla_instituicao


class TestNomeCurto:
    def test_sobrenome_vira_inicial(self):
        assert nome_curto("Cecilia Ferrari") == "Cecilia F."

    def test_primeiro_nome_fica_inteiro(self):
        """E por ele que a familia se reconhece na tela."""
        assert nome_curto("Felipe") == "Felipe"

    def test_particulas_nao_viram_inicial(self):
        """'Maria da Silva' e 'Maria S.', nao 'Maria D. S.'."""
        assert nome_curto("Maria da Silva") == "Maria S."

    def test_varios_sobrenomes(self):
        assert nome_curto("Maria da Silva Santos") == "Maria S. S."

    def test_vazio_nao_estoura(self):
        assert nome_curto(None) == ""
        assert nome_curto("   ") == ""


class TestSiglaInstituicao:
    @pytest.mark.parametrize(
        ("banco", "sigla"),
        [
            ("Banco do Brasil", "BB"),
            ("Caixa Economica Federal", "CEF"),
            ("Itau Unibanco", "IU"),
            ("Nubank", "NU"),
            ("BTG Pactual", "BP"),
        ],
    )
    def test_iniciais(self, banco, sigla):
        assert sigla_instituicao(banco) == sigla

    def test_vazio_nao_estoura(self):
        assert sigla_instituicao(None) == ""


class TestSemDigitosSensiveis:
    def test_agencia_e_conta_somem(self):
        assert "1234" not in sem_digitos_sensiveis("Itau ag 1234 cc 56789-0")
        assert "56789" not in sem_digitos_sensiveis("Itau ag 1234 cc 56789-0")

    def test_numero_curto_sobrevive(self):
        """'Conta 2' e 'Carteira 10' sao nomes legitimos; apaga-los tornaria a
        lista de contas indistinguivel."""
        assert sem_digitos_sensiveis("Conta 2") == "Conta 2"
        assert sem_digitos_sensiveis("Carteira 10") == "Carteira 10"

    def test_nome_sem_numero_fica_igual(self):
        assert sem_digitos_sensiveis("Conta corrente") == "Conta corrente"

    def test_cartao_de_16_digitos_some(self):
        assert "4111" not in sem_digitos_sensiveis("Cartao 4111111111111111")


# ------------------------------------------------- a borda, pela API de verdade

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
def familia(client):
    from app.cli import seed_family

    sufixo = uuid.uuid4().hex[:8]
    email = f"felipe.masc.{sufixo}@exemplo.com"
    seed_family(
        name=f"Familia {sufixo}", titular="Felipe Ferrari", titular_email=email,
        titular_password="segredo-de-teste",
        conjuge="Clarissa Marlet", conjuge_email=f"clarissa.{sufixo}@exemplo.com",
        conjuge_password="segredo-de-teste",
        dependentes=["Cecilia Ferrari", "Giovanna Ferrari"],
    )
    resposta = client.post("/api/v1/auth/login",
                           json={"email": email, "password": "segredo-de-teste"})
    return {"login": resposta.json(),
            "headers": {"Authorization": f"Bearer {resposta.json()['access_token']}"}}


@pytestmark_integracao
def test_login_nao_devolve_nome_completo(client, familia):
    assert familia["login"]["full_name"] == "Felipe F."
    assert "Ferrari" not in familia["login"]["full_name"]


@pytestmark_integracao
def test_lista_de_membros_nao_devolve_nome_completo(client, familia):
    membros = client.get("/api/v1/auth/members", headers=familia["headers"]).json()
    nomes = [m["name"] for m in membros]
    assert "Cecilia F." in nomes
    assert not any("Ferrari" in n or "Marlet" in n for n in nomes), nomes


@pytestmark_integracao
def test_nome_de_conta_nao_devolve_agencia_nem_conta(client, familia):
    """O usuario digita o numero junto; o numero nao atravessa a borda."""
    criada = client.post(
        "/api/v1/accounts",
        json={"name": "Itau ag 1234 cc 56789-0", "type": "CONTA_CORRENTE"},
        headers=familia["headers"],
    ).json()
    assert "1234" not in criada["name"]
    assert "56789" not in criada["name"]

    listadas = client.get("/api/v1/accounts", headers=familia["headers"]).json()
    assert all("1234" not in c["name"] for c in listadas)


def _nenhum_sobrenome_em(objeto, sobrenomes=("Ferrari", "Marlet")) -> None:
    """Varre a resposta inteira, em vez de confiar no nome da chave.

    Escrito assim porque a primeira versao deste teste olhava 'member_name'
    enquanto a API devolvia 'name' - e passou, sem provar nada, com o nome
    completo saindo do servidor. O campo pode mudar de nome; o sobrenome nao
    pode aparecer em lugar nenhum.
    """
    import json

    texto = json.dumps(objeto, default=str)
    for sobrenome in sobrenomes:
        assert sobrenome not in texto, f"{sobrenome!r} vazou em: {texto[:400]}"


@pytestmark_integracao
def test_gastos_por_pessoa_nao_devolvem_nome_completo(client, familia):
    """Com um gasto de verdade no periodo, para a lista nao vir vazia e o teste
    nao passar por falta de dado."""
    conta = client.post(
        "/api/v1/accounts", json={"name": "Carteira", "type": "DINHEIRO"},
        headers=familia["headers"],
    ).json()
    criado = client.post(
        "/api/v1/transactions",
        json={"account_id": conta["id"], "booked_on": "2026-05-10",
              "amount": "80.00", "direction": "SAIDA", "description": "Feira"},
        headers=familia["headers"],
    )
    assert criado.status_code == 201, criado.text

    relatorio = client.get(
        "/api/v1/transactions/by-category",
        params={"start": "2026-01-01", "end": "2026-12-31"},
        headers=familia["headers"],
    )
    assert relatorio.status_code == 200, relatorio.text

    por_pessoa = relatorio.json()["by_member"]
    assert por_pessoa, "sem linhas, o teste nao prova nada"
    _nenhum_sobrenome_em(por_pessoa)
    assert any("Felipe" in str(linha) for linha in por_pessoa), por_pessoa


@pytestmark_integracao
def test_deducoes_do_ir_nao_devolvem_nome_completo(client, familia):
    """A tela de IR lista a quem pertence cada despesa dedutivel."""
    resposta = client.get("/api/v1/tax/2026", headers=familia["headers"])
    assert resposta.status_code == 200, resposta.text
    _nenhum_sobrenome_em(resposta.json())


@pytestmark_integracao
def test_a_resposta_do_login_inteira_esta_limpa(client, familia):
    _nenhum_sobrenome_em(familia["login"])
