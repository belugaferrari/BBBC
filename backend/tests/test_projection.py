"""Testes do simulador de metas e dos tetos de gasto."""

from datetime import date
from decimal import Decimal

from app.services.projection import (
    GoalInput,
    ScheduledFlow,
    budget_status,
    cashflow_forecast,
    future_value,
    months_to_target,
    required_monthly_contribution,
    simulate_goal,
)


def test_valor_futuro_sem_juros():
    assert future_value(Decimal("1000"), Decimal("500"), Decimal("0"), 12) == Decimal("7000.00")


def test_aporte_necessario_bate_com_o_valor_futuro():
    alvo, prazo, taxa = Decimal("80000"), 36, Decimal("0.11")
    aporte = required_monthly_contribution(alvo, Decimal("10000"), taxa, prazo)
    projetado = future_value(Decimal("10000"), aporte, taxa, prazo)
    assert abs(projetado - alvo) < Decimal("1.00")


def test_meta_disney_fora_do_ritmo_mostra_quanto_falta_por_mes():
    meta = GoalInput(
        name="Viagem Disney",
        target_amount=Decimal("120000"),
        target_date=date(2029, 1, 1),
        current_amount=Decimal("15000"),
        monthly_contribution=Decimal("1000"),
        expected_annual_rate=Decimal("0.10"),
    )
    projecao = simulate_goal(meta, today=date(2026, 1, 1))

    assert projecao.months_remaining == 36
    assert not projecao.on_track
    assert projecao.gap > 0
    assert projecao.contribution_delta > 0
    assert len(projecao.series) == 37


def test_meta_indexada_a_inflacao_eleva_o_alvo():
    base = dict(
        name="Disney",
        target_amount=Decimal("100000"),
        target_date=date(2029, 1, 1),
        current_amount=Decimal("0"),
        monthly_contribution=Decimal("2000"),
        expected_annual_rate=Decimal("0.10"),
    )
    nominal = simulate_goal(GoalInput(**base), today=date(2026, 1, 1))
    indexada = simulate_goal(
        GoalInput(**base, inflation_indexed=True, expected_inflation=Decimal("0.045")),
        today=date(2026, 1, 1),
    )
    assert indexada.adjusted_target > nominal.adjusted_target
    assert indexada.required_monthly > nominal.required_monthly


def test_meses_ate_a_meta():
    assert months_to_target(Decimal("12000"), Decimal("0"), Decimal("1000"), Decimal("0")) == 12
    assert months_to_target(Decimal("100"), Decimal("100"), Decimal("0"), Decimal("0")) == 0
    assert months_to_target(Decimal("1000"), Decimal("0"), Decimal("0"), Decimal("0")) is None


def test_teto_projeta_estouro_pelo_ritmo_do_mes():
    status = budget_status(
        category_id="x",
        category_name="Restaurantes",
        cap=Decimal("2000"),
        spent=Decimal("1200"),
        days_elapsed=10,
        days_in_period=30,
    )
    assert status.projected_spend == Decimal("3600.00")
    assert status.projected_overflow == Decimal("1600.00")
    assert status.should_alert
    assert status.severity == "ATENCAO"


def test_teto_ja_estourado_e_critico():
    status = budget_status(
        category_id="x", category_name="Lazer", cap=Decimal("500"),
        spent=Decimal("620"), days_elapsed=20, days_in_period=30,
    )
    assert status.severity == "CRITICO"
    assert status.remaining == Decimal("-120.00")


def test_projecao_de_fluxo_de_caixa():
    flows = [
        ScheduledFlow("Pro-labore", Decimal("25000"), 0),
        ScheduledFlow("Escola", Decimal("-4200"), 0),
        ScheduledFlow("Pro-labore", Decimal("25000"), 1),
    ]
    resultado = cashflow_forecast(Decimal("10000"), flows, months=2)
    assert resultado[0]["closing_balance"] == Decimal("30800.00")
    assert resultado[1]["closing_balance"] == Decimal("55800.00")
