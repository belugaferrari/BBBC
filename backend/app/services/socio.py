"""A fronteira entre o dinheiro da familia e o da empresa.

Duas situacoes acontecem de verdade, e cada uma erra de um jeito diferente se
for lancada ingenuamente:

**A empresa paga uma conta minha.** A escola da filha sai da conta da empresa.
Lancar so a despesa faz o caixa da familia cair R$ 3.000 por um gasto que nao
saiu do bolso dela: o saldo fica errado, e a previsao herda o erro. Mas ignorar
a linha tambem erra - o gasto com educacao existiu, conta na categoria, no teto
e no IR. A saida e o par: a despesa na categoria certa MAIS a entrada que a
cobre. No caixa somam zero; na analise de consumo, so a despesa aparece.

**Eu pago uma conta da empresa.** O dinheiro sai mesmo, entao o caixa cai de
verdade - mas isso nao e consumo da familia, e sim credito a receber. Vai para
uma categoria com counts_as_expense = false, o mesmo mecanismo que ja separa
amortizacao e aporte de despesa, e fica em aberto ate o acerto.

Este modulo e puro de proposito: as regras que decidem se os numeros fecham nao
precisam de banco para serem testadas.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from app.models.enums import SocioFlow, TxDirection

# A contrapartida de uma conta pessoal paga pela empresa. Cada uma e um imposto
# diferente, e por isso a escolha nao pode ter palpite embutido:
CONTRAPARTIDAS = {
    # entra na tabela progressiva
    "PRO_LABORE": "receitas.ativa_fixa.pro_labore",
    # isento na pessoa fisica
    "LUCROS": "receitas.ativa_variavel.lucros",
    # nao e renda: e saldo em conta-corrente de socio, a acertar depois
    "ADIANTAMENTO": "receitas.eventuais.adiantamento_socio",
}

# O padrao e o adiantamento porque e o unico que nao afirma nada sobre imposto.
# Classificar como pro-labore por omissao inventaria tributo; como lucro,
# esconderia um. Adiantamento deixa a decisao para quem sabe.
CONTRAPARTIDA_PADRAO = "ADIANTAMENTO"

CATEGORIA_PAGUEI_PELA_EMPRESA = "conta_corrente_socio.pago_por_mim"


@dataclass(frozen=True)
class Lancamento:
    """O que gravar. Sem id: ainda nao foi para o banco."""

    descricao: str
    valor: Decimal
    direcao: TxDirection
    categoria_path: str | None
    socio_flow: SocioFlow | None = None
    # Quando a saida nao e consumo (vem de counts_as_expense da categoria).
    conta_como_gasto: bool = True
    em_aberto: bool = False


class ContrapartidaDesconhecida(ValueError):
    """Nao da para inventar a classificacao: ela decide o imposto."""


def conta_paga_pela_empresa(
    *,
    descricao: str,
    valor: Decimal,
    categoria_pessoal_path: str,
    contrapartida: str = CONTRAPARTIDA_PADRAO,
) -> tuple[Lancamento, Lancamento]:
    """A empresa pagou uma conta minha: devolve o par (despesa, entrada).

    O par existe para o caixa nao mentir. Veja `efeito_no_caixa`.
    """
    if valor <= 0:
        raise ValueError("valor precisa ser positivo")
    if contrapartida not in CONTRAPARTIDAS:
        raise ContrapartidaDesconhecida(
            f"contrapartida '{contrapartida}' desconhecida; "
            f"use uma de {', '.join(sorted(CONTRAPARTIDAS))}"
        )

    despesa = Lancamento(
        descricao=descricao,
        valor=valor,
        direcao=TxDirection.SAIDA,
        categoria_path=categoria_pessoal_path,
        socio_flow=SocioFlow.PESSOAL_VIA_EMPRESA,
        conta_como_gasto=True,
    )
    entrada = Lancamento(
        descricao=f"Pago pela empresa: {descricao}",
        valor=valor,
        direcao=TxDirection.ENTRADA,
        categoria_path=CONTRAPARTIDAS[contrapartida],
        socio_flow=SocioFlow.PESSOAL_VIA_EMPRESA,
        conta_como_gasto=True,
    )
    return despesa, entrada


def conta_da_empresa_paga_por_mim(*, descricao: str, valor: Decimal) -> Lancamento:
    """Paguei algo da empresa: sai do caixa, mas nao e consumo da familia."""
    if valor <= 0:
        raise ValueError("valor precisa ser positivo")
    return Lancamento(
        descricao=descricao,
        valor=valor,
        direcao=TxDirection.SAIDA,
        categoria_path=CATEGORIA_PAGUEI_PELA_EMPRESA,
        socio_flow=SocioFlow.EMPRESA_VIA_PESSOAL,
        conta_como_gasto=False,
        em_aberto=True,
    )


def efeito_no_caixa(lancamentos: list[Lancamento]) -> Decimal:
    """Quanto o conjunto mexe no saldo. Entrada soma, saida subtrai."""
    total = Decimal("0")
    for lan in lancamentos:
        if lan.direcao == TxDirection.ENTRADA:
            total += lan.valor
        elif lan.direcao == TxDirection.SAIDA:
            total -= lan.valor
    return total


def efeito_no_consumo(lancamentos: list[Lancamento]) -> Decimal:
    """Quanto o conjunto conta como gasto da familia.

    Nao e o espelho do caixa: a entrada que cobre uma conta paga pela empresa
    nao abate consumo nenhum, e o que eu pago pela empresa nao e consumo meu.
    """
    return sum(
        (lan.valor for lan in lancamentos
         if lan.direcao == TxDirection.SAIDA and lan.conta_como_gasto),
        Decimal("0"),
    )


@dataclass(frozen=True)
class Pendencia:
    """Linha em aberto na conta-corrente com a empresa."""

    id: UUID
    descricao: str
    valor: Decimal
    data: date
    socio_flow: SocioFlow

    @property
    def quem_deve(self) -> str:
        return (
            "A empresa me deve"
            if self.socio_flow == SocioFlow.EMPRESA_VIA_PESSOAL
            else "Devo a empresa"
        )


def saldo_com_a_empresa(pendencias: list[Pendencia]) -> Decimal:
    """Positivo: a empresa me deve. Negativo: devo a ela."""
    total = Decimal("0")
    for p in pendencias:
        if p.socio_flow == SocioFlow.EMPRESA_VIA_PESSOAL:
            total += p.valor
        else:
            total -= p.valor
    return total
