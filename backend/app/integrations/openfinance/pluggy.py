"""Cliente Pluggy.

Endpoints e nomes de campo seguem a documentacao publica da Pluggy; o mapeamento
esta isolado nas funcoes `_to_*` para absorver mudancas do provedor sem mexer no
dominio.
"""

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

BASE_URL = "https://api.pluggy.ai"

_ACCOUNT_TYPE_MAP = {
    "BANK": AccountType.CONTA_CORRENTE,
    "CREDIT": AccountType.CARTAO_CREDITO,
    "INVESTMENT": AccountType.INVESTIMENTO,
}


class PluggyProvider(OpenFinanceProvider):
    name = "pluggy"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or httpx.AsyncClient(base_url=BASE_URL, timeout=30)
        self._api_key: str | None = None

    async def _auth_headers(self) -> dict[str, str]:
        if not self._api_key:
            response = await self._client.post(
                "/auth",
                json={
                    "clientId": settings.pluggy_client_id,
                    "clientSecret": settings.pluggy_client_secret,
                },
            )
            response.raise_for_status()
            self._api_key = response.json()["apiKey"]
        return {"X-API-KEY": self._api_key or ""}

    async def create_connect_token(self, external_user_id: str) -> ConnectToken:
        response = await self._client.post(
            "/connect_token",
            headers=await self._auth_headers(),
            json={"clientUserId": external_user_id},
        )
        response.raise_for_status()
        return ConnectToken(token=response.json()["accessToken"])

    async def list_accounts(self, item_id: str) -> list[ProviderAccount]:
        response = await self._client.get(
            "/accounts", headers=await self._auth_headers(), params={"itemId": item_id}
        )
        response.raise_for_status()
        return [_to_account(row) for row in response.json().get("results", [])]

    async def list_transactions(
        self, item_id: str, since: date, until: date | None = None
    ) -> list[ProviderTransaction]:
        results: list[ProviderTransaction] = []
        for account in await self.list_accounts(item_id):
            page = 1
            while True:
                response = await self._client.get(
                    "/transactions",
                    headers=await self._auth_headers(),
                    params={
                        "accountId": account.provider_account_id,
                        "from": since.isoformat(),
                        "to": (until or date.today()).isoformat(),
                        "page": page,
                        "pageSize": 200,
                    },
                )
                response.raise_for_status()
                body = response.json()
                results.extend(
                    _to_transaction(row, account.provider_account_id)
                    for row in body.get("results", [])
                )
                if page >= body.get("totalPages", 1):
                    break
                page += 1
        return results

    async def list_positions(self, item_id: str) -> list[ProviderPosition]:
        response = await self._client.get(
            "/investments", headers=await self._auth_headers(), params={"itemId": item_id}
        )
        response.raise_for_status()
        return [_to_position(row) for row in response.json().get("results", [])]

    def verify_webhook(self, body: bytes, headers: dict[str, str]) -> bool:
        secret = settings.pluggy_webhook_secret
        signature = headers.get("x-signature") or headers.get("X-Signature")
        if not secret or not signature:
            return False
        expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)


def _to_account(row: dict) -> ProviderAccount:
    return ProviderAccount(
        provider_account_id=row["id"],
        name=row.get("name") or row.get("marketingName") or "Conta",
        type=_ACCOUNT_TYPE_MAP.get(row.get("type", ""), AccountType.OUTRO),
        balance=Decimal(str(row.get("balance", 0))),
        currency=row.get("currencyCode", "BRL"),
        credit_limit=(
            Decimal(str(row["creditData"]["creditLimit"]))
            if row.get("creditData", {}).get("creditLimit") is not None
            else None
        ),
    )


def _to_transaction(row: dict, account_id: str) -> ProviderTransaction:
    amount = Decimal(str(row["amount"]))
    credit = row.get("type") == "CREDIT" or amount > 0
    installments = row.get("creditCardMetadata") or {}
    return ProviderTransaction(
        provider_tx_id=row["id"],
        provider_account_id=account_id,
        booked_on=datetime.fromisoformat(row["date"].replace("Z", "+00:00")).date(),
        amount=abs(amount),
        direction=TxDirection.ENTRADA if credit else TxDirection.SAIDA,
        description=row.get("description") or "",
        merchant_name=(row.get("merchant") or {}).get("name"),
        installment_no=installments.get("installmentNumber"),
        installment_total=installments.get("totalInstallments"),
        raw=row,
    )


def _to_position(row: dict) -> ProviderPosition:
    return ProviderPosition(
        provider_position_id=row["id"],
        provider_account_id=row.get("accountId") or "",
        asset_name=row.get("name") or row.get("code") or "Ativo",
        asset_class=row.get("type") or "OUTRO",
        quantity=Decimal(str(row.get("quantity") or 0)),
        market_value=Decimal(str(row.get("balance") or 0)),
        invested_amount=Decimal(str(row.get("amountOriginal") or row.get("balance") or 0)),
        issuer=row.get("issuer"),
        raw=row,
    )
