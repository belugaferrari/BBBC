import os

# Precisa vir ANTES de qualquer import de `app`: as settings sao um singleton
# criado no import de app.core.config, entao definir a variavel depois nao teria
# efeito e os testes de integracao acabariam batendo no banco de desenvolvimento.
_TEST_DATABASE_URL = os.getenv("BBBC_TEST_DATABASE_URL")
if _TEST_DATABASE_URL:
    os.environ["DATABASE_URL"] = _TEST_DATABASE_URL

from decimal import Decimal  # noqa: E402

import pytest  # noqa: E402

from app.services.tax import Bracket, TaxTable  # noqa: E402

# Espelha o que a migration 0002 semeia para 2025.
ANNUAL_2025 = (
    Bracket(Decimal("0"), Decimal("27110.40"), Decimal("0"), Decimal("0")),
    Bracket(Decimal("27110.41"), Decimal("33919.80"), Decimal("0.075"), Decimal("2033.28")),
    Bracket(Decimal("33919.81"), Decimal("45012.60"), Decimal("0.15"), Decimal("4577.28")),
    Bracket(Decimal("45012.61"), Decimal("55976.16"), Decimal("0.225"), Decimal("7953.24")),
    Bracket(Decimal("55976.17"), None, Decimal("0.275"), Decimal("10752.00")),
)

MONTHLY_2025 = (
    Bracket(Decimal("0"), Decimal("2259.20"), Decimal("0"), Decimal("0")),
    Bracket(Decimal("2259.21"), Decimal("2826.65"), Decimal("0.075"), Decimal("169.44")),
    Bracket(Decimal("2826.66"), Decimal("3751.05"), Decimal("0.15"), Decimal("381.44")),
    Bracket(Decimal("3751.06"), Decimal("4664.68"), Decimal("0.225"), Decimal("662.77")),
    Bracket(Decimal("4664.69"), None, Decimal("0.275"), Decimal("896.00")),
)

PARAMS_2025 = {
    "DEDUCAO_DEPENDENTE_ANUAL": Decimal("2275.08"),
    "LIMITE_EDUCACAO_ANUAL": Decimal("3561.50"),
    "DESCONTO_SIMPLIFICADO_PCT": Decimal("0.20"),
    "DESCONTO_SIMPLIFICADO_TETO": Decimal("16754.34"),
    "LIMITE_PGBL_PCT": Decimal("0.12"),
}


@pytest.fixture
def table_2025() -> TaxTable:
    return TaxTable(
        year=2025,
        annual_brackets=ANNUAL_2025,
        monthly_brackets=MONTHLY_2025,
        parameters=dict(PARAMS_2025),
        status="VIGENTE",
    )


@pytest.fixture
def table_2026() -> TaxTable:
    """2026 com a faixa de isencao ampliada e o redutor progressivo."""
    return TaxTable(
        year=2026,
        annual_brackets=ANNUAL_2025,
        monthly_brackets=MONTHLY_2025,
        parameters={
            **PARAMS_2025,
            "ISENCAO_MENSAL": Decimal("5000.00"),
            "REDUTOR_LIMITE_SUPERIOR": Decimal("7350.00"),
        },
        status="PROVISORIO",
    )
