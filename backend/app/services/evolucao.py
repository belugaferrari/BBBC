"""A curva do gasto acumulado no mes, com o que serve para julga-la.

O painel mostrava um Sankey - o diagrama de fluxos que se abre em leques. Ele e
bonito e responde "para onde foi o dinheiro", pergunta que a aba Categorias ja
responde melhor, com numeros. O que o Sankey nao responde e a pergunta que se faz
no dia 12 do mes: "estou gastando rapido demais?"

Para responder isso nao basta o total: precisa do RITMO, e ritmo so aparece
comparado. Daqui saem quatro curvas sobre o mesmo eixo de dias:

  * o acumulado deste mes, que e a resposta;
  * o acumulado do mes passado, que diz se mudou alguma coisa agora;
  * o acumulado do mesmo mes do ano passado, que separa mudanca de sazonalidade
    (escola em fevereiro, presente em dezembro, IPVA em janeiro);
  * a meta do mes, que e reta porque e um teto.

A meta vem da vigencia, e nao do valor de hoje: o mes passado e julgado pela meta
que valia no mes passado. Mudar a meta agora nao pode mexer no grafico de antes.
"""

from __future__ import annotations

from calendar import monthrange
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.analise_categoria import brl, mes_anterior, primeiro_do_mes

ZERO = Decimal("0.00")

# Gasto que conta como consumo: saiu, esta efetivado, e nao e transferencia
# patrimonial (amortizacao, aporte, pagamento de fatura).
_POR_DIA = """
    SELECT EXTRACT(DAY FROM t.booked_on)::int AS dia,
           SUM(t.amount)                      AS total
      FROM transactions t
      LEFT JOIN categories c ON c.id = t.category_id
     WHERE t.family_id = :family_id
       AND t.direction = 'SAIDA'
       AND t.status IN ('EFETIVADA', 'CONCILIADA')
       AND COALESCE(c.counts_as_expense, true)
       AND date_trunc('month', t.booked_on) = date_trunc('month', CAST(:mes AS date))
       AND (CAST(:member_id AS uuid) IS NULL
            OR t.owner_member_id = CAST(:member_id AS uuid))
     GROUP BY 1
"""


def _acumulado(
    db: Session, family_id: UUID, mes: date, member_id: UUID | None
) -> list[dict]:
    """Um ponto por dia do mes, somando o que veio antes.

    Todos os dias aparecem, inclusive os sem gasto: a curva tem de ser continua.
    Um grafico que pula o dia 7 porque ninguem gastou nada nele sobe em degraus
    que nao existiram.
    """
    por_dia = {
        int(linha[0]): Decimal(linha[1])
        for linha in db.execute(
            text(_POR_DIA), {"family_id": family_id, "mes": mes, "member_id": member_id}
        )
    }
    dias = monthrange(mes.year, mes.month)[1]

    pontos = []
    acumulado = ZERO
    for dia in range(1, dias + 1):
        acumulado += por_dia.get(dia, ZERO)
        pontos.append({"day": dia, "total": brl(acumulado)})
    return pontos


def _meta_do_mes(db: Session, family_id: UUID, mes: date) -> Decimal | None:
    """Soma das metas que valiam NAQUELE mes.

    So o primeiro nivel da arvore de despesa entra na soma. As metas de
    subcategoria ficam de fora porque ja estao contidas na do pai - somar as
    duas contaria Gasolina dentro de Transporte e sozinha, e o teto do mes
    apareceria maior do que e.
    """
    total = db.execute(
        text(
            """
            SELECT SUM(b.amount)
              FROM budget_caps b
              JOIN categories c ON c.id = b.category_id
             WHERE b.family_id = :family_id
               AND b.member_id IS NULL
               AND nlevel(c.path) = 2
               AND b.starts_on <= CAST(:mes AS date)
               AND (b.ends_on IS NULL OR b.ends_on >= CAST(:mes AS date))
            """
        ),
        {"family_id": family_id, "mes": mes},
    ).scalar()
    return brl(total) if total is not None else None


def evolucao_do_mes(
    db: Session, family_id: UUID, mes: date, member_id: UUID | None = None
) -> dict:
    """O gasto acumulado do mes e as tres referencias para julga-lo."""
    mes = primeiro_do_mes(mes)
    passado = mes_anterior(mes)
    ano_passado = mes_anterior(mes, 12)

    def bloco(alvo: date) -> dict:
        pontos = _acumulado(db, family_id, alvo, member_id)
        return {
            "month": alvo,
            "total": pontos[-1]["total"] if pontos else ZERO,
            "series": pontos,
            # A meta daquele mes, pela vigencia. E o que impede o grafico de
            # setembro de mudar quando a meta de outubro muda.
            "cap": _meta_do_mes(db, family_id, alvo),
        }

    hoje = date.today()
    return {
        "month": mes,
        "days_in_month": monthrange(mes.year, mes.month)[1],
        # Ate que dia a curva deste mes e real. Nos meses fechados, o mes inteiro;
        # no mes corrente, hoje - desenhar a linha reta ate o dia 31 faria o mes
        # parecer estagnado em vez de incompleto.
        "today": hoje.day if (hoje.year, hoje.month) == (mes.year, mes.month) else None,
        "current": bloco(mes),
        "previous_month": bloco(passado),
        "same_month_last_year": bloco(ano_passado),
    }
