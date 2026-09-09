"""Selecao do provedor conforme a configuracao."""

from functools import lru_cache

from app.core.config import settings
from app.integrations.openfinance.base import ManualProvider, OpenFinanceProvider


@lru_cache
def get_provider(name: str | None = None) -> OpenFinanceProvider:
    provider = (name or settings.open_finance_provider or "none").lower()
    if provider == "pluggy":
        from app.integrations.openfinance.pluggy import PluggyProvider

        return PluggyProvider()
    if provider == "belvo":
        from app.integrations.openfinance.belvo import BelvoProvider

        return BelvoProvider()
    return ManualProvider()
