"""OFX como banco brasileiro realmente escreve.

O padrao OFX e uma coisa; o arquivo que o banco entrega e outra. Estes testes
nasceram de um extrato de verdade que o sistema recusou, e cada um guarda uma
liberdade que os bancos tomam e que o leitor tem de aguentar:

  * agregado sem etiqueta de fechamento (Banco do Brasil, Caixa);
  * encoding declarado no cabecalho que nao e o usado no corpo;
  * UTF-8 com BOM, e UTF-16 com e sem BOM;
  * o arquivo inteiro numa unica linha;
  * OFX 2.x, que e XML de verdade.

Os arquivos sao montados aqui, no corpo do teste, e nao guardados em `samples/`:
o que cada um testa e a DEFORMIDADE que ele carrega, e ela tem de estar legivel
ao lado da asserção.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.models.enums import TxDirection
from app.services.importers.base import StatementParseError
from app.services.importers.detect import parse_statement

CABECALHO_1X = (
    "OFXHEADER:100\n"
    "DATA:OFXSGML\n"
    "VERSION:102\n"
    "SECURITY:NONE\n"
    "ENCODING:USASCII\n"
    "CHARSET:1252\n"
    "COMPRESSION:NONE\n"
    "OLDFILEUID:NONE\n"
    "NEWFILEUID:NONE\n\n"
)


def corpo(lancamentos: str, acctid: str = "1234567890") -> str:
    return (
        "<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><CURDEF>BRL\n"
        f"<BANKACCTFROM><BANKID>341<ACCTID>{acctid}<ACCTTYPE>CHECKING</BANKACCTFROM>\n"
        "<BANKTRANLIST><DTSTART>20260801<DTEND>20260831\n"
        f"{lancamentos}"
        "</BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>\n"
    )


COM_FECHAMENTO = (
    "<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20260805120000[-03:EST]"
    "<TRNAMT>-189.90<FITID>A1<MEMO>SUPERMERCADO ANGELONI 023</STMTTRN>\n"
    "<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20260806<TRNAMT>28000.00"
    "<FITID>A2<MEMO>PRO LABORE</STMTTRN>\n"
)

# A deformidade: nenhum </STMTTRN>. O segundo lancamento abre em cima do primeiro.
SEM_FECHAMENTO = (
    "<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20260803<TRNAMT>-89,50"
    "<FITID>B1<MEMO>POSTO IPIRANGA LTDA\n"
    "<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20260810<TRNAMT>-3500,00"
    "<FITID>B2<MEMO>COLEGIO SAO JOSE MENSALIDADE\n"
)


# ------------------------------------------- etiqueta sem fechamento ---------
def test_agregado_sem_fechamento_e_lido():
    """Banco do Brasil e Caixa nao escrevem </STMTTRN>.

    Procurar pelo fechamento nao achava lancamento nenhum, e o arquivo inteiro
    era recusado com "o arquivo e mesmo um OFX?" - para um OFX legitimo.
    """
    arquivo = (CABECALHO_1X + corpo(SEM_FECHAMENTO)).encode("cp1252")
    extrato = parse_statement("extrato.ofx", arquivo)

    assert len(extrato.transactions) == 2
    primeiro, segundo = extrato.transactions
    assert primeiro.booked_on == date(2026, 8, 3)
    assert primeiro.amount == Decimal("89.50")
    assert primeiro.description == "POSTO IPIRANGA LTDA"
    assert segundo.amount == Decimal("3500.00")
    assert segundo.description == "COLEGIO SAO JOSE MENSALIDADE"


def test_sem_fechamento_nao_mistura_um_lancamento_no_outro():
    """O risco do recorte sem fechamento: o bloco engolir o lancamento seguinte.

    Se engolisse, o primeiro ficaria com o FITID ou o valor do segundo - e dois
    lancamentos diferentes passariam a ter a mesma impressao digital, o que
    estragaria a deduplicacao sem dar erro.
    """
    arquivo = (CABECALHO_1X + corpo(SEM_FECHAMENTO)).encode("cp1252")
    extrato = parse_statement("extrato.ofx", arquivo)

    assert [t.document for t in extrato.transactions] == ["B1", "B2"]
    assert "COLEGIO" not in extrato.transactions[0].description


def test_com_e_sem_fechamento_dao_o_mesmo_resultado():
    """O mesmo extrato escrito das duas formas tem de ser lido igual."""
    mesmos_dados_fechados = (
        "<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20260803<TRNAMT>-89,50"
        "<FITID>B1<MEMO>POSTO IPIRANGA LTDA</STMTTRN>\n"
        "<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20260810<TRNAMT>-3500,00"
        "<FITID>B2<MEMO>COLEGIO SAO JOSE MENSALIDADE</STMTTRN>\n"
    )
    aberto = parse_statement(
        "a.ofx", (CABECALHO_1X + corpo(SEM_FECHAMENTO)).encode("cp1252")
    )
    fechado = parse_statement(
        "b.ofx", (CABECALHO_1X + corpo(mesmos_dados_fechados)).encode("cp1252")
    )

    assert [
        (t.booked_on, t.amount, t.direction, t.description, t.document)
        for t in aberto.transactions
    ] == [
        (t.booked_on, t.amount, t.direction, t.description, t.document)
        for t in fechado.transactions
    ]


# ------------------------------------------------------------ encoding -------
ACENTOS = (
    "<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20260807<TRNAMT>-45.00"
    "<FITID>C1<MEMO>Farmácia São João</STMTTRN>\n"
)


def test_cabecalho_diz_1252_mas_o_corpo_e_utf8():
    """A mentira mais comum do formato.

    Quase todo banco escreve ENCODING:USASCII e CHARSET:1252 no cabecalho, e boa
    parte grava UTF-8 no corpo. Obedecer o cabecalho devolve "FarmÃ¡cia" - e e
    esse texto que alimenta a sugestao de categoria, entao o estrago nao fica no
    visual: a regra 'farmacia' deixa de casar.
    """
    arquivo = (CABECALHO_1X + corpo(ACENTOS)).encode("utf-8")
    extrato = parse_statement("extrato.ofx", arquivo)

    assert extrato.transactions[0].description == "Farmácia São João"


def test_corpo_realmente_em_1252_tambem_e_lido():
    """O caminho honesto continua funcionando."""
    arquivo = (CABECALHO_1X + corpo(ACENTOS)).encode("cp1252")
    extrato = parse_statement("extrato.ofx", arquivo)

    assert extrato.transactions[0].description == "Farmácia São João"


def test_utf8_com_bom():
    arquivo = b"\xef\xbb\xbf" + (CABECALHO_1X + corpo(ACENTOS)).encode("utf-8")
    extrato = parse_statement("extrato.ofx", arquivo)

    assert extrato.transactions[0].description == "Farmácia São João"


@pytest.mark.parametrize("codec", ["utf-16", "utf-16-le", "utf-16-be"])
def test_utf16_com_e_sem_bom(codec):
    """UTF-16 vira byte zero intercalado: sem tratar, nem a etiqueta <STMTTRN>
    aparece, e o arquivo e recusado como se nao fosse OFX."""
    arquivo = (CABECALHO_1X + corpo(ACENTOS)).encode(codec)
    extrato = parse_statement("extrato.ofx", arquivo)

    assert len(extrato.transactions) == 1
    assert extrato.transactions[0].description == "Farmácia São João"


# -------------------------------------------------- forma do arquivo ---------
def test_arquivo_todo_numa_linha():
    """Alguns bancos exportam sem quebra de linha nenhuma."""
    inteiro = (CABECALHO_1X + corpo(COM_FECHAMENTO)).replace("\n", "")
    extrato = parse_statement("extrato.ofx", inteiro.encode("cp1252"))

    assert len(extrato.transactions) == 2
    assert extrato.transactions[0].description == "SUPERMERCADO ANGELONI 023"


def test_ofx_2x_que_e_xml_de_verdade():
    arquivo = (
        b'<?xml version="1.0" encoding="UTF-8"?>\n'
        b'<?OFX OFXHEADER="200" VERSION="211" SECURITY="NONE"?>\n'
        b"<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS>\n"
        b"<CURDEF>BRL</CURDEF>\n"
        b"<BANKACCTFROM><BANKID>033</BANKID><ACCTID>13000123</ACCTID>"
        b"<ACCTTYPE>CHECKING</ACCTTYPE></BANKACCTFROM>\n"
        b"<BANKTRANLIST><DTSTART>20260801</DTSTART><DTEND>20260831</DTEND>\n"
        b"<STMTTRN><TRNTYPE>DEBIT</TRNTYPE><DTPOSTED>20260815</DTPOSTED>"
        b"<TRNAMT>-219.47</TRNAMT><FITID>D1</FITID>"
        b"<NAME>CONDOMINIO EDIFICIO</NAME><MEMO>Taxa de agosto</MEMO></STMTTRN>\n"
        b"</BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>\n"
    )
    extrato = parse_statement("extrato.ofx", arquivo)

    assert len(extrato.transactions) == 1
    lancamento = extrato.transactions[0]
    assert lancamento.booked_on == date(2026, 8, 15)
    assert lancamento.amount == Decimal("219.47")
    assert lancamento.direction is TxDirection.SAIDA
    # NAME traz o fornecedor e MEMO o complemento: os dois entram
    assert lancamento.description == "CONDOMINIO EDIFICIO - Taxa de agosto"


def test_decimal_com_virgula_no_trnamt():
    """O padrao pede ponto, e banco brasileiro as vezes manda virgula."""
    arquivo = (
        CABECALHO_1X
        + corpo(
            "<STMTTRN><DTPOSTED>20260805<TRNAMT>-1.234,56"
            "<FITID>E1<MEMO>ALGUMA COISA</STMTTRN>\n"
        )
    ).encode("cp1252")
    extrato = parse_statement("extrato.ofx", arquivo)

    assert extrato.transactions[0].amount == Decimal("1234.56")
    assert extrato.transactions[0].direction is TxDirection.SAIDA


def test_numero_da_conta_e_capturado_para_conferencia():
    arquivo = (CABECALHO_1X + corpo(COM_FECHAMENTO, acctid="00099887-1")).encode("cp1252")
    extrato = parse_statement("extrato.ofx", arquivo)

    assert extrato.account_hint == "00099887-1"


# ------------------------------------------------------ o que ainda falha ----
def test_arquivo_que_nao_e_ofx_continua_sendo_recusado():
    """O recorte mais tolerante nao pode passar a aceitar qualquer coisa."""
    with pytest.raises(StatementParseError):
        parse_statement("coisa.ofx", b"<html><body>pagina de erro do banco</body></html>")


def test_ofx_sem_lancamento_nenhum_e_recusado_com_motivo():
    arquivo = (CABECALHO_1X + corpo("")).encode("cp1252")
    with pytest.raises(StatementParseError, match="STMTTRN"):
        parse_statement("extrato.ofx", arquivo)
