"""Contas: bancarias, cartoes, custodia e dinheiro.

Contas criadas aqui alimentam tanto o lancamento manual quanto a conciliacao
do Open Finance (basta amarrar `connection_id` e `provider_account_id`).
"""

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import or_, select

from app.api.deps import CurrentMember, DbSession, owned_member
from app.models import Account
from app.models.enums import AccountType
from app.schemas.common import ORMModel
from app.services.mascara import sem_digitos_sensiveis


class AccountIn(BaseModel):
    """Cadastro de conta. Exige o nome; o resto tem padrao.

    So o nome e obrigatorio de proposito. Enquanto o sistema nao puxa dados de
    banco nenhum sozinho, obrigar agencia, conta e saldo no cadastro seria pedir
    ao usuario que digitasse informacao sensivel sem nada em troca. Sem titular
    informado, a conta fica com quem a cadastrou; sem tipo, vale conta corrente,
    que e o caso da grande maioria.
    """

    name: str = Field(min_length=1)
    type: AccountType = AccountType.CONTA_CORRENTE
    current_balance: Decimal = Decimal("0")
    credit_limit: Decimal | None = None
    statement_close_day: int | None = Field(default=None, ge=1, le=31)
    statement_due_day: int | None = Field(default=None, ge=1, le=31)
    is_shared: bool = False
    is_business: bool = False
    owner_member_id: UUID | None = None

    @field_validator("name", mode="after")
    @classmethod
    def _sem_agencia_nem_conta(cls, valor: str) -> str:
        """Tira o numero antes de gravar, e nao so na hora de mostrar.

        E comum digitar o numero junto do nome ("Itau 1234-5"). A saida ja
        mascara, mas o que nao e gravado nao pode vazar depois - e o numero da
        conta nao serve para nada aqui, porque o sistema nao fala com o banco.
        """
        limpo = sem_digitos_sensiveis(valor).strip()
        if not limpo:
            raise ValueError("Diga o nome do banco.")
        return limpo


class AccountOut(ORMModel):
    id: UUID
    name: str

    @field_validator("name", mode="after")
    @classmethod
    def _sem_agencia_nem_conta(cls, valor: str) -> str:
        """O nome da conta e digitado pelo usuario, e e comum digitar o numero
        junto ("Itau 1234-5"). O numero nao sai do servidor."""
        return sem_digitos_sensiveis(valor)

    type: AccountType
    owner_member_id: UUID
    current_balance: Decimal
    credit_limit: Decimal | None = None
    is_shared: bool
    is_business: bool
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
