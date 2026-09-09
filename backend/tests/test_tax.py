"""Testes do motor de IR - o modulo onde um erro custa dinheiro de verdade."""

from decimal import Decimal
from uuid import uuid4

import pytest

from app.models.enums import IRDeductionType, IRTreatment, TaxModel
from app.services.tax import (
    DeductibleExpense,
    IncomeItem,
    MissingTaxParameter,
    TaxpayerYear,
    assess_year,
    carne_leao,
    classify_incomes,
    compute_deductions,
    deduction_benefit,
    progressive_tax,
    project_year,
)

FILHA_1, FILHA_2 = uuid4(), uuid4()


def test_progressive_tax_por_faixa(table_2025):
    assert progressive_tax(Decimal("20000"), table_2025.annual_brackets) == Decimal("0")
    # 60.000 * 27,5% - 10.752,00
    assert progressive_tax(Decimal("60000"), table_2025.annual_brackets) == Decimal("5748.00")


def test_classificacao_separa_tributavel_isento_e_exclusiva():
    totals = classify_incomes(
        (
            IncomeItem(IRTreatment.TRIBUTAVEL_TABELA, Decimal("120000"), Decimal("18000")),
            IncomeItem(IRTreatment.ISENTO_NAO_TRIBUTAVEL, Decimal("200000")),  # lucros
            IncomeItem(IRTreatment.EXCLUSIVA_FONTE, Decimal("9000"), Decimal("1350")),  # CDB
            IncomeItem(IRTreatment.TRIBUTAVEL_CARNE_LEAO, Decimal("30000")),  # leiloes
        )
    )
    assert totals["tributavel"] == Decimal("150000.00")
    assert totals["isento"] == Decimal("200000.00")
    assert totals["exclusiva_fonte"] == Decimal("9000.00")
    assert totals["retido"] == Decimal("19350.00")


def test_teto_de_instrucao_e_aplicado_por_filha(table_2025):
    """O excedente da escola de uma filha nao pode ser aproveitado pela outra."""
    expenses = (
        DeductibleExpense(IRDeductionType.EDUCACAO, Decimal("12000"), FILHA_1, "Filha 1"),
        DeductibleExpense(IRDeductionType.EDUCACAO, Decimal("1500"), FILHA_2, "Filha 2"),
    )
    applied, capped = compute_deductions(expenses, 2, Decimal("200000"), table_2025)

    # 3.561,50 (teto da filha 1) + 1.500,00 (gasto integral da filha 2)
    assert applied["educacao"] == Decimal("5061.50")
    assert capped["educacao"] == Decimal("8438.50")
    assert applied["dependentes"] == Decimal("4550.16")


def test_saude_sem_teto_e_pgbl_limitado_a_12_pct(table_2025):
    expenses = (
        DeductibleExpense(IRDeductionType.SAUDE, Decimal("48000")),
        DeductibleExpense(IRDeductionType.PREVIDENCIA_PRIVADA_PGBL, Decimal("30000")),
    )
    applied, capped = compute_deductions(expenses, 0, Decimal("150000"), table_2025)

    assert applied["saude"] == Decimal("48000.00")
    assert applied["previdencia_privada_pgbl"] == Decimal("18000.00")  # 12% de 150.000
    assert capped["previdencia_privada_pgbl"] == Decimal("12000.00")


def test_apuracao_escolhe_o_modelo_mais_vantajoso(table_2025):
    taxpayer = TaxpayerYear(
        year=2025,
        incomes=(
            IncomeItem(IRTreatment.TRIBUTAVEL_TABELA, Decimal("180000"), Decimal("35000")),
            IncomeItem(IRTreatment.ISENTO_NAO_TRIBUTAVEL, Decimal("240000")),
        ),
        expenses=(
            DeductibleExpense(IRDeductionType.SAUDE, Decimal("36000")),
            DeductibleExpense(IRDeductionType.EDUCACAO, Decimal("30000"), FILHA_1, "Filha 1"),
            DeductibleExpense(IRDeductionType.EDUCACAO, Decimal("28000"), FILHA_2, "Filha 2"),
        ),
        dependents=2,
    )
    result = assess_year(taxpayer, table_2025)

    assert result.taxable_income == Decimal("180000.00")
    assert result.exempt_income == Decimal("240000.00")
    # deducoes do completo superam o teto do simplificado
    assert result.completo.total_deductions > result.simplificado.total_deductions
    assert result.recommended == TaxModel.COMPLETO
    assert result.savings_vs_other > 0
    assert result.completo.balance == result.completo.tax_due - Decimal("35000.00")


def test_simplificado_vence_quando_ha_poucas_deducoes(table_2025):
    taxpayer = TaxpayerYear(
        year=2025,
        incomes=(IncomeItem(IRTreatment.TRIBUTAVEL_TABELA, Decimal("180000"), Decimal("30000")),),
        expenses=(DeductibleExpense(IRDeductionType.SAUDE, Decimal("1200")),),
        dependents=0,
    )
    result = assess_year(taxpayer, table_2025)

    assert result.recommended == TaxModel.SIMPLIFICADO
    assert result.simplificado.total_deductions == Decimal("16754.34")


def test_beneficio_marginal_de_uma_nota_de_saude(table_2025):
    taxpayer = TaxpayerYear(
        year=2025,
        incomes=(IncomeItem(IRTreatment.TRIBUTAVEL_TABELA, Decimal("300000")),),
        expenses=(DeductibleExpense(IRDeductionType.SAUDE, Decimal("60000")),),
        dependents=2,
    )
    result = assess_year(taxpayer, table_2025)
    # na faixa de 27,5%, cada R$ 1.000 de despesa dedutivel devolve R$ 275
    assert deduction_benefit(Decimal("1000"), result) == Decimal("275.00")


def test_carne_leao_mensal(table_2025):
    # 10.000 - dependentes (2 x 2275,08/12 = 379,18) = 9.620,82
    tax = carne_leao(Decimal("10000"), Decimal("0"), 2, table_2025)
    assert tax == Decimal("1749.73")


def test_carne_leao_2026_respeita_isencao_e_redutor(table_2026):
    assert carne_leao(Decimal("4800"), Decimal("0"), 0, table_2026) == Decimal("0")
    # dentro da faixa do redutor, paga menos que a tabela cheia
    cheio = carne_leao(Decimal("6000"), Decimal("0"), 0, table_2026)
    sem_redutor = Decimal("6000") * Decimal("0.275") - Decimal("896.00")
    assert 0 < cheio < sem_redutor


def test_projecao_do_ano_extrapola_os_meses_restantes(table_2025):
    realizado = TaxpayerYear(
        year=2025,
        incomes=(IncomeItem(IRTreatment.TRIBUTAVEL_TABELA, Decimal("60000"), Decimal("9000")),),
        expenses=(DeductibleExpense(IRDeductionType.SAUDE, Decimal("6000")),),
        dependents=2,
    )
    projetado = project_year(realizado, months_elapsed=6, table=table_2025)

    assert projetado.taxable_income == Decimal("120000.00")
    assert projetado.withheld_tax == Decimal("18000.00")


def test_parametro_ausente_falha_alto(table_2025):
    incompleta = type(table_2025)(
        year=2027, annual_brackets=table_2025.annual_brackets, parameters={}
    )
    with pytest.raises(MissingTaxParameter):
        compute_deductions(
            (DeductibleExpense(IRDeductionType.EDUCACAO, Decimal("1000")),),
            0,
            Decimal("100000"),
            incompleta,
        )
