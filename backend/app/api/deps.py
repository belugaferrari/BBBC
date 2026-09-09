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


# ---------------------------------------------------------------------------
# Guardas de propriedade
# ---------------------------------------------------------------------------
# Autenticar nao e autorizar: o token diz QUEM e o usuario, nao a QUE ele pode
# chegar. Todo id que chega pelo corpo ou pela query e resolvido por estas
# funcoes, que devolvem 404 (e nao 403) quando o registro e de outra familia -
# responder 403 confirmaria que aquele id existe.
def _owned(db: Session, model: type, entity_id: UUID, family_id: UUID, label: str):  # noqa: ANN202
    entity = db.get(model, entity_id)
    if entity is None or getattr(entity, "family_id", None) != family_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{label} nao encontrado")
    return entity


def owned_account(db: Session, account_id: UUID, current: Member):
    from app.models import Account

    return _owned(db, Account, account_id, current.family_id, "Conta")


def owned_category(db: Session, category_id: UUID, current: Member):
    """Categoria da familia ou do catalogo global (family_id NULL)."""
    from app.models import Category

    category = db.get(Category, category_id)
    if category is None or category.family_id not in (current.family_id, None):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Categoria nao encontrada")
    return category


def owned_member(db: Session, member_id: UUID, current: Member) -> Member:
    return _owned(db, Member, member_id, current.family_id, "Membro")


def owned_tag(db: Session, tag_id: UUID, current: Member):
    from app.models import Tag

    return _owned(db, Tag, tag_id, current.family_id, "Tag")
