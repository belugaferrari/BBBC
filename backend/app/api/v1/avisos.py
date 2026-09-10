"""Avisos: extratos que faltam, contas a vencer, pontos a expirar - e o envio."""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, text

from app.api.deps import CurrentMember, DbSession
from app.models import NotificationTarget
from app.models.enums import NotificationChannel
from app.services.vigilancia_repository import (
    despachar_pendentes,
    gerar_avisos,
    gravar_avisos,
    montar_checklist,
)

router = APIRouter(tags=["avisos"])


# ---------------------------------------------------------------------------
# Recebimento de extrato mensal
# ---------------------------------------------------------------------------
@router.get("/statements/checklist")
def checklist(current: CurrentMember, db: DbSession, month: date | None = None) -> dict:
    """Quais bancos ja mandaram o extrato do mes e quais ainda faltam."""
    return montar_checklist(db, current.family_id, (month or date.today()).replace(day=1))


# ---------------------------------------------------------------------------
# Avisos
# ---------------------------------------------------------------------------
@router.get("/alerts")
def list_alerts(
    current: CurrentMember, db: DbSession, only_unread: bool = True, limit: int = 50
) -> list[dict]:
    linhas = db.execute(
        text(
            """
            SELECT id, kind, severity::text AS severity, title, body, due_on,
                   read_at, created_at
              FROM alerts
             WHERE family_id = :family_id
               AND (:todos OR read_at IS NULL)
             ORDER BY created_at DESC
             LIMIT :limit
            """
        ),
        {"family_id": current.family_id, "todos": not only_unread, "limit": limit},
    ).mappings().all()
    return [dict(linha) for linha in linhas]


@router.post("/alerts/refresh")
def refresh_alerts(current: CurrentMember, db: DbSession) -> dict:
    """Recalcula os avisos e enfileira o envio.

    Chamado pelo app ao abrir e pela tarefa diaria. E seguro repetir: o indice
    unico da chave de deduplicacao impede o mesmo aviso de nascer duas vezes.
    """
    avisos = gerar_avisos(db, current.family_id)
    criados = gravar_avisos(db, current.family_id, avisos)
    return {"avaliados": len(avisos), "novos": len(criados)}


@router.post("/alerts/{alert_id}/read")
def mark_read(alert_id: UUID, current: CurrentMember, db: DbSession) -> dict:
    atualizado = db.execute(
        text(
            "UPDATE alerts SET read_at = now()"
            " WHERE id = :id AND family_id = :family_id RETURNING id"
        ),
        {"id": alert_id, "family_id": current.family_id},
    ).scalar_one_or_none()
    if atualizado is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aviso nao encontrado")
    return {"id": atualizado, "read": True}


# ---------------------------------------------------------------------------
# Para onde os avisos vao
# ---------------------------------------------------------------------------
class TargetIn(BaseModel):
    channel: NotificationChannel
    address: str
    device_name: str | None = None
    platform: str | None = None


@router.get("/notification-targets")
def list_targets(current: CurrentMember, db: DbSession) -> list[dict]:
    linhas = db.scalars(
        select(NotificationTarget).where(
            NotificationTarget.family_id == current.family_id,
            NotificationTarget.is_active.is_(True),
        )
    ).all()
    return [
        {
            "id": t.id,
            "channel": t.channel,
            # o token de push e longo e nao serve para o usuario ler
            "address": t.address if t.channel == NotificationChannel.EMAIL
            else f"{t.address[:18]}…",
            "device_name": t.device_name,
            "platform": t.platform,
            "member_id": t.member_id,
            "last_used_at": t.last_used_at,
        }
        for t in linhas
    ]


@router.post("/notification-targets", status_code=status.HTTP_201_CREATED)
def register_target(payload: TargetIn, current: CurrentMember, db: DbSession) -> dict:
    """Registra um aparelho (push) ou endereco de e-mail.

    O app chama isto sozinho no primeiro login, com o token do aparelho.
    """
    existente = db.scalar(
        select(NotificationTarget).where(
            NotificationTarget.member_id == current.id,
            NotificationTarget.channel == payload.channel,
            NotificationTarget.address == payload.address,
        )
    )
    if existente:
        existente.is_active = True
        existente.device_name = payload.device_name or existente.device_name
        db.flush()
        return {"id": existente.id, "created": False}

    alvo = NotificationTarget(
        family_id=current.family_id,
        member_id=current.id,
        created_at=date.today(),
        **payload.model_dump(),
    )
    db.add(alvo)
    db.flush()
    return {"id": alvo.id, "created": True}


@router.delete("/notification-targets/{target_id}")
def remove_target(target_id: UUID, current: CurrentMember, db: DbSession) -> dict:
    alvo = db.get(NotificationTarget, target_id)
    if not alvo or alvo.family_id != current.family_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Destino nao encontrado")
    alvo.is_active = False
    db.flush()
    return {"id": target_id, "active": False}


@router.post("/notifications/dispatch")
def dispatch(current: CurrentMember, db: DbSession) -> dict:
    """Envia a fila de notificacoes.

    Existe como endpoint para poder ser disparado a mao e para o agendador
    externo chamar. Ver docs/notificacoes.md.
    """
    return despachar_pendentes(db)
