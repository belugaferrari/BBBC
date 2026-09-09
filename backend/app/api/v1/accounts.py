"""Contas: bancarias, cartoes, custodia e dinheiro.

Contas criadas aqui alimentam tanto o lancamento manual quanto a conciliacao
do Open Finance (basta amarrar `connection_id` e `provider_account_id`).
"""

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import or_, select

from app.api.deps import CurrentMember, DbSession, owned_member
from app.models import Account
from app.models.enums import AccountType
from app.schemas.common import ORMModel


class AccountIn(BaseModel):
    name: str
    type: AccountType
    current_balance: Decimal = Decimal("0")
    credit_limit: Decimal | None = None
    statement_close_day: int | None = Field(default=None, ge=1, le=31)
    statement_due_day: int | None = Field(default=None, ge=1, le=31)
    is_shared: bool = False
    owner_member_id: UUID | None = None


class AccountOut(ORMModel):
    id: UUID
    name: str
    type: AccountType
    owner_member_id: UUID
    current_balance: Decimal
    credit_limit: Decimal | None = None
    is_shared: bool
    is_archived: bool


router = APIRouter(prefix="/accounts", tags=["contas"])


@router.get("", response_model=list[AccountOut])
def list_accounts(current: CurrentMember, db: DbSession, scope: str = "familia") -> list[Account]:
    filters = [Account.family_id == current.family_id, Account.is_archived.is_(False)]
    if scope == "individual":
        # na visao individual o titular ve as suas contas e as compartilhadas
        filters.append(
            or_(Account.owner_member_id == current.id, Account.is_shared.is_(True))
        )
    return list(db.scalars(select(Account).where(*filters).order_by(Account.name)).all())


@router.post("", response_model=AccountOut, status_code=status.HTTP_201_CREATED)
def create_account(payload: AccountIn, current: CurrentMember, db: DbSession) -> Account:
    if payload.owner_member_id:
        owned_member(db, payload.owner_member_id, current)

    account = Account(
        family_id=current.family_id,
        owner_member_id=payload.owner_member_id or current.id,
        **payload.model_dump(exclude={"owner_member_id"}),
    )
    db.add(account)
    db.flush()
    return account


@router.post("/{account_id}/archive", response_model=AccountOut)
def archive_account(account_id: UUID, current: CurrentMember, db: DbSession) -> Account:
    account = db.get(Account, account_id)
    if not account or account.family_id != current.family_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conta nao encontrada")
    account.is_archived = True
    db.flush()
    return account
