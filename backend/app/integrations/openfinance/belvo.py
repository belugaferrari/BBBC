"""Cliente Belvo (alternativa ao Pluggy, mesmo contrato)."""

from __future__ import annotations

import hashlib
import hmac
from datetime import date, datetime
from decimal import Decimal

import httpx

from app.core.config import settings
from app.integrations.openfinance.base import (
    ConnectToken,
    OpenFinanceProvider,
    ProviderAccount,
    ProviderPosition,
    ProviderTransaction,
)
from app.models.enums import AccountType, TxDirection

_ENV_URLS = {
    "sandbox": "https://sandbox.belvo.com",
    "development": "https://development.belvo.com",
    "production": "https://api.belvo.com",
}

_ACCOUNT_TYPE_MAP = {
    "CHECKING_ACCOUNT": AccountType.CONTA_CORRENTE,
    "SAVINGS_ACCOUNT": AccountType.POUPANCA,
    "CREDIT_CARD": AccountType.CARTAO_CREDITO,
    "INVESTMENT": AccountType.INVESTIMENTO,
}


class BelvoProvider(OpenFinanceProvider):
    name = "belvo"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        base_url = _ENV_URLS.get(settings.belvo_env, _ENV_URLS["sandbox"])
        self._client = client or httpx.AsyncClient(
            base_url=base_url,
            auth=(settings.belvo_secret_id or "", settings.belvo_secret_password or ""),
            timeout=30,
        )

    async def create_connect_token(self, external_user_id: str) -> ConnectToken:
        response = await self._client.post(
            "/api/token/",
            json={
                "id": settings.belvo_secret_id,
                "password": settings.belvo_secret_password,
                "scopes": "read_institutions,write_links",
                "widget": {"external_id": external_user_id},
            },
        )
        response.raise_for_status()
        return ConnectToken(token=response.json()["access"])

    async def list_accounts(self, item_id: str) -> list[ProviderAccount]:
        response = await self._client.get("/api/accounts/", params={"link": item_id})
        response.raise_for_status()
        return [
            ProviderAccount(
                provider_account_id=row["id"],
                name=row.get("name") or row.get("category") or "Conta",
                type=_ACCOUNT_TYPE_MAP.get(row.get("category", ""), AccountType.OUTRO),
                balance=Decimal(str((row.get("balance") or {}).get("current") or 0)),
                currency=row.get("currency", "BRL"),
            )
            for row in response.json()
        ]

    async def list_transactions(
        self, item_id: str, since: date, until: date | None = None
    ) -> list[ProviderTransaction]:
        response = await self._client.get(
            "/api/transactions/",
            params={
                "link": item_id,
                "value_date__gte": since.isoformat(),
                "value_date__lte": (until or date.today()).isoformat(),
                "page_size": 500,
            },
        )
        response.raise_for_status()
        return [
            ProviderTransaction(
                provider_tx_id=row["id"],
                provider_account_id=(row.get("account") or {}).get("id", ""),
                booked_on=datetime.fromisoformat(row["value_date"]).date(),
                amount=abs(Decimal(str(row["amount"]))),
                direction=(
                    TxDirection.ENTRADA if row.get("type") == "INFLOW" else TxDirection.SAIDA
                ),
                description=row.get("description") or "",
                merchant_name=(row.get("merchant") or {}).get("name"),
                raw=row,
            )
            for row in response.json()
        ]

    async def list_positions(self, item_id: str) -> list[ProviderPosition]:
        response = await self._client.get("/api/investments/portfolios/", params={"link": item_id})
        response.raise_for_status()
        return [
            ProviderPosition(
                provider_position_id=row["id"],
                provider_account_id=row.get("account", ""),
                asset_name=row.get("name") or "Ativo",
                asset_class=row.get("type") or "OUTRO",
                quantity=Decimal(str(row.get("units") or 0)),
                market_value=Decimal(str(row.get("balance_gross") or 0)),
                invested_amount=Decimal(str(row.get("balance_net") or 0)),
                raw=row,
            )
            for row in response.json()
        ]

    def verify_webhook(self, body: bytes, headers: dict[str, str]) -> bool:
        secret = settings.belvo_webhook_secret
        signature = headers.get("belvo-signature")
        if not secret or not signature:
            return False
        expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)
