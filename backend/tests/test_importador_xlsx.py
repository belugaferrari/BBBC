"""Extrato em planilha do Excel.

"Tenho aqui planilhas (xlsx) com o extrato do cartao, mas o sistema
aparentemente nao le esse tipo de arquivo (so csv)."

A planilha de teste e montada aqui, a mao, em vez de entrar no repositorio como
arquivo binario - assim da para ver o que esta sendo testado, e as duas
armadilhas do formato ficam escritas:

  * o Excel guarda data como NUMERO (46270) e diz em outro lugar que aquela
    celula e para ser vista como data;
  * celula vazia NAO ocupa lugar no XML - cada celula traz o proprio endereco.
    Ler em sequencia desalinharia tudo a partir do primeiro buraco.
"""

from __future__ import annotations

import zipfile
from datetime import date
from decimal import Decimal
from io import BytesIO

import pytest

from app.models.enums import TxDirection
from app.services.importers.base import StatementParseError
from app.services.importers.detect import detect_format, parse_statement
from app.services.importers.xlsx_statement import celulas, parse

_CONTENT_TYPES = (
    '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/'
    'package/2006/content-types">'
    '<Default Extension="xml" ContentType="application/xml"/></Types>'
)
_RELS = (
    '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/'
    'package/2006/relationships"><Relationship Id="rId1" Target="xl/workbook.xml" '
    'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
    'officeDocument"/></Relationships>'
)
_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _planilha(linhas: list[list[object]], *, nome_da_aba: str = "sheet7.xml") -> bytes:
    """Monta um .xlsx de verdade: zip + XML, com texto compartilhado e estilo de
    data, que e como o Excel escreve.

    `linhas` aceita str (texto), float/int (numero), date (data) e None (celula
    que NAO existe no XML - o buraco que desalinha leitor ingenuo).
    """
    textos: list[str] = []
    corpo = []
    for numero, linha in enumerate(linhas, start=1):
        celulas_xml = []
        for coluna, valor in enumerate(linha):
            if valor is None:
                continue  # a celula simplesmente nao e escrita
            endereco = f"{chr(ord('A') + coluna)}{numero}"
            if isinstance(valor, date):
                serial = (valor - date(1899, 12, 30)).days
                # s="1" aponta para o estilo de data no styles.xml abaixo
                celulas_xml.append(f'<c r="{endereco}" s="1"><v>{serial}</v></c>')
            elif isinstance(valor, (int, float)):
                celulas_xml.append(f'<c r="{endereco}"><v>{valor}</v></c>')
            else:
                if valor not in textos:
                    textos.append(valor)
                celulas_xml.append(
                    f'<c r="{endereco}" t="s"><v>{textos.index(valor)}</v></c>'
                )
        corpo.append(f'<row r="{numero}">{"".join(celulas_xml)}</row>')

    aba = f'<?xml version="1.0"?><worksheet xmlns="{_NS}"><sheetData>{"".join(corpo)}</sheetData></worksheet>'
    compartilhados = (
        f'<?xml version="1.0"?><sst xmlns="{_NS}" count="{len(textos)}">'
        + "".join(f"<si><t>{t}</t></si>" for t in textos)
        + "</sst>"
    )
    estilos = (
        f'<?xml version="1.0"?><styleSheet xmlns="{_NS}">'
        '<numFmts count="1"><numFmt numFmtId="164" formatCode="dd/mm/yyyy"/></numFmts>'
        '<cellXfs count="2"><xf numFmtId="0"/><xf numFmtId="164"/></cellXfs>'
        "</styleSheet>"
    )
    livro = (
        f'<?xml version="1.0"?><workbook xmlns="{_NS}" xmlns:r="{_NS_R}">'
        f'<sheets><sheet name="Fatura" sheetId="1" r:id="rId9"/></sheets></workbook>'
    )
    rels_do_livro = (
        f'<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/'
        f'package/2006/relationships"><Relationship Id="rId9" '
        f'Target="worksheets/{nome_da_aba}" Type="{_NS_R}/worksheet"/></Relationships>'
    )

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("[Content_Types].xml", _CONTENT_TYPES)
        zf.writestr("_rels/.rels", _RELS)
        zf.writestr("xl/workbook.xml", livro)
        zf.writestr("xl/_rels/workbook.xml.rels", rels_do_livro)
        zf.writestr("xl/sharedStrings.xml", compartilhados)
        zf.writestr("xl/styles.xml", estilos)
        zf.writestr(f"xl/worksheets/{nome_da_aba}", aba)
        # uma segunda aba, que o leitor NAO deve pegar por engano
        zf.writestr("xl/worksheets/sheet1.xml", aba.replace("</sheetData>", "</sheetData>"))
    return buffer.getvalue()


FATURA = [
    ["Itau Cartoes", None, None],
    ["Fatura de setembro/2026", None, None],
    [None, None, None],
    ["Data", "Lançamento", "Valor"],
    [date(2026, 9, 3), "POSTO SHELL AV BRASIL", -245.90],
    [date(2026, 9, 12), "IFOOD CLUB PARCELA 01/03", -189.0],
    [date(2026, 9, 10), "PAGAMENTO EFETUADO", 4320.15],
    ["", "SALDO FINAL", -434.90],
]


def test_le_a_fatura_em_planilha():
    extrato = parse(_planilha(FATURA))
    assert extrato.file_format == "XLSX"
    assert len(extrato.transactions) == 3

    primeira = extrato.transactions[0]
    assert primeira.booked_on == date(2026, 9, 3)
    assert primeira.amount == Decimal("245.90")
    assert primeira.direction == TxDirection.SAIDA
    assert primeira.description == "POSTO SHELL AV BRASIL"


def test_a_data_sai_do_numero_e_do_estilo():
    """Sem ler o estilo da celula, 03/09/2026 viraria o numero 46268.

    A linha e procurada, e nao contada: o leitor descarta a linha totalmente
    vazia da planilha, entao indice fixo aqui testaria a contagem do teste e nao
    o que importa.
    """
    linhas = celulas(_planilha(FATURA))
    datas = [linha[0] for linha in linhas if linha and linha[0]]
    assert "03/09/2026" in datas
    assert "12/09/2026" in datas
    # e o numero de serie nao vaza para lugar nenhum
    assert not any("46268" in celula for linha in linhas for celula in linha)


def test_o_credito_vem_como_entrada():
    extrato = parse(_planilha(FATURA))
    pagamento = next(t for t in extrato.transactions if "PAGAMENTO" in t.description)
    assert pagamento.direction == TxDirection.ENTRADA
    assert pagamento.amount == Decimal("4320.15")


def test_a_linha_de_saldo_final_nao_vira_lancamento():
    extrato = parse(_planilha(FATURA))
    assert all("SALDO FINAL" not in t.description for t in extrato.transactions)


def test_celula_vazia_nao_desalinha_as_colunas():
    """A armadilha do formato: a celula em branco nao existe no XML. Lido em
    sequencia, o valor da linha seguinte entraria na coluna da descricao."""
    com_buraco = [
        ["Data", "Documento", "Lançamento", "Valor"],
        [date(2026, 9, 3), None, "POSTO SHELL", -245.90],
        [date(2026, 9, 4), "000123", "MERCADO", -100.00],
    ]
    extrato = parse(_planilha(com_buraco))
    assert [t.description for t in extrato.transactions] == ["POSTO SHELL", "MERCADO"]
    assert [t.amount for t in extrato.transactions] == [Decimal("245.90"), Decimal("100.00")]


def test_segue_a_aba_que_a_planilha_declara():
    """Ordem alfabetica nao serve: sheet10 viria antes de sheet2, e a primeira aba
    pode nem se chamar sheet1."""
    extrato = parse(_planilha(FATURA, nome_da_aba="sheet7.xml"))
    assert len(extrato.transactions) == 3


def test_colunas_de_debito_e_credito_separadas():
    """Metade dos bancos exporta assim."""
    separadas = [
        ["Data", "Histórico", "Débito", "Crédito"],
        [date(2026, 9, 3), "POSTO SHELL", 245.90, None],
        [date(2026, 9, 5), "ESTORNO", None, 50.00],
    ]
    extrato = parse(_planilha(separadas))
    assert [t.direction for t in extrato.transactions] == [
        TxDirection.SAIDA,
        TxDirection.ENTRADA,
    ]


def test_o_formato_e_reconhecido_pelo_conteudo():
    conteudo = _planilha(FATURA)
    assert detect_format("fatura.xlsx", conteudo) == "XLSX"
    # nome errado, conteudo certo: o conteudo decide
    assert detect_format("fatura.txt", conteudo) == "XLSX"
    extrato = parse_statement("fatura.xlsx", conteudo)
    assert extrato.file_format == "XLSX"


def test_xls_antigo_explica_o_que_fazer():
    antigo = bytes.fromhex("d0cf11e0a1b11ae1") + b"\x00" * 100
    with pytest.raises(StatementParseError) as erro:
        detect_format("fatura.xls", antigo)
    assert "salve como .xlsx" in str(erro.value)


def test_arquivo_quebrado_nao_derruba():
    with pytest.raises(StatementParseError):
        parse(b"PK\x03\x04 isto nao e um zip de verdade")


def test_planilha_sem_lancamento_reclama():
    vazia = [["Relatorio"], ["sem nada util aqui"]]
    with pytest.raises(StatementParseError):
        parse(_planilha(vazia))


# ---------------------------------------------------------------------------
# A planilha dele: total negativo na frente, compras positivas
# ---------------------------------------------------------------------------
FATURA_COM_SINAL_DA_DIVIDA = [
    ["Itau Cartoes", None, None],
    ["Fatura de setembro/2026", None, None],
    ["Data", "Lançamento", "Valor"],
    [date(2026, 9, 1), "TOTAL DA FATURA", -1035.80],
    [date(2026, 9, 3), "POSTO SHELL AV BRASIL", 245.90],
    [date(2026, 9, 12), "IFOOD CLUB", 189.00],
    [date(2026, 9, 15), "SUPERMERCADO PAO DE ACUCAR", 600.90],
]


def test_a_planilha_de_fatura_com_compra_positiva_vira_gasto():
    """O caminho inteiro do arquivo dele: planilha -> leitor -> ajuste da fatura.

    O leitor de planilha aplica a regra do extrato de CONTA (positivo = entrou),
    que e a certa lá e a errada aqui. Quem conserta e o ajuste da fatura, e e ele
    que esta sendo exercitado junto com o leitor - porque o problema so aparece
    com os dois no mesmo caminho.
    """
    from app.services.importers import fatura

    extrato = parse(_planilha(FATURA_COM_SINAL_DA_DIVIDA))
    # como o leitor entrega, antes do ajuste: tudo ao contrario
    assert sum(1 for t in extrato.transactions if t.direction == TxDirection.ENTRADA) == 3

    ajustado = fatura.ajustar(extrato, e_cartao=True)
    assert [t.direction for t in ajustado.transactions] == [TxDirection.SAIDA] * 3
    assert sum(t.amount for t in ajustado.transactions) == Decimal("1035.80")
    assert all("TOTAL" not in t.description for t in ajustado.transactions)


# ---------------------------------------------------------------------------
# A fatura do Itau como ela e de verdade
# ---------------------------------------------------------------------------
# O formato foi copiado de uma fatura real (os dados, nao: nome, agencia e conta
# aqui sao inventados). O que importa e o FORMATO, e ele tem tres coisas que
# nenhuma outra planilha tinha:
#
#   * um cabecalho com varias linhas antes da tabela, incluindo uma tabela
#     propria com "Vencimento" e a data em que a fatura foi paga;
#   * uma COLUNA de parcelamento ("Parcela 2 de 4"), separada da descricao;
#   * compras positivas, pagamento e estornos negativos.
FATURA_ITAU = [
    ["", "Nome", "Fulana De Tal"],
    ["", "Agência", "0000"],
    ["", "Conta", "00000-0"],
    ["", "Fatura Paga - Janeiro/2026"],
    ["", "Cartão", "", "", "", "", "Valor", "", "Vencimento", ""],
    ["", "Banco Cartao - final 0000", "", "Você pagou R$ 1.000,00 de", "", "",
     1000.00, "", date(2026, 1, 9), ""],
    ["", "Lançamentos"],
    ["", "Data", "Lançamento", "Parcelamento", "Valor", "", "Titularidade"],
    ["", date(2025, 12, 9), "Pagamento Efetuado", "", -900.00, "", "Titular"],
    ["", date(2025, 12, 20), "Mercado Do Bairro", "", 300.00, "", "Titular"],
    ["", date(2025, 12, 15), "Loja De Moveis", "Parcela 1 de 4", 250.00, "", "Titular"],
    # a parcela velha: comprada em julho, cobrada AGORA
    ["", date(2025, 7, 4), "Assinatura Anual", "Parcela 6 de 6", 500.00, "", "Titular"],
    ["", date(2025, 12, 12), "Estorno De Anuidade", "", -50.00, "", "Titular"],
]


def test_le_o_vencimento_que_a_fatura_declara():
    """E a informacao mais valiosa do arquivo, e estava sendo ignorada.

    Com ela, nao e preciso deduzir em que mes cada compra sai da conta a partir
    do dia de fechamento: toda compra de uma fatura e cobrada no dia em que a
    fatura e paga.
    """
    extrato = parse(_planilha(FATURA_ITAU))
    assert extrato.vencimento == date(2026, 1, 9)


def test_le_o_parcelamento_da_coluna_propria():
    """O Itau escreve "Parcela 2 de 4" numa COLUNA, e nao na descricao.

    Lendo so a descricao, essas linhas entravam como compra avulsa - e a parcela
    de uma compra de julho ia parar em agosto, num mes em que nada saiu da
    conta por causa dela.
    """
    extrato = parse(_planilha(FATURA_ITAU))
    por_descricao = {t.description: t for t in extrato.transactions}

    moveis = por_descricao["Loja De Moveis"]
    assert (moveis.installment_no, moveis.installment_total) == (1, 4)

    antiga = por_descricao["Assinatura Anual"]
    assert (antiga.installment_no, antiga.installment_total) == (6, 6)

    # e a linha sem parcelamento continua sem parcela nenhuma
    assert por_descricao["Mercado Do Bairro"].installment_no is None


def test_a_soma_das_compras_bate_com_a_fatura():
    """As compras somam o bruto; o liquido que a fatura cobra desconta os
    estornos. Os dois numeros existem, e nenhum dos dois e o outro."""
    from app.services.importers import fatura as ajuste

    extrato = ajuste.ajustar(parse(_planilha(FATURA_ITAU)), e_cartao=True)
    compras = [t for t in extrato.transactions if t.direction == TxDirection.SAIDA]
    creditos = [t for t in extrato.transactions if t.direction == TxDirection.ENTRADA]

    assert sum(t.amount for t in compras) == Decimal("1050.00")
    # o pagamento da fatura anterior e o estorno, cada um com o seu sinal
    assert {t.description for t in creditos} == {
        "Pagamento Efetuado",
        "Estorno De Anuidade",
    }
