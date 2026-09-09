"""Leitura de extratos: OFX, CSV e PDF.

Os tres arquivos de exemplo em `db/samples/` descrevem o MESMO extrato. Se os
tres leitores nao chegarem ao mesmo resultado, um deles esta errado - e esse e
o teste mais util deste modulo.
"""

from __future__ import annotations

import pathlib
from datetime import date
from decimal import Decimal

import pytest

from app.models.enums import TxDirection
from app.services.importers.base import ParsedTransaction, StatementParseError, fingerprint
from app.services.importers.detect import detect_format, parse_statement
from app.services.importers.parsing import (
    AmountFormatError,
    DateFormatError,
    parse_amount,
    parse_date,
)

SAMPLES = pathlib.Path(__file__).resolve().parent.parent / "db" / "samples"
ARQUIVOS = ["extrato-exemplo.ofx", "extrato-exemplo.csv", "extrato-exemplo.pdf"]


def ler(nome: str) -> bytes:
    return (SAMPLES / nome).read_bytes()


# ---------------------------------------------------------------- numeros ---
@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("1.234,56", "1234.56"),      # brasileiro
        ("1,234.56", "1234.56"),      # americano
        ("R$ 1.234,56", "1234.56"),
        ("-89,90", "-89.90"),
        ("(1.234,56)", "-1234.56"),   # contabil
        ("1234,56-", "-1234.56"),     # sinal no fim
        ("4200", "4200"),
        ("1,50", "1.50"),
    ],
)
def test_valores_em_varios_formatos(texto, esperado):
    assert parse_amount(texto) == Decimal(esperado)


def test_valor_invalido_falha_alto():
    with pytest.raises(AmountFormatError):
        parse_amount("saldo anterior")


@pytest.mark.parametrize(
    "texto", ["05/09/2026", "05/09/26", "2026-09-05", "05.09.2026", "05092026"]
)
def test_datas_em_varios_formatos(texto):
    assert parse_date(texto) == date(2026, 9, 5)


def test_data_sem_ano_usa_a_referencia():
    """Extrato de cartao costuma escrever so `05/set`."""
    assert parse_date("05/set", reference_year=2026) == date(2026, 9, 5)


def test_data_invalida_falha_alto():
    with pytest.raises(DateFormatError):
        parse_date("historico")


# ---------------------------------------------------------------- formato ---
@pytest.mark.parametrize(
    ("nome", "esperado"),
    [
        ("extrato-exemplo.ofx", "OFX"),
        ("extrato-exemplo.csv", "CSV"),
        ("extrato-exemplo.pdf", "PDF"),
    ],
)
def test_deteccao_de_formato_pelo_conteudo(nome, esperado):
    assert detect_format(nome, ler(nome)) == esperado


def test_extensao_mentirosa_nao_engana():
    """Arquivo salvo como .txt mas que e OFX por dentro."""
    assert detect_format("extrato.txt", ler("extrato-exemplo.ofx")) == "OFX"


def test_formato_desconhecido_e_recusado():
    with pytest.raises(StatementParseError):
        parse_statement("foto.jpg", b"\xff\xd8\xff\xe0conteudo binario")


# ---------------------------------------------------------------- leitura ---
@pytest.mark.parametrize("nome", ARQUIVOS)
def test_os_tres_formatos_leem_o_mesmo_extrato(nome):
    extrato = parse_statement(nome, ler(nome))

    assert len(extrato.transactions) == 5
    assert extrato.period_start == date(2026, 8, 5)
    assert extrato.period_end == date(2026, 8, 20)

    entradas = sum(
        t.amount for t in extrato.transactions if t.direction == TxDirection.ENTRADA
    )
    saidas = sum(t.amount for t in extrato.transactions if t.direction == TxDirection.SAIDA)
    assert entradas == Decimal("43000.00")
    assert saidas == Decimal("11925.90")


@pytest.mark.parametrize("nome", ARQUIVOS)
def test_descricoes_sobrevivem_a_leitura(nome):
    extrato = parse_statement(nome, ler(nome))
    textos = " | ".join(t.description.upper() for t in extrato.transactions)
    for esperado in ("PRO LABORE", "ANGELONI", "COLEGIO", "BAMBU LAB", "LUCROS"):
        assert esperado in textos


def test_pdf_ignora_saldo_e_rodape():
    """`SALDO ANTERIOR`, `SALDO FINAL` e `Pagina 1 de 1` nao sao lancamentos."""
    extrato = parse_statement("extrato-exemplo.pdf", ler("extrato-exemplo.pdf"))
    textos = " ".join(t.description.upper() for t in extrato.transactions)
    assert "SALDO" not in textos
    assert "PAGINA" not in textos


def test_pdf_avisa_que_a_leitura_e_aproximada():
    extrato = parse_statement("extrato-exemplo.pdf", ler("extrato-exemplo.pdf"))
    assert any("aproximacao" in aviso for aviso in extrato.warnings)


def test_csv_ignora_cabecalho_do_banco_e_linha_de_saldo():
    """O arquivo tem tres linhas de cabecalho antes das colunas e um rodape."""
    extrato = parse_statement("extrato-exemplo.csv", ler("extrato-exemplo.csv"))
    assert len(extrato.transactions) == 5
    assert extrato.transactions[0].document == "000123"


def test_ofx_traz_o_identificador_do_banco():
    extrato = parse_statement("extrato-exemplo.ofx", ler("extrato-exemplo.ofx"))
    assert extrato.transactions[0].document == "2026080500001"
    assert extrato.account_hint == "56789-0"


def test_csv_com_colunas_de_debito_e_credito_separadas():
    conteudo = (
        b"Data,Descricao,Debito,Credito\n"
        b"05/08/2026,Salario,,28000.00\n"
        b"06/08/2026,Mercado,4235.90,\n"
    )
    extrato = parse_statement("banco.csv", conteudo)

    assert [t.direction for t in extrato.transactions] == [
        TxDirection.ENTRADA,
        TxDirection.SAIDA,
    ]
    assert extrato.transactions[1].amount == Decimal("4235.90")


def test_csv_sem_cabecalho_e_deduzido_pelo_conteudo():
    conteudo = (
        b"05/08/2026;PRO LABORE;28.000,00\n"
        b"06/08/2026;MERCADO;-4.235,90\n"
    )
    extrato = parse_statement("sem-cabecalho.csv", conteudo)

    assert len(extrato.transactions) == 2
    assert any("deduzidas" in aviso for aviso in extrato.warnings)


def test_arquivo_vazio_e_recusado():
    with pytest.raises(StatementParseError):
        parse_statement("vazio.csv", b"")


# ------------------------------------------------------------ dedup ---------
def _tx(**kwargs) -> ParsedTransaction:
    base = {
        "booked_on": date(2026, 8, 6),
        "amount": Decimal("4235.90"),
        "direction": TxDirection.SAIDA,
        "description": "SUPERMERCADO ANGELONI",
    }
    return ParsedTransaction(**{**base, **kwargs})


def test_impressao_digital_ignora_ruido_da_descricao():
    """O mesmo lancamento exportado em formatos diferentes tem a mesma digital."""
    import uuid

    conta = uuid.uuid4()
    assert fingerprint(conta, _tx()) == fingerprint(
        conta, _tx(description="Supermercado  Angeloni")
    )


def test_impressao_digital_separa_lancamentos_diferentes():
    import uuid

    conta = uuid.uuid4()
    digitais = {
        fingerprint(conta, _tx()),
        fingerprint(conta, _tx(amount=Decimal("4235.91"))),
        fingerprint(conta, _tx(booked_on=date(2026, 8, 7))),
        fingerprint(conta, _tx(direction=TxDirection.ENTRADA)),
        fingerprint(conta, _tx(description="OUTRO MERCADO")),
    }
    assert len(digitais) == 5


def test_contas_diferentes_nao_colidem():
    import uuid

    assert fingerprint(uuid.uuid4(), _tx()) != fingerprint(uuid.uuid4(), _tx())


def test_identificador_do_banco_manda_quando_existe():
    """Com FITID, dois lancamentos identicos no mesmo dia continuam distintos."""
    import uuid

    conta = uuid.uuid4()
    assert fingerprint(conta, _tx(document="A1")) != fingerprint(conta, _tx(document="A2"))
