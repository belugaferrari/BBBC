"""Consultas agregadas. SQL explicito onde o ORM atrapalharia a leitura."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.money import ZERO, brl
from app.services.sankey import FlowRow

_SCOPE_FILTER = (
    "AND (CAST(:member_id AS uuid) IS NULL "
    "OR t.owner_member_id = CAST(:member_id AS uuid))"
)


def consolidated_balances(db: Session, family_id: UUID, member_id: UUID | None) -> dict:
    rows = db.execute(
        text(
            """
            SELECT a.type::text AS type,
                   SUM(a.current_balance) AS total,
                   COUNT(*)               AS accounts
              FROM accounts a
             WHERE a.family_id = :family_id
               AND a.is_archived = false
               AND (CAST(:member_id AS uuid) IS NULL
                    OR a.owner_member_id = CAST(:member_id AS uuid) OR a.is_shared)
             GROUP BY a.type
            """
        ),
        {"family_id": family_id, "member_id": member_id},
    ).mappings().all()

    by_type = {r["type"]: brl(r["total"] or 0) for r in rows}
    liquid = sum(
        (v for k, v in by_type.items() if k in {"CONTA_CORRENTE", "POUPANCA", "DINHEIRO"}),
        ZERO,
    )
    card_debt = -by_type.get("CARTAO_CREDITO", ZERO)
    invested = by_type.get("INVESTIMENTO", ZERO)
    return {
        "by_type": by_type,
        "liquid": brl(liquid),
        "credit_card_debt": brl(card_debt),
        "invested": brl(invested),
        "net_worth": brl(liquid + invested - card_debt),
    }


def monthly_cashflow(
    db: Session, family_id: UUID, month: date, member_id: UUID | None
) -> dict:
    row = db.execute(
        text(
            f"""
            SELECT
              COALESCE(SUM(t.amount) FILTER (WHERE t.direction = 'ENTRADA'), 0) AS inflow,
              COALESCE(SUM(t.amount) FILTER (WHERE t.direction = 'SAIDA'),   0) AS outflow,
              COALESCE(SUM(t.amount) FILTER (
                  WHERE t.direction = 'SAIDA'
                    AND COALESCE(c.counts_as_expense, true) = false), 0)        AS patrimonio
              FROM transactions t
              LEFT JOIN categories c ON c.id = t.category_id
             WHERE t.family_id = :family_id
               AND t.status IN ('EFETIVADA', 'CONCILIADA')
               AND t.direction <> 'TRANSFERENCIA'
               AND date_trunc('month', t.booked_on) = date_trunc('month', CAST(:month AS date))
               {_SCOPE_FILTER}
            """
        ),
        {"family_id": family_id, "month": month, "member_id": member_id},
    ).mappings().one()

    inflow, outflow = brl(row["inflow"]), brl(row["outflow"])
    # Amortizacao e aporte saem da conta, mas nao sao consumo: sao divida
    # virando patrimonio e dinheiro mudando de bolso. Somados ao gasto, fariam
    # o mes parecer pior - e a taxa de poupanca, menor - justamente para quem
    # esta construindo patrimonio.
    patrimonio = brl(row["patrimonio"])
    consumo = brl(outflow - patrimonio)
    savings_rate = (inflow - consumo) / inflow if inflow else ZERO
    return {
        "month": month.replace(day=1),
        "inflow": inflow,
        "outflow": outflow,
        "consumo": consumo,
        "patrimonio": patrimonio,
        "net": brl(inflow - outflow),
        "savings_rate": Decimal(savings_rate).quantize(Decimal("0.0001")),
    }


def sankey_rows(db: Session, family_id: UUID, month: date, member_id: UUID | None) -> list[FlowRow]:
    """Fluxos do mes ja resolvidos ate o nivel 2 (grupo) e o nivel exibido."""
    rows = db.execute(
        text(
            f"""
            SELECT t.direction::text AS direction,
                   COALESCE(grp.name, 'Sem categoria')  AS grp,
                   COALESCE(c.name,   'Sem categoria')  AS category,
                   SUM(t.amount)                        AS amount
              FROM transactions t
              LEFT JOIN categories c   ON c.id = t.category_id
              LEFT JOIN categories grp ON grp.family_id IS NOT DISTINCT FROM c.family_id
                                      AND grp.path = subpath(c.path, 0, LEAST(2, nlevel(c.path)))
             WHERE t.family_id = :family_id
               AND t.status IN ('EFETIVADA', 'CONCILIADA')
               AND t.direction <> 'TRANSFERENCIA'
               AND date_trunc('month', t.booked_on) = date_trunc('month', CAST(:month AS date))
               {_SCOPE_FILTER}
             GROUP BY 1, 2, 3
            """
        ),
        {"family_id": family_id, "month": month, "member_id": member_id},
    ).mappings().all()

    return [
        FlowRow(
            direction=r["direction"],
            group=r["grp"],
            category=r["category"],
            amount=brl(r["amount"]),
        )
        for r in rows
    ]


def spend_by_budget_cap(db: Session, family_id: UUID, month: date) -> list[dict]:
    """Gasto realizado no mes para cada teto configurado.

    `includes_descendants` faz a soma descer a subarvore inteira via ltree.
    """
    rows = db.execute(
        text(
            """
            SELECT b.id            AS cap_id,
                   b.category_id,
                   c.name          AS category_name,
                   b.member_id,
                   b.amount        AS cap,
                   b.alert_at_pct,
                   COALESCE((
                       SELECT SUM(t.amount)
                         FROM transactions t
                         JOIN categories tc ON tc.id = t.category_id
                        WHERE t.family_id = b.family_id
                          AND t.direction = 'SAIDA'
                          AND t.status IN ('EFETIVADA', 'CONCILIADA')
                          AND date_trunc('month', t.booked_on)
                              = date_trunc('month', CAST(:month AS date))
                          AND (b.member_id IS NULL OR t.owner_member_id = b.member_id)
                          AND (CASE WHEN b.includes_descendants
                                    THEN tc.path <@ c.path
                                    ELSE tc.id = c.id END)
                   ), 0) AS spent
              FROM budget_caps b
              JOIN categories c ON c.id = b.category_id
             WHERE b.family_id = :family_id
               AND b.starts_on <= CAST(:month AS date)
               AND (b.ends_on IS NULL OR b.ends_on >= CAST(:month AS date))
            """
        ),
        {"family_id": family_id, "month": month},
    ).mappings().all()
    return [dict(r) for r in rows]


def ir_year_rows(db: Session, family_id: UUID, member_id: UUID, year: int) -> dict:
    """Materializa rendimentos e despesas dedutiveis do ano para o motor de IR.

    A classificacao sai da view `v_transactions_ir`, que ja resolve
    'override da transacao > herdado da categoria'.
    """
    incomes = db.execute(
        text(
            """
            SELECT v.ir_treatment::text AS treatment, SUM(v.amount) AS amount
              FROM v_transactions_ir v
             WHERE v.family_id = :family_id
               AND v.owner_member_id = :member_id
               AND v.ir_year = :year
               AND v.direction = 'ENTRADA'
             GROUP BY 1
            """
        ),
        {"family_id": family_id, "member_id": member_id, "year": year},
    ).mappings().all()

    deductions = db.execute(
        text(
            """
            SELECT v.ir_deduction_type::text AS deduction_type,
                   v.ir_deduction_member_id  AS member_id,
                   m.full_name               AS member_name,
                   SUM(v.amount)             AS amount
              FROM v_transactions_ir v
              LEFT JOIN members m ON m.id = v.ir_deduction_member_id
             WHERE v.family_id = :family_id
               AND v.owner_member_id = :member_id
               AND v.ir_year = :year
               AND v.direction = 'SAIDA'
               AND v.ir_deduction_type <> 'NENHUMA'
             GROUP BY 1, 2, 3
            """
        ),
        {"family_id": family_id, "member_id": member_id, "year": year},
    ).mappings().all()

    dependents = db.execute(
        text(
            """
            SELECT COUNT(*) AS n
              FROM members
             WHERE family_id = :family_id
               AND is_ir_dependent
               AND (ir_dependent_of = :member_id OR ir_dependent_of IS NULL)
            """
        ),
        {"family_id": family_id, "member_id": member_id},
    ).scalar_one()

    return {
        "incomes": [dict(r) for r in incomes],
        "deductions": [dict(r) for r in deductions],
        "dependents": int(dependents or 0),
    }


def spend_by_category(
    db: Session,
    family_id: UUID,
    start: date,
    end: date,
    member_id: UUID | None,
    depth: int = 2,
) -> list[dict]:
    """Gastos agrupados pelo nivel `depth` da arvore de categorias.

    `depth=1` agrega em Essenciais / Estilo de Vida / Metas / Financeiro;
    `depth=2` desce para Moradia, Alimentacao, Saude...; e assim por diante.
    O corte usa `subpath` do ltree, entao continua valendo se a arvore mudar de
    formato - inclusive quando o Felipe trocar a taxonomia pela dele.

    Lancamentos sem categoria nao somem: aparecem agrupados em 'Sem categoria',
    que e justamente o que precisa de atencao.
    """
    rows = db.execute(
        text(
            f"""
            WITH gastos AS (
                SELECT t.id,
                       t.amount,
                       t.owner_member_id,
                       CASE WHEN c.id IS NULL THEN NULL
                            ELSE subpath(c.path, 0, LEAST(:depth, nlevel(c.path)))
                       END AS grupo_path
                  FROM transactions t
                  LEFT JOIN categories c ON c.id = t.category_id
                 WHERE t.family_id = :family_id
                   AND t.direction = 'SAIDA'
                   AND t.status IN ('EFETIVADA', 'CONCILIADA')
                   AND t.booked_on BETWEEN :start AND :end
                   -- amortizacao e aporte saem da conta, mas nao sao consumo
                   AND COALESCE(c.counts_as_expense, true)
                   {_SCOPE_FILTER}
            )
            SELECT COALESCE(g.grupo_path::text, 'sem_categoria') AS path,
                   COALESCE(cat.name, 'Sem categoria')           AS name,
                   COALESCE(cat.icon, NULL)                      AS icon,
                   SUM(g.amount)                                 AS total,
                   COUNT(*)                                      AS lancamentos
              FROM gastos g
              LEFT JOIN categories cat
                     ON cat.path = g.grupo_path
                    AND cat.family_id IS NOT DISTINCT FROM :family_id
             GROUP BY 1, 2, 3
             ORDER BY 4 DESC
            """
        ),
        {
            "family_id": family_id,
            "start": start,
            "end": end,
            "member_id": member_id,
            "depth": depth,
        },
    ).mappings().all()

    total = sum((Decimal(r["total"]) for r in rows), ZERO)
    return [
        {
            "path": r["path"],
            "name": r["name"],
            "icon": r["icon"],
            "total": brl(r["total"]),
            "transactions": int(r["lancamentos"]),
            "share": (
                (Decimal(r["total"]) / total).quantize(Decimal("0.0001"))
                if total
                else ZERO
            ),
        }
        for r in rows
    ]


def spend_by_member(
    db: Session, family_id: UUID, start: date, end: date
) -> list[dict]:
    """Quanto cada um gastou no periodo - a leitura que so faz sentido depois
    de o responsavel poder ser informado por lancamento."""
    rows = db.execute(
        text(
            """
            SELECT m.id, m.full_name, COALESCE(m.nickname, m.full_name) AS apelido,
                   COALESCE(SUM(t.amount), 0) AS total,
                   COUNT(t.id)                AS lancamentos
              FROM members m
              LEFT JOIN transactions t
                     ON t.owner_member_id = m.id
                    AND t.direction = 'SAIDA'
                    AND t.status IN ('EFETIVADA', 'CONCILIADA')
                    AND t.booked_on BETWEEN :start AND :end
             WHERE m.family_id = :family_id
               AND m.password_hash IS NOT NULL
             GROUP BY 1, 2, 3
             ORDER BY 4 DESC
            """
        ),
        {"family_id": family_id, "start": start, "end": end},
    ).mappings().all()

    total = sum((Decimal(r["total"]) for r in rows), ZERO)
    return [
        {
            "member_id": r["id"],
            "name": r["apelido"],
            "total": brl(r["total"]),
            "transactions": int(r["lancamentos"]),
            "share": (
                (Decimal(r["total"]) / total).quantize(Decimal("0.0001"))
                if total
                else ZERO
            ),
        }
        for r in rows
    ]


def note_required_for(db: Session, category_id: UUID) -> str | None:
    """Nome da categoria que exige comentario, olhando a subarvore inteira.

    A exigencia e herdada: marcar 'Unicos' vale para 'Unicos > Viagens' e para
    qualquer filha criada depois. Sem a heranca, bastaria criar uma subcategoria
    para escapar da regra - e a exigencia existe justamente para o gasto avulso,
    que e onde os filhos ficam.
    """
    return db.execute(
        text(
            """
            SELECT ancestral.name
              FROM categories alvo
              JOIN categories ancestral
                ON ancestral.family_id IS NOT DISTINCT FROM alvo.family_id
               AND alvo.path <@ ancestral.path
             WHERE alvo.id = :category_id
               AND ancestral.requires_note
             ORDER BY nlevel(ancestral.path)
             LIMIT 1
            """
        ),
        {"category_id": category_id},
    ).scalar_one_or_none()
