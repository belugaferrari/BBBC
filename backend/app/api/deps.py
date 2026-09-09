"""Dependencias compartilhadas pelos endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models import Member

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_v1_prefix}/auth/login")

DbSession = Annotated[Session, Depends(get_db)]


def get_current_member(
    token: Annotated[str, Depends(oauth2_scheme)], db: DbSession
) -> Member:
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token invalido ou expirado")
    member = db.get(Member, UUID(payload["sub"]))
    if not member or not member.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Membro inativo")
    return member


CurrentMember = Annotated[Member, Depends(get_current_member)]


def scope_member_id(current: Member, scope: str) -> UUID | None:
    """Traduz o filtro de visao do app em um filtro de dono.

    'familia' -> None (sem filtro); 'individual' -> apenas o membro logado.
    """
    return None if scope == "familia" else current.id
