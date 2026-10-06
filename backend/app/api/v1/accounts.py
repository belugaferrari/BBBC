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
    # Os dias da fatura saem do servidor porque a tela precisa deles para dizer,
    # ANTES de o extrato ser confirmado, em que mes cada compra vai contar. Sem
    # eles a conta e feita assim mesmo, supondo fatura que fecha no fim do mes e
    # vence no dia 10 - e a tela avisa que esta supondo.
    statement_close_day: int | None = None
    statement_due_day: int | None = None
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


class AccountUpdate(BaseModel):
    """O que da para corrigir numa conta ja cadastrada.

    "Eu preciso poder EDITAR as informacoes das Contas que mando pro sistema."
    Cadastro de conta se faz uma vez e se convive com ele por anos: o cartao
    muda de dia de vencimento, o apelido ficou ruim, a conta que era so dele
    virou conjunta. Sem edicao, a saida era arquivar e criar outra - e o
    historico ficava na conta velha, partido em duas.

    `current_balance` fica de fora: saldo nao se digita, se apura. Ele e
    recalculado pela conciliacao a partir dos lancamentos, e deixar alguem
    escrever por cima faria o saldo divergir do razao sem deixar rastro.
    """

    name: str | None = Field(default=None, min_length=1)
    type: AccountType | None = None
    credit_limit: Decimal | None = None
    statement_close_day: int | None = Field(default=None, ge=1, le=31)
    statement_due_day: int | None = Field(default=None, ge=1, le=31)
    is_shared: bool | None = None
    is_business: bool | None = None
    owner_member_id: UUID | None = None

    @field_validator("name", mode="after")
    @classmethod
    def _sem_agencia_nem_conta(cls, valor: str | None) -> str | None:
        if valor is None:
            return None
        limpo = sem_digitos_sensiveis(valor).strip()
        if not limpo:
            raise ValueError("Diga o nome do banco.")
        return limpo


@router.patch("/{account_id}", response_model=AccountOut)
def update_account(
    account_id: UUID, payload: AccountUpdate, current: CurrentMember, db: DbSession
) -> Account:
    """Corrige uma conta. So o que foi enviado muda.

    Os lancamentos que ja existem NAO sao recalculados quando os dias da fatura
    mudam - e isso e escolha, nao esquecimento. Boa parte deles tem o mes de
    caixa lido do proprio arquivo ("Vencimento 09/01/2026"), que e informacao
    melhor do que qualquer conta a partir do dia de fechamento; recalcular por
    cima trocaria um dado por um palpite. Para refazer um lote com os dias
    certos, o caminho e desfazer a importacao e importar de novo.
    """
    account = db.get(Account, account_id)
    if not account or account.family_id != current.family_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conta nao encontrada")

    if payload.owner_member_id:
        owned_member(db, payload.owner_member_id, current)

    for campo, valor in payload.model_dump(exclude_unset=True).items():
        setattr(account, campo, valor)
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
