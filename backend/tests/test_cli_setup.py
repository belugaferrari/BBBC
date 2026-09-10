"""Leitura das senhas pela entrada padrao.

As senhas nao passam pela linha de comando de proposito: aspas, cifrao e acento
quebrariam ao atravessar o shell - e no Windows quebrariam de um jeito
silencioso, cadastrando uma senha diferente da digitada.
"""

import io

import pytest

from app.cli import read_passwords


def test_duas_senhas_em_linhas_separadas():
    assert read_passwords(io.StringIO("primeira\nsegunda\n")) == ("primeira", "segunda")


def test_quebra_de_linha_do_windows_nao_vira_parte_da_senha():
    """O PowerShell manda \\r\\n. Um \\r invisivel no fim trancaria o usuario."""
    titular, conjuge = read_passwords(io.StringIO("minha-senha\r\noutra-senha\r\n"))
    assert titular == "minha-senha"
    assert conjuge == "outra-senha"
    assert "\r" not in titular


@pytest.mark.parametrize(
    "senha",
    [
        'Se"nha-com-aspas',
        "Se'nha-com-apostrofo",
        "Senha$com&simbolos",
        "senha-com-acento-çãé",
        "senha com espaços",
        "S3nh@!#%*()[]{}",
        "`backtick`-e-|barra",
    ],
)
def test_senha_com_caractere_dificil_sobrevive(senha):
    titular, _ = read_passwords(io.StringIO(f"{senha}\nsegunda\n"))
    assert titular == senha


def test_so_uma_senha_deixa_o_conjuge_vazio():
    assert read_passwords(io.StringIO("unica\n")) == ("unica", None)


def test_segunda_linha_em_branco_nao_vira_senha_vazia():
    """Sem isto, a Clarissa seria cadastrada com senha vazia."""
    assert read_passwords(io.StringIO("unica\n\n")) == ("unica", None)


def test_entrada_vazia_nao_estoura():
    assert read_passwords(io.StringIO("")) == ("", None)
