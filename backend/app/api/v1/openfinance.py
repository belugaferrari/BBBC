"""Endpoints de Open Finance: consentimento, sincronizacao e webhooks."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import CurrentMember, DbSession
from app.core.config import settings
from app.integrations.openfinance.factory import get_provider
from app.models import BankConnection, WebhookEvent
from app.models.enums import ConnectionStatus
from app.services.open_finance_sync import default_sync_window, sync_connection

router = APIRouter(prefix="/open-finance", tags=["open-finance"])


class ConnectionIn(BaseModel):
    provider_item_id: str
    provider: str | None = None
    institution_name: str | None = None


@router.post("/connect-token")
async def connect_token(current: CurrentMember) -> dict:
    """Token efemero para o app abrir o widget de consentimento do provedor."""
    provider = get_provider()
    if provider.name == "manual":
        raise HTTPException(
            status.HTTP_501_NOT_IMPLEMENTED,
            "Nenhum provedor de Open Finance configurado; use lancamento manual",
        )
    token = await provider.create_connect_token(str(current.id))
    return {"provider": provider.name, "token": token.token, "expires_at": token.expires_at}


@router.post("/connections", status_code=status.HTTP_201_CREATED)
def register_connection(payload: ConnectionIn, current: CurrentMember, db: DbSession) -> dict:
    """Registra o item/link criado no widget. Credenciais ficam no provedor."""
    connection = BankConnection(
        family_id=current.family_id,
        owner_member_id=current.id,
        provider=payload.provider or settings.open_finance_provider,
        provider_item_id=payload.provider_item_id,
        status=ConnectionStatus.ATIVA,
    )
    db.add(connection)
    db.flush()
    return {"id": connection.id, "status": connection.status}


@router.post("/connections/{connection_id}/sync")
async def sync(connection_id: UUID, current: CurrentMember, db: DbSession) -> dict:
    connection = db.get(BankConnection, connection_id)
    if not connection or connection.family_id != current.family_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conexao nao encontrada")

    provider = get_provider(connection.provider)
    since, until = default_sync_window(connection)
    # as contas vem primeiro: as transacoes chegam referenciando o id de conta
    # do provedor e precisam encontrar a conta local ja criada
    accounts = await provider.list_accounts(connection.provider_item_id or "")
    transactions = await provider.list_transactions(
        connection.provider_item_id or "", since, until
    )
    log = sync_connection(db, connection, provider, transactions, provider_accounts=accounts)
    connection.last_error = log.error_message
    return {
        "window": {"since": since, "until": until},
        "accounts": log.accounts_synced,
        "created": log.transactions_created,
        "updated": log.transactions_updated,
        "status": log.status,
        "warning": log.error_message,
    }


@router.post("/webhooks/{provider_name}", status_code=status.HTTP_202_ACCEPTED)
async def webhook(provider_name: str, request: Request, db: DbSession) -> dict:
    """Recebe notificacoes do provedor.

    A assinatura e obrigatoria: payload nao autenticado e registrado e
    descartado, nunca processado.
    """
    body = await request.body()
    provider = get_provider(provider_name)
    signature_ok = provider.verify_webhook(body, dict(request.headers))

    payload = await request.json()
    event = WebhookEvent(
        provider=provider_name,
        event_id=str(payload.get("id") or payload.get("event_id") or ""),
        event_type=str(payload.get("event") or payload.get("type") or "desconhecido"),
        payload=payload,
        signature_ok=signature_ok,
        received_at=datetime.now(UTC),
    )
    db.add(event)
    # commit antes de recusar: a sessao faz rollback ao levantar a excecao e
    # perderiamos justamente o registro da tentativa nao autenticada
    db.commit()

    if not signature_ok:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Assinatura invalida")

    item_id = str(payload.get("itemId") or payload.get("link_id") or "")
    connection = db.scalar(
        select(BankConnection).where(BankConnection.provider_item_id == item_id)
    )
    if connection:
        connection.status = ConnectionStatus.ATIVA
        connection.last_error = None
    return {"received": True, "connection_found": connection is not None}
