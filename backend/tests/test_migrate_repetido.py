"""Ligar o sistema duas vezes tem que funcionar.

Este teste existe por causa de uma falha real, e ela so aparecia na segunda
partida: `migrate` reaplicava todas as migrations toda vez, porque nao havia
registro do que ja tinha rodado. A primeira instalacao ia bem; a segunda morria
em 0001, no CREATE TRIGGER, que o Postgres nao aceita repetir.

Nenhum teste pegou isso porque o banco de teste sempre nascia limpo - o unico
caso que nao reproduz o problema. Por isso aqui o banco e proprio e descartavel:
so num banco que sobrevive entre chamadas da para ver a segunda partida.
"""

from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, text

pytestmark = pytest.mark.skipif(
    not os.getenv("BBBC_TEST_DATABASE_URL"),
    reason="defina BBBC_TEST_DATABASE_URL para rodar a integracao",
)


@pytest.fixture
def banco_proprio(monkeypatch):
    """Um banco vazio so para este teste, devolvido ao fim.

    Os outros testes de integracao compartilham o banco e esperam o schema de
    pe; derrubar o schema deles pelo caminho faria este teste passar as custas
    dos vizinhos.
    """
    from app import cli

    url = os.environ["BBBC_TEST_DATABASE_URL"]
    nome = f"bbbc_mig_{uuid.uuid4().hex[:12]}"
    base = url.rsplit("/", 1)[0]

    # CREATE/DROP DATABASE nao roda dentro de transacao
    admin = create_engine(url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{nome}"'))

    temporario = create_engine(f"{base}/{nome}")
    # `migrate` usa o engine global do modulo; sem trocar aqui ele escreveria no
    # banco compartilhado e o teste nao testaria nada.
    monkeypatch.setattr(cli, "engine", temporario)
    try:
        yield temporario
    finally:
        temporario.dispose()
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{nome}" WITH (FORCE)'))
        admin.dispose()


def _aplicadas(conn) -> set[str]:
    return {linha[0] for linha in conn.execute(text("SELECT filename FROM schema_migrations"))}


def _no_disco() -> set[str]:
    from app.cli import MIGRATIONS_DIR

    return {p.name for p in MIGRATIONS_DIR.glob("*.sql")}


def test_migrate_duas_vezes_seguidas_nao_quebra(banco_proprio):
    from app.cli import migrate

    migrate()
    migrate()  # era aqui que estourava: CREATE TRIGGER ja existente
    migrate()

    with banco_proprio.begin() as conn:
        assert _aplicadas(conn) == _no_disco()


def test_registra_cada_migration_uma_unica_vez(banco_proprio):
    from app.cli import migrate

    migrate()
    migrate()

    with banco_proprio.begin() as conn:
        total = conn.execute(text("SELECT count(*) FROM schema_migrations")).scalar()
    assert total == len(_no_disco())


def test_banco_da_versao_antiga_e_adotado_sem_reexecutar(banco_proprio):
    """O caso do Felipe: schema de pe, criado antes de existir registro.

    Reproduz o estado exato - todas as migrations aplicadas, nenhuma tabela de
    registro - e verifica que `migrate` reconhece em vez de tentar recriar.
    """
    from app.cli import migrate

    migrate()
    with banco_proprio.begin() as conn:
        conn.execute(text("DROP TABLE schema_migrations"))
        categorias_antes = conn.execute(text("SELECT count(*) FROM categories")).scalar()

    migrate()  # sem a adocao, isto reexecutaria 0001 e falharia

    with banco_proprio.begin() as conn:
        assert _aplicadas(conn) == _no_disco()
        # o catalogo continua de pe, e sem duplicar
        assert conn.execute(text("SELECT count(*) FROM categories")).scalar() == categorias_antes


def test_banco_vazio_nao_e_confundido_com_banco_antigo(banco_proprio):
    """Sem schema nenhum, a adocao nao pode disparar: as migrations tem que rodar."""
    from app.cli import migrate

    migrate()

    with banco_proprio.begin() as conn:
        assert conn.execute(text("SELECT count(*) FROM categories")).scalar() > 0


def test_lista_de_adocao_bate_com_as_migrations_que_existiam():
    """Guarda a lista fixa contra edicao distraida.

    Renomear uma dessas migrations sem ajustar a lista faria um banco antigo ser
    tratado como novo - e ele quebraria na reexecucao, que e o bug original.
    """
    from app.cli import MIGRATIONS_ANTES_DO_REGISTRO

    assert set(MIGRATIONS_ANTES_DO_REGISTRO) <= _no_disco()
