"""Extrato de CONTA CORRENTE brasileiro - outro mundo que a fatura de cartao.

Fatura de cartao traz nome de loja: iFood, Uber, Netflix. Extrato de conta
corrente traz sigla de banco e PIX para pessoas. O catalogo so conhecia o
primeiro, e o primeiro extrato de conta corrente de verdade chegou com UMA linha
de catorze sugerida.

Estes testes nasceram desse arquivo. Os nomes aqui sao inventados; o formato das
descricoes e exatamente o que o Itau escreve.
"""

from __future__ import annotations

import os
import uuid
from datetime import date
from decimal import Decimal

import pytest

from app.services.categorization import merchant_key, normalize
from app.services.importers.detect import parse_statement

CABECALHO = (
    "OFXHEADER:100\nDATA:OFXSGML\nVERSION:102\nSECURITY:NONE\n"
    "ENCODING:USASCII\nCHARSET:1252\nCOMPRESSION:NONE\n"
    "OLDFILEUID:NONE\nNEWFILEUID:NONE\n\n"
)


def extrato(lancamentos: str, inicio: str = "20260918", fim: str = "20261001") -> bytes:
    return (
        CABECALHO
        + "<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><CURDEF>BRL\n"
        "<BANKACCTFROM><BANKID>0341<ACCTID>4807478484<ACCTTYPE>CHECKING"
        "</BANKACCTFROM>\n"
        f"<BANKTRANLIST><DTSTART>{inicio}100000[-03:EST]<DTEND>{fim}100000[-03:EST]\n"
        f"{lancamentos}"
        "</BANKTRANLIST>\n"
        "<LEDGERBAL><BALAMT>4222.58<DTASOF>20261002100000[-03:EST]</LEDGERBAL>\n"
        "</STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>\n"
    ).encode("cp1252")


def linha(dia: str, valor: str, fitid: str, memo: str, tipo: str = "DEBIT") -> str:
    return (
        f"<STMTTRN>\n<TRNTYPE>{tipo}\n<DTPOSTED>{dia}100000[-03:EST]\n"
        f"<TRNAMT>{valor}\n<FITID>{fitid}\n<CHECKNUM>{fitid}\n<MEMO>{memo}\n"
        "</STMTTRN>\n"
    )


# ------------------------------------------------- o leitor nao filtra -------
def test_o_leitor_traz_todas_as_linhas_do_arquivo():
    """O primeiro susto foi "li so metade do mes" - e o arquivo e que tinha
    metade. O leitor nao olha DTSTART nem DTEND para decidir o que entra: ele
    traz todo <STMTTRN> que existir. Quem recorta o periodo e o banco, na hora
    de gerar o arquivo."""
    corpo = (
        linha("20260918", "-80.12", "A1", "PIX QRS Pagar Me Pa18 09")
        + linha("20260924", "-3197.13", "A2", "FINANC IMOBILIARIO 040 420")
        + linha("20261001", "4000.00", "A3", "PIX TRANSF ALMIR SO01 10", "CREDIT")
    )
    lido = parse_statement("extrato.ofx", extrato(corpo))

    assert len(lido.transactions) == 3
    assert min(t.booked_on for t in lido.transactions) == date(2026, 9, 18)
    assert max(t.booked_on for t in lido.transactions) == date(2026, 10, 1)


def test_linha_fora_do_periodo_declarado_tambem_entra():
    """Se o banco declara um periodo e escreve uma linha fora dele, a linha vale:
    ela esta no arquivo, e o arquivo e a verdade."""
    corpo = linha("20260815", "-10.00", "B1", "ALGUMA COISA 15 08")
    lido = parse_statement("extrato.ofx", extrato(corpo, inicio="20260918"))

    assert len(lido.transactions) == 1
    assert lido.transactions[0].booked_on == date(2026, 8, 15)


# --------------------------------------- a data colada no fim da descricao ---
@pytest.mark.parametrize(
    ("setembro", "outubro"),
    [
        ("PIX TRANSF KARINA 27 09", "PIX TRANSF KARINA 25 10"),
        # sem espaco antes da data, que e como o Itau trunca nomes longos
        ("PIX TRANSF GEORGET26 09", "PIX TRANSF GEORGET15 10"),
        ("PIX QRS BOOMA ORGAN18 09", "PIX QRS BOOMA ORGAN02 10"),
        ("PIX AUT SEM PARAR 30 09", "PIX AUT SEM PARAR 30 10"),
    ],
)
def test_o_fornecedor_aprendido_atravessa_o_mes(setembro, outubro):
    """O Itau termina a descricao com o dia e o mes.

    Enquanto a data ficava, o padrao aprendido numa correcao nascia com ela
    dentro e so casava naquele dia: ensinar o sistema sobre um fornecedor nao
    servia para o mes seguinte. E o mesmo fornecedor todo mes e exatamente o caso
    que o aprendizado existe para resolver - numa conta corrente, a maior parte
    das linhas e PIX para gente, e regra nenhuma vai adivinhar essas.
    """
    assert merchant_key(setembro) == merchant_key(outubro)
    assert merchant_key(setembro) != ""
    # e a data nao sobrou escondida no meio
    assert not any(ch.isdigit() for ch in merchant_key(setembro))


def test_o_prefixo_de_movimentacao_sai_e_o_fornecedor_fica():
    """'PIX QRS' diz COMO o dinheiro andou, nao PARA QUEM."""
    assert normalize("PIX QRS BOOMA ORGANICOS").startswith("booma")
    assert normalize("PIX TRANSF JOANA").startswith("joana")
    assert normalize("TED RECEBIDA CONSULTORIA").startswith("consultoria")


def test_numero_que_nao_e_data_nao_e_apagado():
    """O recorte da data nao pode comer numero de contrato: 'FINANC IMOBILIARIO
    040 420' tem tres digitos de cada lado, e nao dois."""
    assert "040 420" in normalize("FINANC IMOBILIARIO 040 420")


# ------------------------------------------------ as siglas do extrato -------
@pytest.mark.parametrize(
    ("descricao", "caminho"),
    [
        ("FINANC IMOBILIARIO 040 420", "despesas.financiamentos"),
        ("REND PAGO APLIC AUT MAIS", "receitas.passiva.renda_fixa"),
        ("PIX AUT SEM PARAR 30 09", "despesas.transporte.pedagio_tag"),
        ("TARIFA PACOTE DE SERVICOS", "despesas.gastos_anuais.anuidades"),
    ],
)
def test_sigla_de_extrato_tem_regra(descricao, caminho):
    from uuid import uuid4

    from app.models.enums import TxDirection
    from app.services.categorization import Rule, TransactionFacts, categorize
    from app.services.default_rules import DEFAULT_MERCHANT_RULES, prioridade_de

    porCaminho = {}
    regras = []
    for padrao, destino in DEFAULT_MERCHANT_RULES:
        porCaminho.setdefault(destino, uuid4())
        regras.append(
            Rule(
                id=None,
                pattern=padrao,
                category_id=porCaminho[destino],
                priority=prioridade_de(padrao),
                confidence=Decimal("0.6"),
            )
        )

    achado = categorize(
        TransactionFacts(
            description=descricao,
            amount=Decimal("10"),
            direction=TxDirection.SAIDA,
            account_id=None,
        ),
        regras,
    )
    assert achado is not None, f"{descricao} ficou sem regra"
    assert achado.category_id == porCaminho[caminho], (
        f"{descricao} casou com outra categoria"
    )


def test_o_rendimento_vence_a_aplicacao_no_empate():
    """"REND PAGO APLIC AUT MAIS" casa com 'rend pago' (receita) e com
    'aplic aut' (transferencia), e as duas tem nove letras. Empate exato e pior
    que erro: a resposta passaria a depender da ordem em que o banco devolveu as
    regras."""
    from app.services.default_rules import prioridade_de

    assert prioridade_de("rend pago") < prioridade_de("aplic aut")


# ------------------------------------------- o aprendizado, de ponta a ponta -
pytestmark_integracao = pytest.mark.skipif(
    not os.getenv("BBBC_TEST_DATABASE_URL"),
    reason="defina BBBC_TEST_DATABASE_URL para rodar a integracao",
)


@pytestmark_integracao
def test_corrigir_um_pix_em_setembro_resolve_o_de_outubro():
    """O caso que torna a conta corrente utilizavel.

    Nenhuma regra vai adivinhar para quem e um PIX. O que resolve e corrigir uma
    vez e o sistema lembrar - e so lembra se o padrao aprendido nao carregar a
    data daquele dia dentro.
    """
    from fastapi.testclient import TestClient
    from sqlalchemy import text

    from app.cli import seed_family
    from app.db.session import SessionLocal
    from app.main import app

    sufixo = uuid.uuid4().hex[:8]
    email = f"felipe.cc.{sufixo}@exemplo.com"
    family_id = seed_family(
        name=f"Familia {sufixo}",
        titular="Felipe",
        titular_email=email,
        titular_password="segredo-de-teste",
        conjuge="Clarissa",
        conjuge_email=f"clarissa.cc.{sufixo}@exemplo.com",
        conjuge_password="segredo-de-teste",
        dependentes=["Filha"],
    )
    with TestClient(app) as client:
        auth = client.post(
            "/api/v1/auth/login", json={"email": email, "password": "segredo-de-teste"}
        ).json()
        headers = {"Authorization": f"Bearer {auth['access_token']}"}
        conta = client.post(
            "/api/v1/accounts",
            json={"name": "Itau", "type": "CONTA_CORRENTE"},
            headers=headers,
        ).json()
        with SessionLocal() as db:

            def categoria(caminho: str) -> str:
                return str(
                    db.execute(
                        text(
                            "SELECT id FROM categories WHERE family_id = :f"
                            " AND path = CAST(:p AS ltree)"
                        ),
                        {"f": family_id, "p": caminho},
                    ).scalar_one()
                )

            diarista = categoria("despesas.limpeza.diarista")
            a_definir = categoria("despesas.a_definir")

        def lancar(dia: str, descricao: str):
            return client.post(
                "/api/v1/transactions",
                json={
                    "account_id": conta["id"],
                    "booked_on": dia,
                    "amount": "3468.00",
                    "direction": "SAIDA",
                    "description": descricao,
                },
                headers=headers,
            ).json()

        setembro = lancar("2026-09-28", "PIX TRANSF KARINA 27 09")
        # Nenhuma regra devia adivinhar um PIX - e sem regra o lancamento vai
        # para "A definir", que e onde ele fica visivel para ser corrigido.
        assert setembro["category_id"] == a_definir, (
            "sem regra, o PIX devia cair em 'A definir'"
        )

        client.patch(
            f"/api/v1/transactions/{setembro['id']}",
            json={"category_id": diarista, "learn_rule": True},
            headers=headers,
        )

        outubro = lancar("2026-10-25", "PIX TRANSF KARINA 25 10")
        assert outubro["category_id"] == diarista
