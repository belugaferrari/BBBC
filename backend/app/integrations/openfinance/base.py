"""Contrato unico de Open Finance.

O resto do sistema nunca fala com Pluggy ou Belvo diretamente: fala com este
protocolo. Trocar de provedor (ou rodar 100% manual) e trocar a implementacao
registrada em `get_provider()`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from app.models.enums import AccountType, TxDirection


@dataclass(frozen=True)
class ProviderAccount:
    provider_account_id: str
    name: str
    type: AccountType
    balance: Decimal
    currency: str = "BRL"
    credit_limit: Decimal | None = None
    institution_name: str | None = None


@dataclass(frozen=True)
class ProviderTransaction:
    provider_tx_id: str
    provider_account_id: str
    booked_on: date
    amount: Decimal            # sempre positivo
    direction: TxDirection
    description: str
    merchant_name: str | None = None
    installment_no: int | None = None
    installment_total: int | None = None
    raw: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderPosition:
    provider_position_id: str
    provider_account_id: str
    asset_name: str
    asset_class: str
    quantity: Decimal
    market_value: Decimal
    invested_amount: Decimal
    issuer: str | None = None
    maturity_date: date | None = None
    raw: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ConnectToken:
    """Token efemero entregue ao app para abrir o widget de consentimento."""

    token: str
    expires_at: datetime | None = None
    widget_url: str | None = None


class OpenFinanceProvider(ABC):
    """Interface implementada por Pluggy, Belvo ou pelo modo manual."""

    name: str

    @abstractmethod
    async def create_connect_token(self, external_user_id: str) -> ConnectToken: ...

    @abstractmethod
    async def list_accounts(self, item_id: str) -> list[ProviderAccount]: ...

    @abstractmethod
    async def list_transactions(
        self, item_id: str, since: date, until: date | None = None
    ) -> list[ProviderTransaction]: ...

    @abstractmethod
    async def list_positions(self, item_id: str) -> list[ProviderPosition]: ...

    @abstractmethod
    def verify_webhook(self, body: bytes, headers: dict[str, str]) -> bool:
        """Valida a assinatura do webhook. Payload nao assinado e descartado."""


class ManualProvider(OpenFinanceProvider):
    """Modo padrao: tudo entra por lancamento manual/importacao de arquivo.

    Existe para que o app funcione por inteiro antes de qualquer contrato com
    provedor de Open Finance.
    """

    name = "manual"

    async def create_connect_token(self, external_user_id: str) -> ConnectToken:
        raise NotImplementedError("Nenhum provedor de Open Finance configurado")

    async def list_accounts(self, item_id: str) -> list[ProviderAccount]:
        return []

    async def list_transactions(
        self, item_id: str, since: date, until: date | None = None
    ) -> list[ProviderTransaction]:
        return []

    async def list_positions(self, item_id: str) -> list[ProviderPosition]:
        return []

    def verify_webhook(self, body: bytes, headers: dict[str, str]) -> bool:
        return False
