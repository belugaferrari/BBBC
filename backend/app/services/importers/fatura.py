"""O extrato de cartao de credito, que fala ao contrario do extrato de conta.

"No inicio ele poe o valor total como negativo e todo o resto sai discriminado
como positivo."

Num extrato de CONTA, o sinal e o do saldo: gasto negativo, deposito positivo. E
o que todos os leitores assumem, e esta certo lá. Na FATURA do cartao o sinal e o
da DIVIDA: cada compra aumenta o que voce deve, entao vem positiva, e o
pagamento da fatura (que abate a divida) vem negativo. O mesmo numero, o mesmo
sinal, dois significados opostos.

Lido com a regra da conta, o mes inteiro vira ao contrario: as compras entram
como ENTRADA - dinheiro chegando -, pegam categoria de receita, inflam a renda e
a taxa de poupanca. E o total da fatura, por ser o unico negativo, entra como o
unico gasto. Foi exatamente o que apareceu na tela.

Duas correcoes, e as duas precisam acontecer ANTES da impressao digital, porque
a direcao entra nela: corrigir depois criaria uma linha nova em vez de consertar
a que ja existe.

  1. **O sinal.** Numa fatura, a esmagadora maioria das linhas e compra. Se a
     maioria chegou como ENTRADA, foi o sinal que estava invertido - e nao o mes
     que foi de devolucoes. Por isso a decisao e pela maioria, e nao por uma
     tabela de bancos: funciona com o banco que exporta certo, com o que exporta
     errado, e com o proximo.

  2. **A linha do total.** A fatura repete, numa linha, a soma das outras. Ela
     nao e um lancamento: importada junto, cobra o mes duas vezes - e era
     justamente o risco de contar em dobro que ele tinha levantado.
"""

from __future__ import annotations

import unicodedata
from dataclasses import replace
from decimal import Decimal

from app.models.enums import TxDirection
from app.services.importers.base import ParsedStatement, ParsedTransaction

# Tolerancia ao comparar o total com a soma das linhas: centavo de arredondamento
# de IOF e conversao de moeda aparece em fatura de verdade.
_FOLGA = Decimal("0.02")

# Quantas linhas de compra a soma precisa ter para o teste aritmetico valer. Com
# duas linhas iguais - R$ 100 e R$ 100 -, uma e "a soma da outra" por
# coincidencia, e apagar uma compra de verdade e pior que deixar passar um total.
_MINIMO_PARA_A_SOMA = 3

# Frases que sao resumo, e nao lancamento. Comparadas por IGUALDADE, nunca por
# prefixo: posto "TOTAL ENERGIES BR" e compra, e um prefixo o apagaria.
_RESUMOS = frozenset(
    {
        "total",
        "total geral",
        "total parcial",
        "subtotal",
        "total da fatura",
        "total desta fatura",
        "total fatura",
        "fatura",
        "total a pagar",
        "total a pagar desta fatura",
        "valor total",
        "valor total da fatura",
        "valor da fatura",
        "total dos lancamentos",
        "total de lancamentos",
        "total do periodo",
        "total nacional",
        "total internacional",
        "total nacionais",
        "total internacionais",
        "total de compras",
        "total compras",
        "saldo total",
    }
)


def _sem_enfeite(texto: str) -> str:
    """Minusculas, sem acento, sem "r$" e sem pontuacao de borda."""
    plano = unicodedata.normalize("NFKD", texto or "")
    plano = "".join(c for c in plano if not unicodedata.combining(c))
    plano = plano.lower().replace("r$", " ")
    plano = " ".join(plano.replace(":", " ").replace("-", " ").split())
    return plano.strip(" .")


def _e_resumo(descricao: str) -> bool:
    return _sem_enfeite(descricao) in _RESUMOS


def _inverter(tx: ParsedTransaction) -> ParsedTransaction:
    oposta = (
        TxDirection.SAIDA
        if tx.direction == TxDirection.ENTRADA
        else TxDirection.ENTRADA
    )
    return replace(tx, direction=oposta)


def _indice_do_total(transacoes: list[ParsedTransaction]) -> int | None:
    """A linha que e a SOMA das outras - o total da fatura, nao uma compra.

    O teste e aritmetico de proposito: nome de linha varia de banco para banco e
    de exportacao para exportacao, mas "este numero e a soma dos outros" e um
    fato do arquivo. As tres condicoes juntas existem para nao apagar lancamento
    de verdade:

      * a linha esta na direcao OPOSTA a das compras (na fatura, o total vem com
        o sinal contrario ao delas);
      * o valor dela bate com o que as compras somam - com ou sem as devolucoes
        descontadas, porque banco nenhum concorda sobre isso;
      * ha compras o bastante para essa soma nao ser coincidencia.

    Se a coincidencia acontecer e a linha removida for um pagamento de fatura de
    verdade, o estrago e pequeno: pagamento de fatura nao conta como gasto da
    familia em lugar nenhum, so muda o saldo daquele cartao. Deixar o total
    passar, ao contrario, cobra o mes inteiro duas vezes.
    """
    compras = [t for t in transacoes if t.direction == TxDirection.SAIDA]
    if len(compras) < _MINIMO_PARA_A_SOMA:
        return None

    for indice, candidata in enumerate(transacoes):
        if candidata.direction != TxDirection.ENTRADA:
            continue
        devolvido = sum(
            (
                t.amount
                for i, t in enumerate(transacoes)
                if i != indice and t.direction == TxDirection.ENTRADA
            ),
            start=Decimal("0"),
        )
        gasto = sum((t.amount for t in compras), start=Decimal("0"))
        if min(
            abs(candidata.amount - gasto),
            abs(candidata.amount - (gasto - devolvido)),
        ) <= _FOLGA:
            return indice
    return None


def ajustar(statement: ParsedStatement, *, e_cartao: bool) -> ParsedStatement:
    """Deixa a fatura falando a mesma lingua do resto do sistema.

    Mexe no `statement` recebido e o devolve, para ficar legivel no lugar onde e
    chamado. Cada correcao deixa um aviso: a tela de conferencia e onde ele
    descobre o que o sistema entendeu do arquivo, e correcao silenciosa em
    dinheiro e a que ninguem confere.
    """
    if not statement.transactions:
        return statement

    # 1. As linhas de resumo saem primeiro: elas mentem na contagem da maioria
    # (na fatura dele, o total era o unico negativo) e nao sao lancamento.
    #
    # O OFX fica de fora desta parte: ali cada lancamento e um bloco <STMTTRN>,
    # nunca um rodape de planilha, e a descricao vem do MEMO - que pode ser o
    # nome de um estabelecimento.
    if statement.file_format != "OFX":
        resumos = [t for t in statement.transactions if _e_resumo(t.description)]
        if resumos:
            statement.transactions = [
                t for t in statement.transactions if not _e_resumo(t.description)
            ]
            statement.warnings.append(
                "Linha de resumo ignorada ("
                + ", ".join(f"{t.description.strip()} {t.amount:.2f}" for t in resumos[:3])
                + "): e a soma das outras, e importada junto cobraria o mes duas vezes."
            )

    if not e_cartao or not statement.transactions:
        return statement

    # 2. O sinal. Fatura com mais entrada que saida e sinal invertido, nao mes de
    # devolucoes.
    entradas = sum(1 for t in statement.transactions if t.direction == TxDirection.ENTRADA)
    saidas = len(statement.transactions) - entradas
    if entradas > saidas:
        statement.transactions = [_inverter(t) for t in statement.transactions]
        statement.warnings.append(
            f"Extrato de cartao: {entradas} das {entradas + saidas} linhas vinham "
            "com o sinal de quem olha a divida (compra positiva). Foram lidas como "
            "gasto; o pagamento da fatura, como entrada. Confira abaixo antes de gravar."
        )

    # 3. Agora que as compras estao do lado certo, da para achar o total que
    # escapou do nome - "LANCAMENTOS 1234" tambem e total em alguns bancos.
    indice = _indice_do_total(statement.transactions)
    if indice is not None:
        total = statement.transactions[indice]
        statement.transactions = [
            t for i, t in enumerate(statement.transactions) if i != indice
        ]
        statement.warnings.append(
            f"A linha de {total.amount:.2f} ({total.description.strip()}) e a soma "
            "das outras - o total da fatura - e foi ignorada para o mes nao ser "
            "cobrado duas vezes."
        )

    return statement
