"""Monta os eventos da projecao a partir do banco."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from dateutil.rrule import rrulestr
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.enums import TxDirection
from app.services.forecast import (
    FlowKind,
    ForecastEvent,
    add_months,
    average_by_category,
    horizon,
    month_start,
    subtract_covered,
)
from app.services.money import ZERO, brl

# Quantos meses de historico alimentam a media por categoria. Tres equilibra:
# um mes so e refem de atipico, doze arrasta gasto que voce ja cortou.
HISTORY_MONTHS = 3


def _expand_recurring(
    rule_text: str, next_run: date, ends_on: date | None, until: date
) -> list[date]:
    """Datas de um lancamento recorrente dentro da janela.

    Se a regra for invalida (digitada a mao, por exemplo), cai para uma
    repeticao mensal a partir da proxima data - melhor projetar de forma
    aproximada do que sumir com uma despesa fixa da previsao.
    """
    limite = min(ends_on, until) if ends_on else until
    if next_run > limite:
        return []
    try:
        regra = rrulestr(rule_text, dtstart=next_run)
        return [d.date() for d in regra.between(next_run, limite, inc=True)]
    except (ValueError, TypeError):
        datas, cursor = [], next_run
        while cursor <= limite:
            datas.append(cursor)
            cursor = add_months(month_start(cursor), 1).replace(
                day=min(next_run.day, 28)
            )
        return datas


def build_events(
    db: Session, family_id: UUID, start: date, months: int, member_id: UUID | None
) -> tuple[list[ForecastEvent], dict]:
    """Devolve os eventos previstos e um resumo de como foram obtidos."""
    janela = horizon(start, months)
    fim = add_months(janela[-1], 1)
    eventos: list[ForecastEvent] = []

    escopo = (
        "AND (CAST(:member_id AS uuid) IS NULL "
        "OR t.owner_member_id = CAST(:member_id AS uuid))"
    )
    parametros = {"family_id": family_id, "member_id": member_id}

    # ---------------------------------------------------------------- FIXO --
    recorrentes = db.execute(
        text(
            """
            SELECT r.description, r.amount, r.direction::text AS direction,
                   r.rrule, r.next_run_on, r.ends_on,
                   c.path::text AS category_path, c.name AS category_name
              FROM recurring_transactions r
              LEFT JOIN categories c ON c.id = r.category_id
             WHERE r.family_id = :family_id
               AND r.is_active
               AND (CAST(:member_id AS uuid) IS NULL
                    OR r.owner_member_id = CAST(:member_id AS uuid))
            """
        ),
        parametros,
    ).mappings().all()

    coberto_por_fixo: dict[str, Decimal] = {}
    for linha in recorrentes:
        for quando in _expand_recurring(
            linha["rrule"], linha["next_run_on"], linha["ends_on"], fim
        ):
            if quando < janela[0]:
                continue
            eventos.append(
                ForecastEvent(
                    month=month_start(quando),
                    kind=FlowKind.FIXO,
                    direction=TxDirection(linha["direction"]),
                    amount=Decimal(linha["amount"]),
                    label=linha["description"],
                    category_path=linha["category_path"],
                    category_name=linha["category_name"],
                )
            )
            if linha["direction"] == "SAIDA" and linha["category_path"]:
                caminho = linha["category_path"]
                coberto_por_fixo[caminho] = (
                    coberto_por_fixo.get(caminho, ZERO) + Decimal(linha["amount"])
                )

    # ------------------------------------------------------------ ESPERADO --
    # Lancamentos que ja existem com data futura: parcelas de cartao, contas
    # agendadas, aportes programados.
    futuros = db.execute(
        text(
            f"""
            SELECT t.description, t.amount, t.direction::text AS direction,
                   t.booked_on, t.installment_no, t.installment_total,
                   c.path::text AS category_path, c.name AS category_name
              FROM transactions t
              LEFT JOIN categories c ON c.id = t.category_id
             WHERE t.family_id = :family_id
               AND t.direction <> 'TRANSFERENCIA'
               AND t.status IN ('PREVISTA', 'PENDENTE', 'EFETIVADA', 'CONCILIADA')
               AND t.booked_on >= :inicio
               AND t.booked_on < :fim
               {escopo}
            """
        ),
        {**parametros, "inicio": janela[0], "fim": fim},
    ).mappings().all()

    coberto_por_esperado: dict[str, Decimal] = {}
    for linha in futuros:
        rotulo = linha["description"]
        if linha["installment_no"] and linha["installment_total"]:
            rotulo = f"{rotulo} ({linha['installment_no']}/{linha['installment_total']})"
        eventos.append(
            ForecastEvent(
                month=month_start(linha["booked_on"]),
                kind=FlowKind.ESPERADO,
                direction=TxDirection(linha["direction"]),
                amount=Decimal(linha["amount"]),
                label=rotulo,
                category_path=linha["category_path"],
                category_name=linha["category_name"],
            )
        )
        if linha["direction"] == "SAIDA" and linha["category_path"]:
            caminho = linha["category_path"]
            coberto_por_esperado[caminho] = (
                coberto_por_esperado.get(caminho, ZERO) + Decimal(linha["amount"])
            )

    # ------------------------------------------------------------ ESTIMADO --
    inicio_historico = add_months(janela[0], -HISTORY_MONTHS)
    historico = db.execute(
        text(
            f"""
            SELECT date_trunc('month', t.booked_on)::date AS mes,
                   c.path::text AS category_path,
                   c.name       AS category_name,
                   SUM(t.amount) AS total
              FROM transactions t
              JOIN categories c ON c.id = t.category_id
             WHERE t.family_id = :family_id
               AND t.direction = 'SAIDA'
               AND t.status IN ('EFETIVADA', 'CONCILIADA')
               AND t.booked_on >= :inicio_historico
               AND t.booked_on < :inicio
               {escopo}
             GROUP BY 1, 2, 3
            """
        ),
        {**parametros, "inicio_historico": inicio_historico, "inicio": janela[0]},
    ).mappings().all()

    nomes = {
        linha["category_path"]: linha["category_name"] for linha in historico
    }
    medias = average_by_category(
        [(linha["mes"], linha["category_path"], Decimal(linha["total"])) for linha in historico],
        HISTORY_MONTHS,
    )
    # o mesmo gasto nao pode entrar como fixo e de novo como media historica
    cobertura = dict(coberto_por_fixo)
    for caminho, valor in coberto_por_esperado.items():
        cobertura[caminho] = cobertura.get(caminho, ZERO) + valor
    # a cobertura foi somada na janela inteira; a media e mensal
    cobertura_mensal = {k: brl(v / max(1, months)) for k, v in cobertura.items()}
    estimativas = subtract_covered(medias, cobertura_mensal)

    for mes in janela:
        for caminho, valor in estimativas.items():
            eventos.append(
                ForecastEvent(
                    month=mes,
                    kind=FlowKind.ESTIMADO,
                    direction=TxDirection.SAIDA,
                    amount=valor,
                    label=nomes.get(caminho, caminho),
                    category_path=caminho,
                    category_name=nomes.get(caminho),
                )
            )

    resumo = {
        "recurring_rules": len(recorrentes),
        "scheduled_transactions": len(futuros),
        "estimated_categories": len(estimativas),
        "history_months": HISTORY_MONTHS,
    }
    return eventos, resumo


def opening_balance(db: Session, family_id: UUID, member_id: UUID | None) -> Decimal:
    """Saldo disponivel hoje: contas liquidas menos a fatura em aberto."""
    total = db.execute(
        text(
            """
            SELECT COALESCE(SUM(
                       CASE WHEN a.type = 'CARTAO_CREDITO' THEN a.current_balance
                            WHEN a.type IN ('CONTA_CORRENTE','POUPANCA','DINHEIRO')
                                 THEN a.current_balance
                            ELSE 0 END), 0) AS saldo
              FROM accounts a
             WHERE a.family_id = :family_id
               AND a.is_archived = false
               AND (CAST(:member_id AS uuid) IS NULL
                    OR a.owner_member_id = CAST(:member_id AS uuid) OR a.is_shared)
            """
        ),
        {"family_id": family_id, "member_id": member_id},
    ).scalar_one()
    return brl(total or 0)
