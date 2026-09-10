"""Le os fatos do banco, gera os avisos e enfileira o envio."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.vigilancia import (
    Aviso,
    ContaAVencer,
    ContaEsperada,
    PontosAExpirar,
    avisos_de_extrato,
    avisos_de_pontos,
    avisos_de_vencimento,
    checklist_extratos,
    proximo_vencimento,
)


def montar_checklist(db: Session, family_id: UUID, month: date) -> dict:
    """Contas das quais se espera extrato, e quais ja mandaram o do mes."""
    linhas = db.execute(
        text(
            """
            SELECT a.id, a.name, i.name AS instituicao, a.statement_expected_day,
                   (SELECT max(s.confirmed_at::date)
                      FROM statement_imports s
                     WHERE s.account_id = a.id
                       AND s.status = 'CONFIRMADO'
                       AND s.period_end >= date_trunc('month', CAST(:month AS date))
                       AND s.period_start < date_trunc('month', CAST(:month AS date))
                                            + interval '1 month'
                   ) AS recebido_em
              FROM accounts a
              LEFT JOIN institutions i ON i.id = a.institution_id
             WHERE a.family_id = :family_id
               AND a.expects_statement
               AND a.is_archived = false
             ORDER BY a.name
            """
        ),
        {"family_id": family_id, "month": month},
    ).mappings().all()

    contas = [
        ContaEsperada(
            account_id=str(linha["id"]),
            name=linha["name"],
            institution=linha["instituicao"],
            expected_day=linha["statement_expected_day"],
            received_at=linha["recebido_em"],
        )
        for linha in linhas
    ]
    return checklist_extratos(contas, month)


def contas_a_vencer(db: Session, family_id: UUID, hoje: date) -> list[ContaAVencer]:
    """Contas recorrentes marcadas como conta a pagar, mais a fatura dos cartoes."""
    contas: list[ContaAVencer] = []

    for linha in db.execute(
        text(
            """
            SELECT r.id, r.description, r.amount, r.next_run_on, r.remind_days_before,
                   a.name AS conta
              FROM recurring_transactions r
              LEFT JOIN accounts a ON a.id = r.account_id
             WHERE r.family_id = :family_id
               AND r.is_active
               AND r.is_bill
               AND r.direction = 'SAIDA'
            """
        ),
        {"family_id": family_id},
    ).mappings():
        contas.append(
            ContaAVencer(
                id=str(linha["id"]),
                description=linha["description"],
                amount=Decimal(linha["amount"]),
                due_on=linha["next_run_on"],
                remind_days_before=linha["remind_days_before"],
                account_name=linha["conta"],
            )
        )

    # Fatura de cartao: o vencimento e um dia fixo do mes, e o valor devido e o
    # proprio saldo negativo da conta do cartao.
    for linha in db.execute(
        text(
            """
            SELECT a.id, a.name, a.current_balance, a.statement_due_day
              FROM accounts a
             WHERE a.family_id = :family_id
               AND a.type = 'CARTAO_CREDITO'
               AND a.is_archived = false
               AND a.statement_due_day IS NOT NULL
            """
        ),
        {"family_id": family_id},
    ).mappings():
        devido = -Decimal(linha["current_balance"])
        if devido <= 0:
            continue
        contas.append(
            ContaAVencer(
                id=f"fatura:{linha['id']}",
                description=f"Fatura {linha['name']}",
                amount=devido,
                due_on=proximo_vencimento(linha["statement_due_day"], hoje),
                # fatura precisa de mais antecedencia: o dinheiro para paga-la
                # costuma vir de outro lugar
                remind_days_before=7,
                account_name=linha["name"],
            )
        )

    return contas


def pontos_a_expirar(db: Session, family_id: UUID) -> list[PontosAExpirar]:
    return [
        PontosAExpirar(
            program_id=str(linha["id"]),
            name=linha["name"],
            points=Decimal(linha["expires_next_points"]),
            expires_on=linha["expires_next_on"],
            value_brl=(
                Decimal(linha["expires_next_points"]) * Decimal(linha["point_value_brl"])
                if linha["point_value_brl"] is not None
                else None
            ),
        )
        for linha in db.execute(
            text(
                """
                SELECT id, name, expires_next_on, expires_next_points, point_value_brl
                  FROM card_programs
                 WHERE family_id = :family_id
                   AND is_active
                   AND expires_next_on IS NOT NULL
                   AND COALESCE(expires_next_points, 0) > 0
                """
            ),
            {"family_id": family_id},
        ).mappings()
    ]


def gerar_avisos(db: Session, family_id: UUID, hoje: date | None = None) -> list[Aviso]:
    hoje = hoje or date.today()
    return [
        *avisos_de_extrato(montar_checklist(db, family_id, hoje)),
        *avisos_de_vencimento(contas_a_vencer(db, family_id, hoje), hoje),
        *avisos_de_pontos(pontos_a_expirar(db, family_id), hoje),
    ]


def gravar_avisos(db: Session, family_id: UUID, avisos: list[Aviso]) -> list[UUID]:
    """Grava os avisos novos e enfileira o envio para cada destino ativo.

    O indice unico em (family_id, dedupe_key) e o que impede o mesmo aviso de
    nascer de novo a cada execucao: sem ele, uma conta a vencer em tres dias
    viraria tres avisos identicos.
    """
    criados: list[UUID] = []

    for aviso in avisos:
        alert_id = db.execute(
            text(
                """
                INSERT INTO alerts (family_id, kind, severity, title, body,
                                    payload, dedupe_key, due_on, created_at)
                VALUES (:family_id, :kind, CAST(:severity AS alert_severity), :title,
                        :body, CAST(:payload AS jsonb), :dedupe_key, :due_on, now())
                ON CONFLICT (family_id, dedupe_key) WHERE dedupe_key IS NOT NULL
                DO NOTHING
                RETURNING id
                """
            ),
            {
                "family_id": family_id,
                "kind": aviso.kind,
                "severity": aviso.severity,
                "title": aviso.title,
                "body": aviso.body,
                "payload": __import__("json").dumps(aviso.payload or {}),
                "dedupe_key": aviso.dedupe_key,
                "due_on": aviso.due_on,
            },
        ).scalar_one_or_none()

        if alert_id is None:
            continue          # ja existia; nada a fazer
        criados.append(alert_id)

        db.execute(
            text(
                """
                INSERT INTO notification_deliveries (alert_id, target_id, created_at)
                SELECT :alert_id, t.id, now()
                  FROM notification_targets t
                 WHERE t.family_id = :family_id
                   AND t.is_active
                ON CONFLICT (alert_id, target_id) DO NOTHING
                """
            ),
            {"alert_id": alert_id, "family_id": family_id},
        )

    return criados


def despachar_pendentes(db: Session, limite: int = 100) -> dict:
    """Envia o que esta na fila. Idempotente: so pega o que esta PENDENTE."""
    from app.services.notifier import Mensagem, NotificadorIndisponivel, enviar

    pendentes = db.execute(
        text(
            """
            SELECT d.id, d.attempts, t.channel::text AS canal, t.address,
                   a.title, a.body, a.severity::text AS severity, a.kind
              FROM notification_deliveries d
              JOIN notification_targets t ON t.id = d.target_id
              JOIN alerts a ON a.id = d.alert_id
             WHERE d.status = 'PENDENTE'
               AND t.is_active
             ORDER BY d.created_at
             LIMIT :limite
            """
        ),
        {"limite": limite},
    ).mappings().all()

    enviados = falhas = indisponiveis = 0

    for item in pendentes:
        mensagem = Mensagem(
            title=item["title"],
            body=item["body"] or "",
            severity=item["severity"],
            data={"kind": item["kind"]},
        )
        try:
            resultado = enviar(item["canal"], item["address"], mensagem)
        except NotificadorIndisponivel as exc:
            # falta de credencial nao e falha de envio: a fila espera a
            # configuracao, em vez de queimar tentativas
            indisponiveis += 1
            db.execute(
                text("UPDATE notification_deliveries SET error = :erro WHERE id = :id"),
                {"erro": str(exc), "id": item["id"]},
            )
            continue

        if resultado.ok:
            enviados += 1
            db.execute(
                text(
                    """
                    UPDATE notification_deliveries
                       SET status = 'ENVIADO', sent_at = :agora,
                           attempts = attempts + 1, error = NULL
                     WHERE id = :id
                    """
                ),
                {"agora": datetime.now(UTC), "id": item["id"]},
            )
            db.execute(
                text(
                    "UPDATE notification_targets SET last_used_at = :agora"
                    " WHERE id = (SELECT target_id FROM notification_deliveries"
                    " WHERE id = :id)"
                ),
                {"agora": datetime.now(UTC), "id": item["id"]},
            )
        else:
            falhas += 1
            tentativas = item["attempts"] + 1
            # tres tentativas e o suficiente para distinguir queda de rede de
            # endereco invalido; alem disso e insistir em erro permanente
            db.execute(
                text(
                    """
                    UPDATE notification_deliveries
                       SET status = CASE WHEN :tentativas >= 3 THEN 'ERRO' ELSE 'PENDENTE' END,
                           attempts = :tentativas, error = :erro
                     WHERE id = :id
                    """
                ),
                {"tentativas": tentativas, "erro": resultado.error, "id": item["id"]},
            )

    return {
        "pendentes": len(pendentes),
        "enviados": enviados,
        "falhas": falhas,
        "sem_configuracao": indisponiveis,
    }
