"""Utilitarios de linha de comando.

    python -m app.cli migrate
    python -m app.cli seed-family --name "Familia Ferrari" \
        --titular "Felipe" --titular-email felipe@exemplo.com \
        --conjuge "Clarissa" --conjuge-email clarissa@exemplo.com \
        --dependente "Filha 1" --dependente "Filha 2"
"""

from __future__ import annotations

import argparse
import pathlib
import sys
from uuid import UUID

from sqlalchemy import text

from app.core.security import hash_password
from app.db.session import SessionLocal, engine

MIGRATIONS_DIR = pathlib.Path(__file__).resolve().parent.parent / "db" / "migrations"


def migrate() -> None:
    """Aplica as migrations em ordem. Substituir por Alembic quando o schema
    comecar a evoluir com dados em producao."""
    with engine.begin() as conn:
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            print(f"aplicando {path.name}")
            conn.execute(text(path.read_text()))


def count_families() -> int:
    """Quantas familias ja existem. Usado pelo script de instalacao para nao
    recriar tudo a cada vez que o usuario abre o programa."""
    with SessionLocal() as db:
        return int(db.execute(text("SELECT count(*) FROM families")).scalar_one())


def status() -> dict:
    """Resumo do estado do sistema, em linguagem de gente."""
    with SessionLocal() as db:
        familias = int(db.execute(text("SELECT count(*) FROM families")).scalar_one())
        membros = int(
            db.execute(
                text("SELECT count(*) FROM members WHERE password_hash IS NOT NULL")
            ).scalar_one()
        )
        contas = int(db.execute(text("SELECT count(*) FROM accounts")).scalar_one())
        lancamentos = int(
            db.execute(text("SELECT count(*) FROM transactions")).scalar_one()
        )
        emails = [
            row[0]
            for row in db.execute(
                text("SELECT email FROM members WHERE password_hash IS NOT NULL ORDER BY role")
            )
        ]
    return {
        "familias": familias,
        "logins": membros,
        "contas": contas,
        "lancamentos": lancamentos,
        "emails": emails,
    }


def read_passwords(stream: object) -> tuple[str, str | None]:
    """Le as senhas da entrada padrao: primeira linha titular, segunda conjuge.

    Usa splitlines() e nao split("\n") de proposito: o PowerShell termina as
    linhas com \r\n, e um \r invisivel grudado no fim viraria parte da senha -
    o usuario cadastraria uma senha e digitaria outra para sempre.
    """
    linhas = stream.read().splitlines()
    titular = linhas[0] if linhas else ""
    conjuge = linhas[1] if len(linhas) > 1 and linhas[1] else None
    return titular, conjuge


def needs_setup() -> int:
    """Codigo de saida para os scripts de instalacao decidirem o que fazer.

    0 = precisa cadastrar, 1 = ja existe, 2 = nao consegui falar com o banco.
    E um numero, e nao texto: analisar a saida de `status` quebraria com
    qualquer mudanca de mensagem, e um erro de conexao seria lido como
    "ja existe" - justamente o contrario do que deve acontecer.
    """
    try:
        return 0 if count_families() == 0 else 1
    except Exception:
        return 2


def seed_family(
    name: str,
    titular: str,
    titular_email: str,
    titular_password: str,
    conjuge: str | None,
    conjuge_email: str | None,
    conjuge_password: str | None,
    dependentes: list[str],
    skip_if_exists: bool = False,
) -> UUID | None:
    """Cria a familia, os membros e clona o catalogo global de categorias.

    Com `skip_if_exists`, nao faz nada se ja houver familia cadastrada - e o que
    permite o script de instalacao ser executado quantas vezes for preciso.
    """
    if skip_if_exists and count_families() > 0:
        return None
    with SessionLocal.begin() as db:
        family_id = db.execute(
            text("INSERT INTO families (name) VALUES (:name) RETURNING id"), {"name": name}
        ).scalar_one()

        titular_id = db.execute(
            text(
                """
                INSERT INTO members (family_id, full_name, role, email, password_hash)
                VALUES (:family_id, :name, 'TITULAR', :email, :pwd)
                RETURNING id
                """
            ),
            {
                "family_id": family_id,
                "name": titular,
                "email": titular_email.lower(),
                "pwd": hash_password(titular_password),
            },
        ).scalar_one()

        if conjuge and conjuge_email and conjuge_password:
            db.execute(
                text(
                    """
                    INSERT INTO members (family_id, full_name, role, email, password_hash)
                    VALUES (:family_id, :name, 'CONJUGE', :email, :pwd)
                    """
                ),
                {
                    "family_id": family_id,
                    "name": conjuge,
                    "email": conjuge_email.lower(),
                    "pwd": hash_password(conjuge_password),
                },
            )

        for dependente in dependentes:
            db.execute(
                text(
                    """
                    INSERT INTO members
                        (family_id, full_name, role, is_ir_dependent, ir_dependent_of)
                    VALUES (:family_id, :name, 'DEPENDENTE', true, :titular)
                    """
                ),
                {"family_id": family_id, "name": dependente, "titular": titular_id},
            )

        clone_catalog(db, family_id)
        seed_default_rules(db, family_id)
        return family_id


def seed_default_rules(db, family_id: UUID) -> int:  # noqa: ANN001 - Session
    """Cria as regras de fornecedor do catalogo para a familia.

    Ficam com prioridade pior que a das regras aprendidas, entao a primeira
    correcao que o usuario fizer passa a mandar sobre o padrao.
    """
    from app.services.default_rules import (
        CATALOG_RULE_CONFIDENCE,
        CATALOG_RULE_PRIORITY,
        DEFAULT_MERCHANT_RULES,
    )

    caminhos = {
        row[0]: row[1]
        for row in db.execute(
            text("SELECT path::text, id FROM categories WHERE family_id = :f"),
            {"f": family_id},
        )
    }

    criadas = 0
    for padrao, caminho in DEFAULT_MERCHANT_RULES:
        categoria = caminhos.get(caminho)
        if categoria is None:
            continue
        db.execute(
            text(
                """
                INSERT INTO categorization_rules
                    (family_id, match_type, pattern, category_id, priority,
                     confidence, is_learned)
                VALUES (:family_id, 'CONTEM', :pattern, :category_id, :priority,
                        :confidence, false)
                """
            ),
            {
                "family_id": family_id,
                "pattern": padrao,
                "category_id": categoria,
                "priority": CATALOG_RULE_PRIORITY,
                "confidence": CATALOG_RULE_CONFIDENCE,
            },
        )
        criadas += 1
    return criadas


def clone_catalog(db, family_id: UUID) -> int:  # noqa: ANN001 - Session
    """Copia o catalogo global (family_id NULL) para a familia.

    A copia entra com o `path` pronto e o parent_id e amarrado depois, pelo
    proprio caminho materializado - por isso o trigger aceita path explicito.
    """
    inserted = db.execute(
        text(
            """
            INSERT INTO categories (family_id, slug, name, kind, path, income_nature,
                                    expense_nature, ir_treatment, ir_deduction_type,
                                    requires_note, counts_as_expense, icon, color,
                                    is_system, sort_order)
            SELECT :family_id, slug, name, kind, path, income_nature, expense_nature,
                   ir_treatment, ir_deduction_type, requires_note, counts_as_expense,
                   icon, color, is_system, sort_order
              FROM categories
             WHERE family_id IS NULL
            """
        ),
        {"family_id": family_id},
    ).rowcount

    db.execute(
        text(
            """
            UPDATE categories c
               SET parent_id = p.id
              FROM categories p
             WHERE c.family_id = :family_id
               AND p.family_id = :family_id
               AND nlevel(c.path) > 1
               AND p.path = subpath(c.path, 0, nlevel(c.path) - 1)
            """
        ),
        {"family_id": family_id},
    )
    return inserted


def reset_categories(family_id: UUID | None = None) -> tuple[int, int]:
    """Reaplica o catalogo atual na familia, com as regras de fornecedor.

    Recusa se ja houver lancamento apontando para as categorias existentes -
    apagar categoria com historico em cima transformaria gasto classificado em
    gasto solto, e o estrago so apareceria no fechamento do mes.
    """
    with SessionLocal.begin() as db:
        if family_id is None:
            family_id = db.execute(
                text("SELECT id FROM families ORDER BY created_at LIMIT 1")
            ).scalar_one_or_none()
            if family_id is None:
                raise RuntimeError("nenhuma familia cadastrada")

        em_uso = db.execute(
            text(
                """
                SELECT count(*) FROM transactions t
                  JOIN categories c ON c.id = t.category_id
                 WHERE c.family_id = :f
                """
            ),
            {"f": family_id},
        ).scalar_one()
        if em_uso:
            raise RuntimeError(
                f"{em_uso} lancamentos ja usam as categorias atuais. "
                "Recategorize-os antes, ou crie as novas categorias pelo app."
            )

        db.execute(
            text("DELETE FROM categorization_rules WHERE family_id = :f"),
            {"f": family_id},
        )
        db.execute(text("DELETE FROM categories WHERE family_id = :f"), {"f": family_id})
        categorias = clone_catalog(db, family_id)
        regras = seed_default_rules(db, family_id)
        return categorias, regras


def rodar_avisos() -> dict:
    """Tarefa diaria: recalcula os avisos e envia a fila.

    E um comando e nao um processo em segundo plano de proposito: um sistema
    que roda na maquina de casa nao pode contar com estar sempre ligado. Quem
    decide a frequencia e o agendador do sistema operacional - ver
    docs/notificacoes.md.
    """
    from app.services.vigilancia_repository import (
        despachar_pendentes,
        gerar_avisos,
        gravar_avisos,
    )

    resultado = {"familias": 0, "avisos_novos": 0}
    with SessionLocal.begin() as db:
        familias = [
            linha[0] for linha in db.execute(text("SELECT id FROM families"))
        ]
        for family_id in familias:
            avisos = gerar_avisos(db, family_id)
            criados = gravar_avisos(db, family_id, avisos)
            resultado["familias"] += 1
            resultado["avisos_novos"] += len(criados)

        resultado["envio"] = despachar_pendentes(db)
    return resultado


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bbbc")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("migrate", help="aplica as migrations SQL")

    seed = sub.add_parser("seed-family", help="cria a familia e clona o catalogo")
    seed.add_argument("--name", required=True)
    seed.add_argument("--titular", required=True)
    seed.add_argument("--titular-email", required=True)
    seed.add_argument("--titular-password")
    seed.add_argument("--conjuge")
    seed.add_argument("--conjuge-email")
    seed.add_argument("--conjuge-password")
    seed.add_argument(
        "--passwords-from-stdin",
        action="store_true",
        help=(
            "le as senhas de duas linhas na entrada padrao (titular, conjuge). "
            "Evita que senha com aspas ou acento quebre ao passar pela linha de "
            "comando do Windows ou do Mac."
        ),
    )
    seed.add_argument("--dependente", action="append", default=[])
    seed.add_argument(
        "--skip-if-exists",
        action="store_true",
        help="nao faz nada se ja existir familia cadastrada",
    )

    sub.add_parser("status", help="mostra o que ja existe no sistema")
    reset = sub.add_parser(
        "reset-categories",
        help="reaplica o catalogo de categorias e as regras na familia",
    )
    reset.add_argument("--family", help="id da familia (padrao: a primeira)")

    sub.add_parser(
        "run-alerts",
        help="recalcula os avisos e envia as notificacoes pendentes",
    )

    sub.add_parser(
        "needs-setup",
        help="codigo de saida: 0 precisa cadastrar, 1 ja existe, 2 sem banco",
    )

    args = parser.parse_args(argv)
    if args.command == "migrate":
        migrate()
        print("migrations aplicadas")
        return 0

    if args.command == "run-alerts":
        resultado = rodar_avisos()
        envio = resultado["envio"]
        print(
            f"{resultado['familias']} familia(s), "
            f"{resultado['avisos_novos']} aviso(s) novo(s)"
        )
        print(
            f"envio: {envio['enviados']} enviados, {envio['falhas']} falhas, "
            f"{envio['sem_configuracao']} sem configuracao"
        )
        return 0

    if args.command == "needs-setup":
        return needs_setup()

    if args.command == "reset-categories":
        try:
            categorias, regras = reset_categories(
                UUID(args.family) if args.family else None
            )
        except RuntimeError as exc:
            print(f"nada foi alterado: {exc}")
            return 1
        print(f"{categorias} categorias e {regras} regras aplicadas")
        return 0

    if args.command == "status":
        info = status()
        print(f"familias:    {info['familias']}")
        print(f"logins:      {info['logins']}")
        print(f"contas:      {info['contas']}")
        print(f"lancamentos: {info['lancamentos']}")
        for email in info["emails"]:
            print(f"  - {email}")
        return 0

    titular_password = args.titular_password
    conjuge_password = args.conjuge_password
    if args.passwords_from_stdin:
        titular_password, conjuge_password = read_passwords(sys.stdin)
    if not titular_password:
        parser.error("informe --titular-password ou --passwords-from-stdin")

    family_id = seed_family(
        args.name,
        args.titular,
        args.titular_email,
        titular_password,
        args.conjuge,
        args.conjuge_email,
        conjuge_password,
        args.dependente,
        skip_if_exists=args.skip_if_exists,
    )
    if family_id is None:
        print("ja existe familia cadastrada; nada a fazer")
    else:
        print(f"familia criada: {family_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
