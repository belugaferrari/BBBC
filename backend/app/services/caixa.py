"""Quando o dinheiro sai da conta - que nem sempre e o dia da compra.

"O extrato do cartao vem com a data da efetivacao da compra, nao com a data do
pagamento do cartao."

Sao duas datas diferentes, e o sistema precisava das duas:

  * `booked_on` e QUANDO ACONTECEU. E a data da compra, a que esta no extrato, a
    que ele lembra. E ela que aparece na lista: "jantar, dia 25".
  * `paid_on` e QUANDO O DINHEIRO SAIU. Numa conta corrente, e o mesmo dia. Num
    cartao, e o vencimento da fatura que cobra aquela compra - o mes seguinte,
    quase sempre.

O MES do Resumo e o do `paid_on`, por decisao dele: o gasto conta no mes em que
de fato saiu da conta. Assim o Resumo fecha com o extrato bancario, que e o
documento contra o qual ele confere.

A compra parcelada cai sozinha nesse desenho: cada fatura cobra uma parcela, e
cada parcela sai da conta no vencimento da SUA fatura. Importando a fatura de
cada mes, as parcelas se distribuem pelos meses sem ninguem precisar espalhar
nada - porque elas de fato aconteceram assim.
"""

from __future__ import annotations

import calendar
from datetime import date

# Sem o dia de fechamento cadastrado, a suposicao e a mais comum e a mais
# conservadora: a fatura pega o mes inteiro e vence no inicio do mes seguinte.
# E tambem como ele descreveu o proprio cartao - "aparece contabilmente so no
# mes seguinte".
FECHAMENTO_PADRAO = 31
VENCIMENTO_PADRAO = 10


def _dia_valido(ano: int, mes: int, dia: int) -> date:
    """Dia 31 em fevereiro vira o ultimo dia de fevereiro.

    Cartao que fecha dia 31 existe, e fevereiro tambem. Sem o corte, a conta
    levantaria ValueError no meio de uma importacao."""
    ultimo = calendar.monthrange(ano, mes)[1]
    return date(ano, mes, min(dia, ultimo))


def _somar_meses(ano: int, mes: int, quantos: int) -> tuple[int, int]:
    total = (ano * 12 + (mes - 1)) + quantos
    return total // 12, total % 12 + 1


def fatura_que_cobra(
    compra: date, *, fechamento: int | None = None, vencimento: int | None = None
) -> date:
    """O vencimento da fatura que cobra uma compra feita neste dia.

    Duas contas, nesta ordem:

      1. QUAL FATURA pega a compra. A que fecha depois dela: comprou ate o dia do
         fechamento, entra na fatura deste mes; comprou depois, ja e a do mes que
         vem. E por isso que uma compra do dia 26 e uma do dia 24 podem ser
         cobradas com um mes de diferenca.
      2. QUANDO essa fatura vence. Se o vencimento cai num dia MENOR que o do
         fechamento, ele e do mes seguinte - fecha dia 25, vence dia 5. Se for
         maior, e do mesmo mes: fecha dia 5, vence dia 15.
    """
    dia_fechamento = fechamento or FECHAMENTO_PADRAO
    dia_vencimento = vencimento or VENCIMENTO_PADRAO

    ano, mes = compra.year, compra.month
    if compra.day > min(dia_fechamento, calendar.monthrange(ano, mes)[1]):
        ano, mes = _somar_meses(ano, mes, 1)

    if dia_vencimento <= dia_fechamento:
        ano, mes = _somar_meses(ano, mes, 1)
    return _dia_valido(ano, mes, dia_vencimento)


def data_de_caixa(
    booked_on: date,
    *,
    e_cartao: bool,
    fechamento: int | None = None,
    vencimento: int | None = None,
) -> date:
    """O dia em que o dinheiro sai da conta por causa deste lancamento."""
    if not e_cartao:
        return booked_on
    return fatura_que_cobra(booked_on, fechamento=fechamento, vencimento=vencimento)


def caixa_da_conta(account, booked_on: date, direction) -> date:  # noqa: ANN001
    """A data de caixa de um lancamento, lendo a conta de onde ele sai.

    So a COMPRA no cartao espera a fatura. O credito dentro de uma conta de
    cartao - o pagamento da propria fatura, que vem dentro do extrato dele -
    acontece no dia em que acontece: ele nao e cobrado por fatura nenhuma.
    """
    from app.models.enums import AccountType, TxDirection

    e_cartao = (
        getattr(account, "type", None) == AccountType.CARTAO_CREDITO
        and direction == TxDirection.SAIDA
    )
    return data_de_caixa(
        booked_on,
        e_cartao=e_cartao,
        fechamento=getattr(account, "statement_close_day", None),
        vencimento=getattr(account, "statement_due_day", None),
    )


def meses_depois(quando: date, meses: int) -> date:
    """A mesma data, tantos meses adiante - com o dia cortado quando nao existe.

    E a conta das parcelas: a fatura de novembro vence no mesmo dia que a de
    outubro. Dia 31 em meses de 30 vira o ultimo dia, que e o que o cartao faz.
    """
    ano, mes = _somar_meses(quando.year, quando.month, meses)
    return _dia_valido(ano, mes, quando.day)


def caixa_da_parcela(account, booked_on: date, direction, numero_da_parcela: int | None) -> date:  # noqa: ANN001
    """A data de caixa de UMA parcela.

    A fatura repete a data da COMPRA em toda parcela: a de novembro traz
    "MAGAZINE 02/10" datada do dia da compra, em setembro. Entao a conta nao
    pode parar na fatura que cobra a compra - a parcela 2 sai uma fatura depois
    dela, a 3 duas faturas depois, e assim por diante.

    Sem isto, todas as parcelas de uma compra cairiam no mesmo mes, e uma compra
    de dez vezes pesaria dez vezes num mes so - o oposto exato do que parcelar
    faz com o dinheiro de verdade.
    """
    base = caixa_da_conta(account, booked_on, direction)
    if not numero_da_parcela or numero_da_parcela <= 1:
        return base
    return meses_depois(base, numero_da_parcela - 1)
