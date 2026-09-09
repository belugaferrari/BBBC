"""Testes do motor de categorizacao e do aprendizado de fornecedores."""

from decimal import Decimal
from uuid import uuid4

from app.models.enums import TxDirection
from app.services.categorization import (
    Rule,
    TransactionFacts,
    categorize,
    learn_from_correction,
    merchant_key,
    normalize,
)

MERCADO = uuid4()
IMPRESSAO_3D = uuid4()
RESTAURANTE = uuid4()


def facts(description: str, amount: str = "100.00") -> TransactionFacts:
    return TransactionFacts(
        description=description, amount=Decimal(amount), direction=TxDirection.SAIDA
    )


def test_normalize_remove_acento_e_ruido_de_extrato():
    assert normalize("COMPRA CARTAO *BAMBU LAB 12/03") == "bambu lab"
    assert normalize("Padaria Sao Joao LTDA") == "padaria sao joao"


def test_merchant_key_extrai_assinatura_do_fornecedor():
    assert merchant_key("PAG*BAMBULAB STORE 004321") == "pag bambulab store"
    assert merchant_key("SUPERMERCADO ANGELONI 0021") == "supermercado angeloni"


def test_regra_mais_especifica_vence_a_generica():
    rules = [
        Rule(id=uuid4(), pattern="mercado", category_id=MERCADO, priority=100),
        Rule(id=uuid4(), pattern="bambu lab", category_id=IMPRESSAO_3D, priority=50),
    ]
    match = categorize(facts("COMPRA CARTAO BAMBU LAB FILAMENTO"), rules)
    assert match is not None
    assert match.category_id == IMPRESSAO_3D


def test_regra_respeita_filtro_de_valor_e_direcao():
    rule = Rule(
        id=uuid4(),
        pattern="uber",
        category_id=RESTAURANTE,
        direction=TxDirection.SAIDA,
        max_amount=Decimal("50.00"),
    )
    assert categorize(facts("UBER *TRIP", "35.00"), [rule]) is not None
    assert categorize(facts("UBER *TRIP", "180.00"), [rule]) is None


def test_sem_match_a_transacao_fica_para_revisao():
    assert categorize(facts("DEBITO DESCONHECIDO XPTO"), []) is None


def test_correcao_manual_vira_regra_de_fornecedor():
    generica = Rule(id=uuid4(), pattern="bambu", category_id=MERCADO, confidence=Decimal("0.6"))
    nova, enfraquecidas = learn_from_correction(
        facts("COMPRA CARTAO BAMBU LAB FILAMENTO PLA"), IMPRESSAO_3D, [generica]
    )

    assert nova.is_learned
    assert nova.category_id == IMPRESSAO_3D
    assert nova.pattern == "bambu lab filamento"
    assert nova.priority < generica.priority
    # a regra que errou perde confianca
    assert enfraquecidas[0].confidence < generica.confidence


def test_segunda_correcao_reaponta_a_regra_existente_em_vez_de_duplicar():
    aprendida = Rule(
        id=uuid4(),
        pattern="bambu lab filamento",
        category_id=IMPRESSAO_3D,
        is_learned=True,
        confidence=Decimal("0.7"),
    )
    nova, _ = learn_from_correction(
        facts("COMPRA CARTAO BAMBU LAB FILAMENTO PLA"), MERCADO, [aprendida]
    )
    assert nova.id == aprendida.id
    assert nova.category_id == MERCADO
    assert nova.confidence > aprendida.confidence
