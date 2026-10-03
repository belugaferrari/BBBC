"""Leitura de uma categoria ao longo do tempo: mes, ano passado e doze meses.

A pergunta que estas funcoes respondem nao e "quanto gastei" - isso o painel ja
dizia. E "quanto gastei COMPARADO COM O QUE", que e o que transforma um numero em
decisao. Tres comparacoes, porque cada uma pega um tipo diferente de problema:

  * contra a meta do mes: estou dentro ou fora do combinado;
  * contra o mesmo mes do ano passado: subiu de verdade ou e sazonalidade
    (escola em fevereiro, IPVA em janeiro, presente em dezembro);
  * contra os doze meses: qual o tamanho normal desta categoria, para o mes
    esquisito aparecer como esquisito.

A soma desce a subarvore inteira: a meta fica no nivel em que a pessoa pensa
("Transporte"), e o gasto chega nas folhas ("Gasolina", "Estacionamento").
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

ZERO = Decimal("0.00")


def brl(valor: Decimal | int | float | None) -> Decimal:
    return Decimal(valor or 0).quantize(Decimal("0.01"))


def primeiro_do_mes(dia: date) -> date:
    return dia.replace(day=1)


def mes_anterior(mes: date, meses: int = 1) -> date:
    """Recua `meses` meses a partir do primeiro dia de `mes`."""
    total = (mes.year * 12 + mes.month - 1) - meses
    return date(total // 12, total % 12 + 1, 1)


# Dinheiro que saiu E foi consumo. `counts_as_expense` tira amortizacao, aporte e
# pagamento de fatura; `direction = 'SAIDA'` tira as entradas; o status tira o
# que ainda e previsao.
_FILTRO_GASTO = """
    t.direction = 'SAIDA'
AND t.status IN ('EFETIVADA', 'CONCILIADA')
AND COALESCE(c.counts_as_expense, true)
"""


def serie_mensal(
    db: Session,
    family_id: UUID,
    category_id: UUID,
    ate: date,
    meses: int = 13,
    member_id: UUID | None = None,
) -> list[dict]:
    """Gasto mes a mes na subarvore da categoria, do mais antigo ao mais novo.

    Meses sem gasto nenhum voltam com zero, e nao faltando: um grafico com buraco
    no meio mente sobre a forma da serie, e a media dividiria pelo numero errado.
    """
    fim = primeiro_do_mes(ate)
    inicio = mes_anterior(fim, meses - 1)

    linhas = db.execute(
        text(
            f"""
            WITH meses AS (
                SELECT generate_series(
                    CAST(:inicio AS date), CAST(:fim AS date), interval '1 month'
                )::date AS mes
            ),
            alvo AS (
                SELECT path FROM categories WHERE id = :category_id
            ),
            gastos AS (
                SELECT date_trunc('month', t.booked_on)::date AS mes,
                       SUM(t.amount) AS total,
                       COUNT(*)      AS lancamentos
                  FROM transactions t
                  JOIN categories c ON c.id = t.category_id
                 WHERE t.family_id = :family_id
                   AND {_FILTRO_GASTO}
                   AND c.path <@ (SELECT path FROM alvo)
                   AND t.booked_on >= CAST(:inicio AS date)
                   AND t.booked_on < (CAST(:fim AS date) + interval '1 month')
                   -- CAST obrigatorio: sem ele o Postgres nao consegue
                   -- inferir o tipo do parametro num `$1 IS NULL` solto, e a
                   -- consulta inteira falha com "could not determine data type"
                   AND (CAST(:member_id AS uuid) IS NULL
                        OR t.owner_member_id = CAST(:member_id AS uuid))
                 GROUP BY 1
            )
            SELECT m.mes,
                   COALESCE(g.total, 0)       AS total,
                   COALESCE(g.lancamentos, 0) AS lancamentos
              FROM meses m
              LEFT JOIN gastos g ON g.mes = m.mes
             ORDER BY m.mes
            """
        ),
        {
            "family_id": family_id,
            "category_id": category_id,
            "inicio": inicio,
            "fim": fim,
            "member_id": member_id,
        },
    ).mappings().all()

    return [
        {
            "month": linha["mes"],
            "total": brl(linha["total"]),
            "transactions": int(linha["lancamentos"]),
        }
        for linha in linhas
    ]


def meta_vigente(
    db: Session, family_id: UUID, category_id: UUID, mes: date
) -> dict | None:
    """A meta que valia naquele mes, se havia uma.

    Olhar a vigencia, e nao so a existencia, e o que permite mudar a meta em
    maio sem reescrever a historia de janeiro a abril.
    """
    linha = db.execute(
        text(
            """
            SELECT b.id, b.amount, b.alert_at_pct, b.includes_descendants,
                   b.member_id, b.period, b.starts_on, b.ends_on
              FROM budget_caps b
             WHERE b.family_id = :family_id
               AND b.category_id = :category_id
               AND b.starts_on <= CAST(:mes AS date)
               AND (b.ends_on IS NULL OR b.ends_on >= CAST(:mes AS date))
             ORDER BY b.starts_on DESC
             LIMIT 1
            """
        ),
        {"family_id": family_id, "category_id": category_id, "mes": mes},
    ).mappings().first()
    if linha is None:
        return None
    return {
        "id": linha["id"],
        "amount": brl(linha["amount"]),
        "alert_at_pct": linha["alert_at_pct"],
        "includes_descendants": linha["includes_descendants"],
        "member_id": linha["member_id"],
        "period": linha["period"],
        "starts_on": linha["starts_on"],
        "ends_on": linha["ends_on"],
    }


def analise(
    db: Session,
    family_id: UUID,
    category_id: UUID,
    mes: date,
    member_id: UUID | None = None,
) -> dict:
    """Tudo o que a tela da categoria mostra, numa consulta de treze meses.

    Treze e nao doze de proposito: os doze da media mais o mes escolhido. Com
    doze, ou a media incluiria o mes que ela deveria julgar, ou faltaria um ponto
    no grafico.
    """
    mes = primeiro_do_mes(mes)
    serie = serie_mensal(db, family_id, category_id, mes, meses=25, member_id=member_id)
    por_mes = {linha["month"]: linha for linha in serie}

    deste_mes = por_mes.get(mes, {"total": ZERO, "transactions": 0})
    mes_passado = por_mes.get(mes_anterior(mes), {"total": ZERO, "transactions": 0})
    ano_passado = por_mes.get(mes_anterior(mes, 12), {"total": ZERO, "transactions": 0})

    # Os doze meses ANTERIORES ao escolhido: e com eles que se julga o mes, e
    # incluir o proprio mes na media faria a media perseguir o que ela mede.
    doze = [
        por_mes[mes_anterior(mes, n)]["total"]
        for n in range(1, 13)
        if mes_anterior(mes, n) in por_mes
    ]
    acumulado = brl(sum(doze, ZERO))
    media = brl(acumulado / len(doze)) if doze else ZERO

    meta = meta_vigente(db, family_id, category_id, mes)
    gasto = deste_mes["total"]

    return {
        "month": mes,
        "spent": gasto,
        "transactions": deste_mes["transactions"],
        "cap": meta,
        "remaining": brl(meta["amount"] - gasto) if meta else None,
        "used_pct": (
            (gasto / meta["amount"]).quantize(Decimal("0.0001"))
            if meta and meta["amount"]
            else None
        ),
        "previous_month": mes_passado["total"],
        "same_month_last_year": ano_passado["total"],
        # Variacao contra zero nao e "infinito por cento": e "nao havia base de
        # comparacao", e a tela precisa saber a diferenca para nao escrever
        # besteira.
        "vs_last_year_pct": (
            ((gasto - ano_passado["total"]) / ano_passado["total"]).quantize(
                Decimal("0.0001")
            )
            if ano_passado["total"]
            else None
        ),
        "last_12_months": acumulado,
        "monthly_average": media,
        "vs_average_pct": (
            ((gasto - media) / media).quantize(Decimal("0.0001")) if media else None
        ),
        # Treze pontos para o grafico: o mes e os doze que o antecedem.
        "series": [
            linha
            for linha in serie
            if linha["month"] >= mes_anterior(mes, 12) and linha["month"] <= mes
        ],
    }
