"""Trocar a senha de um login.

"Penso que pode ser a senha (nao tem botao para eu visualizar a senha para ver
se digitei algo errado)."

Duas faltas apareceram na mesma noite: nao dava para VER o que estava sendo
digitado, e nao dava para TROCAR a senha se fosse ela mesma - o jeito seria
mexer no banco de dados a mao. Esquecer a senha do proprio sistema nao pode ser
um beco sem saida.

So roda no computador onde o banco mora, que e o unico lugar de onde isso pode
ser pedido. Nao ha "esqueci minha senha" pela rede, e nao vai haver: um e-mail
de recuperacao seria uma porta a mais para um sistema que, de proposito, nao tem
porta nenhuma para fora.
"""

from __future__ import annotations

import os
import uuid

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
    email = f"felipe.senha.{sufixo}@exemplo.com"
    seed_family(
        name=f"Familia {sufixo}",
        titular="Felipe",
        titular_email=email,
        titular_password="a-senha-de-antes",
        conjuge="Clarissa",
        conjuge_email=f"clarissa.senha.{sufixo}@exemplo.com",
        conjuge_password="segredo-de-teste",
        dependentes=[],
    )
    return {"email": email}


def entrar(client, email: str, senha: str):
    return client.post("/api/v1/auth/login", json={"email": email, "password": senha})


def test_a_senha_nova_entra_e_a_velha_nao(client, casa):
    from app.cli import trocar_senha

    assert entrar(client, casa["email"], "a-senha-de-antes").status_code == 200

    nome = trocar_senha(casa["email"], "uma-senha-nova-boa")
    assert nome

    assert entrar(client, casa["email"], "uma-senha-nova-boa").status_code == 200
    assert entrar(client, casa["email"], "a-senha-de-antes").status_code == 401


def test_o_e_mail_nao_precisa_estar_na_caixa_certa(client, casa):
    """Quem digita o proprio e-mail no terminal as vezes capitaliza. Recusar por
    causa disso seria uma barreira sem motivo nenhum."""
    from app.cli import trocar_senha

    trocar_senha(casa["email"].upper(), "outra-senha-boa")
    assert entrar(client, casa["email"], "outra-senha-boa").status_code == 200


def test_e_mail_que_nao_existe_diz_quais_existem(client, casa):
    """Errar o e-mail e o erro mais provavel aqui. A mensagem mostra a lista em
    vez de so dizer 'nao encontrado' - a resposta esta na propria pergunta."""
    from app.cli import trocar_senha

    with pytest.raises(RuntimeError) as erro:
        trocar_senha("nao-existe@exemplo.com", "qualquer-coisa-boa")
    assert casa["email"] in str(erro.value)


def test_senha_curta_e_recusada(client, casa):
    from app.cli import trocar_senha

    with pytest.raises(RuntimeError):
        trocar_senha(casa["email"], "curta")
    # e a de antes continua valendo: nada foi alterado
    assert entrar(client, casa["email"], "a-senha-de-antes").status_code == 200


def test_os_logins_aparecem_com_apelido_e_sem_sobrenome(client, casa):
    """A pergunta que vem antes de trocar a senha e "qual era meu e-mail mesmo?".
    A lista responde - mas sem nome completo, que e regra do sistema inteiro."""
    from app.cli import listar_logins

    logins = listar_logins()
    meu = [x for x in logins if x["email"] == casa["email"]]
    assert meu, logins
    assert meu[0]["nome"] == "Felipe"
    assert all(" " not in x["nome"] for x in logins)


def test_a_senha_pode_vir_pela_entrada_padrao(client, casa):
    """No Windows, senha escrita na linha de comando aparece na lista de
    processos e no historico do terminal. Pela entrada padrao, em nenhum dos
    dois - e e por ai que o TROCAR-SENHA manda."""
    import os
    import subprocess
    import sys

    saida = subprocess.run(
        [sys.executable, "-m", "app.cli", "trocar-senha",
         "--email", casa["email"], "--senha-de-stdin"],
        input="senha-vinda-do-cano\n",
        capture_output=True,
        text=True,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        env={**os.environ, "DATABASE_URL": os.environ["BBBC_TEST_DATABASE_URL"]},
    )
    assert saida.returncode == 0, saida.stdout + saida.stderr
    assert entrar(client, casa["email"], "senha-vinda-do-cano").status_code == 200


def test_o_carriage_return_do_powershell_nao_vira_parte_da_senha(client, casa):
    """O PowerShell termina linha com \r\n. Um \r invisivel grudado no fim
    gravaria uma senha que ninguem conseguiria digitar depois."""
    import os
    import subprocess
    import sys

    subprocess.run(
        [sys.executable, "-m", "app.cli", "trocar-senha",
         "--email", casa["email"], "--senha-de-stdin"],
        input="senha-do-windows\r\n",
        capture_output=True,
        text=True,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        env={**os.environ, "DATABASE_URL": os.environ["BBBC_TEST_DATABASE_URL"]},
    )
    assert entrar(client, casa["email"], "senha-do-windows").status_code == 200
