"""A imagem Docker precisa instalar o que o pyproject declara.

Este teste existe por causa de uma falha real: o Dockerfile repetia a lista de
dependencias na mao. O pyproject ganhou python-multipart e pypdf, o Dockerfile
nao, e a API passou a morrer na importacao - o FastAPI exige python-multipart
para receber arquivo enviado. Nenhum outro teste percebeu, porque todos rodam
num ambiente onde as dependencias ja estao instaladas.

A protecao aqui e estrutural: nao basta acrescentar os pacotes que faltavam,
porque o proximo a ser adicionado quebraria de novo. O Dockerfile tem que ler o
pyproject.
"""

import re
import tomllib
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DOCKERFILE = RAIZ / "Dockerfile"
PYPROJECT = RAIZ / "pyproject.toml"


def _linhas_de_instalacao() -> list[str]:
    """As linhas do Dockerfile que instalam algo, sem comentarios.

    Junta as continuacoes de linha antes de procurar - um "pip install" quebrado
    com "\\" em varias linhas passaria despercebido - e descarta comentarios,
    senao a propria explicacao acima do RUN contaria como instalacao.
    """
    texto = DOCKERFILE.read_text(encoding="utf-8").replace("\\\n", " ")
    linhas = [
        linha for linha in texto.splitlines() if not linha.lstrip().startswith("#")
    ]
    return [linha for linha in linhas if "pip install" in linha]


def test_dockerfile_instala_a_partir_do_pyproject():
    instalacoes = _linhas_de_instalacao()
    assert instalacoes, "o Dockerfile nao instala dependencia nenhuma"
    assert all(
        "requirements.txt" in linha or "pyproject" in linha for linha in instalacoes
    ), (
        "alguma instalacao do Dockerfile nao vem do pyproject.toml:\n"
        + "\n".join(instalacoes)
    )


def test_dockerfile_nao_repete_a_lista_de_pacotes():
    # so as linhas de instalacao: o CMD final cita "uvicorn" para executa-lo,
    # o que nao e fixar versao de dependencia
    conteudo = "\n".join(_linhas_de_instalacao())
    deps = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]["dependencies"]

    repetidos = []
    for dep in deps:
        # "fastapi>=0.115" -> "fastapi"; "psycopg[binary]>=3.2" -> "psycopg"
        nome = re.split(r"[\[><=!~ ]", dep, maxsplit=1)[0]
        if re.search(rf'"{re.escape(nome)}[\[><=!~"]', conteudo):
            repetidos.append(nome)

    assert not repetidos, (
        "o Dockerfile voltou a fixar pacotes na mao: "
        + ", ".join(repetidos)
        + ". Declare no pyproject.toml; a imagem le de la."
    )


def test_pyproject_declara_o_que_o_upload_de_extrato_exige():
    deps = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]["dependencies"]
    nomes = {re.split(r"[\[><=!~ ]", d, maxsplit=1)[0] for d in deps}

    # python-multipart: exigido pelo FastAPI em POST /imports (UploadFile).
    # Sem ele o app nem importa - o erro aparece no boot, nao no endpoint.
    assert "python-multipart" in nomes
    # pypdf: usado na leitura de extrato em PDF.
    assert "pypdf" in nomes
