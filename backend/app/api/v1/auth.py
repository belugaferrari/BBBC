"""Autenticacao. Apenas Felipe e Clarissa tem credenciais; dependentes nao logam."""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentMember, DbSession
from app.core.security import create_access_token, verify_password
from app.models import Member
from app.schemas.common import LoginRequest, Token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
def login(payload: LoginRequest, db: DbSession) -> Token:
    member = db.scalar(select(Member).where(Member.email == payload.email.lower()))
    if not member or not member.password_hash or not verify_password(
        payload.password, member.password_hash
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Credenciais invalidas")
    if not member.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Membro inativo")

    return Token(
        access_token=create_access_token(member.id, member.family_id),
        member_id=member.id,
        family_id=member.family_id,
        full_name=member.full_name,
    )


@router.get("/members")
def list_members(current: CurrentMember, db: DbSession) -> list[dict]:
    """Quem existe na familia. Alimenta o seletor de responsavel pelo gasto e
    o de quem consumiu a despesa dedutivel."""
    membros = db.scalars(
        select(Member)
        .where(Member.family_id == current.family_id, Member.is_active.is_(True))
        .order_by(Member.role, Member.full_name)
    ).all()
    return [
        {
            "id": m.id,
            "name": m.nickname or m.full_name,
            "role": m.role,
            "is_ir_dependent": m.is_ir_dependent,
            "can_login": m.can_login,
        }
        for m in membros
    ]


@router.get("/me")
def me(current: CurrentMember) -> dict:
    return {
        "id": current.id,
        "full_name": current.full_name,
        "nickname": current.nickname,
        "role": current.role,
        "family_id": current.family_id,
    }
