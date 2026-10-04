"""Ler arquivo sem dizer a codificacao, e o que isso derrubou.

A atualizacao dele parou no meio, com o banco ja de pe e as tabelas pela metade:

    5. Criando as tabelas
    aplicando 0014_nomes_com_acento.sql
    UnicodeDecodeError: 'charmap' codec can't decode byte 0x81 in position 1715

O arquivo estava certo - UTF-8, como todo o repositorio. Quem leu e que supos a
lingua errada: sem `encoding`, o Python usa a codificacao do SISTEMA, que no
Windows em portugues e a cp1252. Em Linux e Mac o padrao e UTF-8, entao o erro
nao aparece em nenhuma maquina de desenvolvimento - so na dele.

Enquanto as migrations foram ASCII puro, ninguem viu. A primeira que trouxe
acento para os nomes das categorias ("Doações recebidas", "Saúde") achou o
buraco. O teste simula a situacao rodando o leitor com o sistema em ASCII, que e
o mesmo tipo de erro por outro caminho.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
MIGRATIONS = RAIZ / "db" / "migrations"


def test_toda_migration_e_utf8_valido():
    """O repositorio e UTF-8. Se uma migration nao for, o erro aparece aqui e
    nao na maquina de quem esta atualizando."""
    for arquivo in sorted(MIGRATIONS.glob("*.sql")):
        arquivo.read_bytes().decode("utf-8")  # levanta se nao for


def test_alguma_migration_tem_acento():
    """O teste de baixo so vale enquanto existir acento para quebrar.

    Se um dia todas as migrations voltarem a ser ASCII, este teste falha e avisa
    que o outro virou enfeite - em vez de deixa-lo passando sem testar nada.
    """
    com_acento = [
        arquivo.name
        for arquivo in MIGRATIONS.glob("*.sql")
        if any(byte > 127 for byte in arquivo.read_bytes())
    ]
    assert com_acento, "nenhuma migration tem caractere fora do ASCII"


def test_a_migration_e_lida_mesmo_com_o_sistema_em_outra_lingua():
    """Roda o leitor de verdade num processo cujo sistema NAO e UTF-8.

    `LC_ALL=C` com a coercao do PEP 538 desligada deixa o Python em ASCII puro -
    o mesmo tipo de armadilha que a cp1252 do Windows dele, reproduzivel aqui.
    Sem o `encoding="utf-8"` no leitor, este teste falha exatamente como a tela
    dele falhou.
    """
    ambiente = {
        **os.environ,
        "LC_ALL": "C",
        "LANG": "C",
        "PYTHONCOERCECLOCALE": "0",
        "PYTHONUTF8": "0",
        "DATABASE_URL": os.environ.get(
            "DATABASE_URL", "postgresql+psycopg://ninguem@localhost/nada"
        ),
    }
    codigo = (
        "import locale, pathlib, sys;"
        "from app.cli import ler_migration;"
        "alvo = sorted(pathlib.Path('db/migrations').glob('*.sql'));"
        "comacento = [p for p in alvo if any(b > 127 for b in p.read_bytes())];"
        "texto = ''.join(ler_migration(p) for p in comacento);"
        "print(locale.getencoding(), len(comacento), len(texto))"
    )
    resultado = subprocess.run(
        [sys.executable, "-c", codigo],
        cwd=RAIZ,
        env=ambiente,
        capture_output=True,
        text=True,
    )
    assert resultado.returncode == 0, resultado.stderr
    encoding, quantas, tamanho = resultado.stdout.split()
    # o processo filho estava mesmo com o sistema em outra lingua
    assert "UTF-8" not in encoding.upper()
    assert int(quantas) > 0 and int(tamanho) > 0


def test_arquivo_lido_sem_dizer_a_codificacao_nao_volta_a_existir():
    """A regra, e nao so o caso.

    `read_text()` e `open()` sem `encoding` funcionam na maquina de quem escreve
    e quebram na de quem usa - e quebram tarde, no meio de uma atualizacao. Em
    vez de confiar na lembranca, o teste varre o codigo.
    """
    suspeitas: list[str] = []
    # open( com modo binario nao tem encoding, e esta certo assim
    chamada = re.compile(r"(?<![\w.])(open|read_text|write_text)\(([^)]*)\)")
    for arquivo in sorted((RAIZ / "app").rglob("*.py")):
        for numero, linha in enumerate(
            arquivo.read_text(encoding="utf-8").splitlines(), start=1
        ):
            for nome, argumentos in chamada.findall(linha):
                if "encoding=" in argumentos or '"rb"' in argumentos or "'rb'" in argumentos:
                    continue
                if "wb" in argumentos:
                    continue
                suspeitas.append(f"{arquivo.relative_to(RAIZ)}:{numero}: {nome}({argumentos})")

    assert not suspeitas, (
        "leitura de arquivo sem dizer a codificacao - no Windows em portugues "
        "isso le em cp1252 e quebra com acento:\n  " + "\n  ".join(suspeitas)
    )
