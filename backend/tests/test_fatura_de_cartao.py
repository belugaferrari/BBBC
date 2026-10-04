"""A fatura do cartao, que fala pelo lado da divida.

"Realmente temos um problema com o cartao de credito. No inicio ele poe o valor
total como negativo e todo o resto sai discriminado como positivo. (...) alem de
aparecer como saldo no sistema, as categorias saem invertidas."

Num extrato de CONTA o sinal e o do saldo: gasto negativo, deposito positivo. Na
FATURA o sinal e o da DIVIDA: a compra aumenta o que se deve, entao vem
positiva. Lida com a regra da conta, a fatura inteira vira ao contrario - as
compras entram como ENTRADA, pegam categoria de receita e inflam a renda, e o
total da fatura, por ser o unico negativo, vira o unico gasto do mes.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.models.enums import TxDirection
from app.services.importers import fatura
from app.services.importers.base import ParsedStatement, ParsedTransaction


def tx(valor: str, descricao: str, dia: int = 3) -> ParsedTransaction:
    """Uma linha como o leitor de planilha entrega: sinal virou direcao.

    Positivo = ENTRADA e negativo = SAIDA e a regra do extrato de CONTA, que e a
    que os leitores aplicam. O ajuste da fatura acontece depois, e e ele que esta
    sendo testado aqui.
    """
    numero = Decimal(valor)
    return ParsedTransaction(
        booked_on=date(2026, 9, dia),
        amount=abs(numero),
        direction=TxDirection.ENTRADA if numero >= 0 else TxDirection.SAIDA,
        description=descricao,
    )


def extrato(*linhas: ParsedTransaction, formato: str = "XLSX") -> ParsedStatement:
    return ParsedStatement(file_format=formato, transactions=list(linhas))


# ---------------------------------------------------------------------------
# A fatura dele
# ---------------------------------------------------------------------------
def A_FATURA_DELE() -> ParsedStatement:
    """O arquivo que ele descreveu: total negativo na frente, compras positivas."""
    return extrato(
        tx("-1035.80", "TOTAL DA FATURA", dia=1),
        tx("245.90", "POSTO SHELL AV BRASIL", dia=3),
        tx("189.00", "IFOOD CLUB", dia=12),
        tx("600.90", "SUPERMERCADO PAO DE ACUCAR", dia=15),
    )


def test_as_compras_da_fatura_entram_como_gasto():
    ajustado = fatura.ajustar(A_FATURA_DELE(), e_cartao=True)
    assert [t.direction for t in ajustado.transactions] == [TxDirection.SAIDA] * 3
    assert sum(t.amount for t in ajustado.transactions) == Decimal("1035.80")


def test_o_total_da_fatura_nao_vira_lancamento():
    """Importado junto, ele cobra o mes duas vezes.

    E a conta em dobro que ele tinha levantado quando descobriu que o extrato da
    conta trazia o cartao sem detalhe.
    """
    ajustado = fatura.ajustar(A_FATURA_DELE(), e_cartao=True)
    assert len(ajustado.transactions) == 3
    assert all("TOTAL" not in t.description for t in ajustado.transactions)


def test_a_correcao_e_dita_na_tela_de_conferencia():
    """Correcao silenciosa em dinheiro e a que ninguem confere."""
    ajustado = fatura.ajustar(A_FATURA_DELE(), e_cartao=True)
    assert len(ajustado.warnings) == 2
    juntos = " ".join(ajustado.warnings).lower()
    assert "cartao" in juntos
    assert "resumo" in juntos or "soma" in juntos


def test_o_pagamento_da_fatura_continua_sendo_entrada():
    """O pagamento abate a divida: no cartao, ele e entrada.

    Depois da inversao ele precisa continuar do lado certo - e e justamente ele
    que, contado como renda, criou os R$ 4.320,15 de renda que nao existiam.
    """
    ajustado = fatura.ajustar(
        extrato(
            tx("-4320.15", "PAGAMENTO EFETUADO", dia=10),
            tx("245.90", "POSTO SHELL", dia=3),
            tx("189.00", "IFOOD CLUB", dia=12),
            tx("600.90", "SUPERMERCADO", dia=15),
        ),
        e_cartao=True,
    )
    pagamento = next(t for t in ajustado.transactions if "PAGAMENTO" in t.description)
    assert pagamento.direction == TxDirection.ENTRADA
    compras = [t for t in ajustado.transactions if "PAGAMENTO" not in t.description]
    assert [t.direction for t in compras] == [TxDirection.SAIDA] * 3


# ---------------------------------------------------------------------------
# O que NAO pode acontecer
# ---------------------------------------------------------------------------
def test_fatura_que_ja_vem_com_o_sinal_certo_fica_como_esta():
    """Metade dos bancos exporta a fatura com a compra negativa.

    Inverter por tabela de banco seria errar no proximo banco; a decisao e pela
    maioria das linhas, e aqui a maioria ja esta do lado certo.
    """
    ajustado = fatura.ajustar(
        extrato(
            tx("-245.90", "POSTO SHELL"),
            tx("-189.00", "IFOOD CLUB"),
            tx("-600.90", "SUPERMERCADO"),
            tx("4320.15", "PAGAMENTO EFETUADO"),
        ),
        e_cartao=True,
    )
    por_nome = {t.description: t.direction for t in ajustado.transactions}
    assert por_nome["POSTO SHELL"] == TxDirection.SAIDA
    assert por_nome["PAGAMENTO EFETUADO"] == TxDirection.ENTRADA
    assert not any("sinal" in a for a in ajustado.warnings)


def test_extrato_de_conta_corrente_nao_e_tocado():
    """So a fatura fala pelo lado da divida.

    Em conta corrente, o deposito de salario e positivo e E entrada. Inverter ali
    seria transformar a renda do mes em gasto.
    """
    conta = extrato(
        tx("10000.00", "SALARIO"),
        tx("28000.00", "PRO LABORE"),
        tx("-245.90", "POSTO SHELL"),
    )
    ajustado = fatura.ajustar(conta, e_cartao=False)
    assert [t.direction for t in ajustado.transactions] == [
        TxDirection.ENTRADA,
        TxDirection.ENTRADA,
        TxDirection.SAIDA,
    ]
    assert ajustado.warnings == []


def test_posto_chamado_total_continua_sendo_compra():
    """"TOTAL ENERGIES BR" e estabelecimento, nao rodape.

    Por isso a comparacao de nome e por igualdade, e nunca por prefixo: um
    prefixo apagaria a compra e o mes ficaria mais barato do que foi.
    """
    ajustado = fatura.ajustar(
        extrato(
            tx("120.00", "TOTAL ENERGIES BR 1234"),
            tx("245.90", "POSTO SHELL"),
            tx("189.00", "IFOOD CLUB"),
        ),
        e_cartao=True,
    )
    assert len(ajustado.transactions) == 3
    assert all(t.direction == TxDirection.SAIDA for t in ajustado.transactions)


def test_duas_compras_de_valor_igual_nao_viram_total_uma_da_outra():
    """Com duas linhas, "uma e a soma da outra" e coincidencia.

    Apagar uma compra de verdade e pior que deixar passar um total: o total da
    uma diferenca visivel no mes, a compra apagada nao da nenhuma.
    """
    ajustado = fatura.ajustar(
        extrato(tx("-100.00", "MERCADO A"), tx("100.00", "MERCADO B")),
        e_cartao=True,
    )
    assert len(ajustado.transactions) == 2


def test_estorno_dentro_da_fatura_sobrevive_a_inversao():
    """Estorno de compra e credito na fatura, e continua credito depois."""
    ajustado = fatura.ajustar(
        extrato(
            tx("245.90", "POSTO SHELL"),
            tx("189.00", "IFOOD CLUB"),
            tx("600.90", "SUPERMERCADO"),
            tx("-50.00", "ESTORNO IFOOD"),
        ),
        e_cartao=True,
    )
    estorno = next(t for t in ajustado.transactions if "ESTORNO" in t.description)
    assert estorno.direction == TxDirection.ENTRADA
    assert estorno.amount == Decimal("50.00")
    assert len(ajustado.transactions) == 4


def test_o_resumo_sai_mesmo_em_extrato_de_conta():
    """Linha de total e rodape de planilha em qualquer extrato."""
    ajustado = fatura.ajustar(
        extrato(tx("10000.00", "SALARIO"), tx("10000.00", "Total")),
        e_cartao=False,
    )
    assert [t.description for t in ajustado.transactions] == ["SALARIO"]


def test_no_ofx_a_descricao_nao_apaga_lancamento():
    """No OFX cada lancamento e um bloco, nunca um rodape - e o texto vem do
    MEMO, que pode ser o nome do estabelecimento."""
    ajustado = fatura.ajustar(
        extrato(tx("-100.00", "Total"), tx("-50.00", "MERCADO"), formato="OFX"),
        e_cartao=True,
    )
    assert len(ajustado.transactions) == 2


def test_extrato_vazio_nao_quebra():
    assert fatura.ajustar(extrato(), e_cartao=True).transactions == []
