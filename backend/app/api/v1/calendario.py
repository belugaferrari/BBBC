"""O ano inteiro numa tela.

"Crie uma aba 'Calendario': esse sim sera o grande resumo da coisa toda. Ano na
parte superior. Uma tela com 12 retangulos com as abreviacoes de cada mes
mostrando ali quanto entrou e o quanto saiu em cada mes. Abaixo o acumulado do
ano (entradas; saidas; Lucros/Prejuizos). Abaixo disso o resumo da atualidade,
com as seguintes informacoes: Patrimonio; Reservas; Gastos mes anterior."

Tres alturas de leitura, da mais larga para a mais estreita, e e a largura que
define o que cada uma responde:

  * o ANO mes a mes - onde estao os picos, que mes saiu do lugar;
  * o ACUMULADO - o ano foi de lucro ou de prejuizo;
  * o HOJE - quanto a familia tem, quanto da para usar, e quanto custou o ultimo
    mes fechado.
"""

from datetime import date, timedelta

from fastapi import APIRouter, Query

from app.api.deps import CurrentMember, DbSession, scope_member_id
from app.services.money import ZERO, brl
from app.services.queries import consolidated_balances, monthly_cashflow, year_calendar

router = APIRouter(prefix="/calendario", tags=["calendario"])


def _mes_anterior(hoje: date) -> date:
    """O ultimo mes FECHADO. O mes corrente nao serve de comparacao: no dia 3
    ele esta vazio, e no dia 28 esta quase cheio."""
    return (hoje.replace(day=1) - timedelta(days=1)).replace(day=1)


@router.get("")
def calendario(
    current: CurrentMember,
    db: DbSession,
    year: int | None = Query(None, ge=2000, le=2100),
    scope: str = Query("familia", pattern="^(familia|individual)$"),
) -> dict:
    hoje = date.today()
    ano = year or hoje.year
    owner = scope_member_id(current, scope)

    meses = year_calendar(db, current.family_id, ano, owner)
    entrou = sum((m["entrou"] for m in meses), ZERO)
    saiu = sum((m["saiu"] for m in meses), ZERO)

    saldos = consolidated_balances(db, current.family_id, owner)
    anterior = _mes_anterior(hoje)
    fechado = monthly_cashflow(db, current.family_id, anterior, owner)

    return {
        "year": ano,
        "scope": scope,
        "months": meses,
        "ano": {
            "entrou": brl(entrou),
            "saiu": brl(saiu),
            # Lucro ou prejuizo: a unica pergunta que o ano inteiro responde
            # melhor do que qualquer mes sozinho.
            "net": brl(entrou - saiu),
        },
        "hoje": {
            # tudo o que a familia tem, somando contas e investimentos e tirando
            # a divida do cartao
            "patrimonio": saldos["net_worth"],
            # o que da para usar hoje, sem mexer em investimento
            "reservas": saldos["liquid"],
            "investido": saldos["invested"],
            "divida_no_cartao": saldos["credit_card_debt"],
            # fora do patrimonio, e dito em voz alta: o dinheiro da empresa nao
            # e da familia, mas tambem nao pode sumir da tela
            "na_empresa": saldos["na_empresa"],
            "mes_anterior": anterior,
            "gastos_mes_anterior": fechado["consumo_proprio"],
        },
    }
