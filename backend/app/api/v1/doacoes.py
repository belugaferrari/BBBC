"""Doacoes recebidas: quem deu, quanto no ano, e o que o imposto cobra.

Dinheiro que entra e nao e renda. Os sogros depositam todo mes para pagar a
escola das meninas - o dinheiro passa pela conta da familia, mas nao e dela, e
tratar como renda estraga tres numeros: a renda do mes, a taxa de poupanca e a
projecao dos proximos meses. Esta ultima e a pior, porque passaria a contar com
dinheiro que depende da vontade de outra pessoa.

SOBRE O IMPOSTO, e com cuidado. Sao dois impostos diferentes, e confundi-los e o
erro comum:

  * IMPOSTO DE RENDA (federal). Doacao recebida NAO paga. Ela e declarada em
    "Rendimentos Isentos e Nao Tributaveis". O sistema ja a leva para la sozinho,
    pela categoria.

  * ITCMD (estadual). Esse sim incide sobre doacao, e e onde mora o limite de
    isencao. A aliquota e o limite MUDAM DE ESTADO PARA ESTADO e sao corrigidos
    todo ano - nao ha um numero nacional. Por isso o limite nasce vazio aqui, e e
    preenchido com o do estado da familia. Um padrao chutado tranquilizaria sobre
    um limite que nao e o dela, o que e pior que nao dizer nada.

  * E a ESCOLA continua dedutivel por quem a pagou e declara a dependente -
    receber doacao isenta nao tira esse direito. Se os avos pagassem a escola
    direto, a deducao seria deles, e eles nao declaram as meninas.

Nada aqui apura nem recolhe imposto. O que isto faz e somar por doador e por ano,
que e a conta que o limite exige e que nenhuma planilha de gastos costuma ter.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, text

from app.api.deps import CurrentMember, DbSession
from app.models import Donor, Family
from app.schemas.common import ORMModel
from app.services.mascara import nome_curto, sem_digitos_sensiveis

router = APIRouter(tags=["doacoes"])

# Acima disto o aviso aparece. Nao e regra fiscal: e a distancia em que ainda da
# para fazer alguma coisa a respeito (parar, dividir entre doadores, falar com o
# contador) antes de estourar o ano.
ALERTA_A_PARTIR_DE = Decimal("0.80")


class DonorIn(BaseModel):
    name: str = Field(min_length=1)
    relationship: str | None = None
    notes: str | None = None


class DonorOut(ORMModel):
    id: UUID
    name: str
    relationship: str | None = None
    is_active: bool


def _meu_doador(db: DbSession, donor_id: UUID, current: CurrentMember) -> Donor:
    doador = db.get(Donor, donor_id)
    if not doador or doador.family_id != current.family_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Doador nao encontrado")
    return doador


@router.get("/donors", response_model=list[DonorOut])
def list_donors(current: CurrentMember, db: DbSession) -> list[Donor]:
    return list(
        db.scalars(
            select(Donor)
            .where(Donor.family_id == current.family_id, Donor.is_active.is_(True))
            .order_by(Donor.name)
        ).all()
    )


@router.post("/donors", response_model=DonorOut, status_code=status.HTTP_201_CREATED)
def create_donor(payload: DonorIn, current: CurrentMember, db: DbSession) -> Donor:
    doador = Donor(family_id=current.family_id, **payload.model_dump())
    db.add(doador)
    db.flush()
    return doador


@router.patch("/donors/{donor_id}", response_model=DonorOut)
def update_donor(
    donor_id: UUID, payload: DonorIn, current: CurrentMember, db: DbSession
) -> Donor:
    doador = _meu_doador(db, donor_id, current)
    for campo, valor in payload.model_dump(exclude_unset=True).items():
        setattr(doador, campo, valor)
    db.flush()
    return doador


@router.delete("/donors/{donor_id}")
def archive_donor(donor_id: UUID, current: CurrentMember, db: DbSession) -> dict:
    """Arquiva em vez de apagar: as doacoes dele continuam no historico, e um
    doador apagado deixaria somas sem dono no ano que ja passou."""
    doador = _meu_doador(db, donor_id, current)
    doador.is_active = False
    db.flush()
    return {"arquivado": True, "nome": nome_curto(doador.name)}


class LimiteIn(BaseModel):
    """O limite de isencao do ITCMD, que e estadual.

    `uf` fica guardado so para a tela poder lembrar de onde veio o numero.
    """

    itcmd_state: str | None = Field(default=None, max_length=2)
    itcmd_annual_exemption: Decimal | None = Field(default=None, ge=0)


@router.put("/doacoes/limite")
def definir_limite(payload: LimiteIn, current: CurrentMember, db: DbSession) -> dict:
    familia = db.get(Family, current.family_id)
    if familia is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Familia nao encontrada")
    familia.itcmd_state = (payload.itcmd_state or "").upper()[:2] or None
    familia.itcmd_annual_exemption = payload.itcmd_annual_exemption
    db.flush()
    return {
        "itcmd_state": familia.itcmd_state,
        "itcmd_annual_exemption": familia.itcmd_annual_exemption,
    }


@router.get("/doacoes/resumo")
def resumo_das_doacoes(
    current: CurrentMember, db: DbSession, year: int | None = None
) -> dict:
    """Quanto cada doador deu no ano, contra o limite de isencao.

    Por DOADOR, e nao no total: o limite do ITCMD e por doador. Vera e Jose
    depositando metade cada um nao e a mesma coisa que um deles depositar tudo, e
    so olhando separado da para saber de qual dos dois se trata.

    Doador arquivado continua aparecendo no ano em que doou. Esconde-lo faria o
    dinheiro desaparecer da soma - nem no nome dele, nem no balde "sem doador",
    porque a doacao tem dono. Arquivar serve para tirar da lista de escolha, nao
    para apagar o historico.
    """
    ano = year or date.today().year
    familia = db.get(Family, current.family_id)
    limite = familia.itcmd_annual_exemption if familia else None

    linhas = db.execute(
        text(
            """
            SELECT d.id,
                   d.name,
                   d.relationship,
                   d.is_active,
                   COALESCE(SUM(t.amount), 0) AS total,
                   COUNT(t.id)                AS depositos,
                   MAX(t.booked_on)           AS ultimo
              FROM donors d
              LEFT JOIN transactions t
                     ON t.donor_id = d.id
                    AND t.direction = 'ENTRADA'
                    AND t.status IN ('EFETIVADA', 'CONCILIADA')
                    AND EXTRACT(YEAR FROM t.booked_on) = :ano
             WHERE d.family_id = :familia
             GROUP BY d.id, d.name, d.relationship, d.is_active
            HAVING d.is_active OR COUNT(t.id) > 0
             ORDER BY 5 DESC, d.name
            """
        ),
        {"familia": current.family_id, "ano": ano},
    ).mappings().all()

    # Doacao lancada sem doador informado. Nao da para dizer de quem e, entao nao
    # da para medir contra limite nenhum - e dizer isso em voz alta e melhor que
    # deixar a soma por doador parecer completa quando nao e.
    sem_doador = db.execute(
        text(
            """
            SELECT COALESCE(SUM(t.amount), 0)
              FROM transactions t
              JOIN categories c ON c.id = t.category_id
             WHERE t.family_id = :familia
               AND t.direction = 'ENTRADA'
               AND t.status IN ('EFETIVADA', 'CONCILIADA')
               AND t.donor_id IS NULL
               AND c.path <@ 'receitas.doacoes'::ltree
               AND EXTRACT(YEAR FROM t.booked_on) = :ano
            """
        ),
        {"familia": current.family_id, "ano": ano},
    ).scalar_one()

    # As doacoes sem dono, uma por uma, para a tela poder resolver no lugar. Sem
    # isto o aviso seria uma reclamacao sem saida: o deposito que veio do extrato
    # chega sempre sem doador, porque o banco nao sabe quem depositou.
    pendentes = db.execute(
        text(
            """
            SELECT t.id, t.booked_on, t.amount, t.description
              FROM transactions t
              JOIN categories c ON c.id = t.category_id
             WHERE t.family_id = :familia
               AND t.direction = 'ENTRADA'
               AND t.status IN ('EFETIVADA', 'CONCILIADA')
               AND t.donor_id IS NULL
               AND c.path <@ 'receitas.doacoes'::ltree
               AND EXTRACT(YEAR FROM t.booked_on) = :ano
             ORDER BY t.booked_on DESC
             LIMIT 50
            """
        ),
        {"familia": current.family_id, "ano": ano},
    ).mappings().all()

    doadores = []
    for linha in linhas:
        total = Decimal(linha["total"])
        usado = (total / limite) if limite else None
        doadores.append(
            {
                "id": linha["id"],
                "name": nome_curto(linha["name"]),
                "relationship": linha["relationship"],
                "is_active": linha["is_active"],
                "total": total,
                "deposits": int(linha["depositos"]),
                "last_on": linha["ultimo"],
                "used_pct": usado.quantize(Decimal("0.0001")) if usado else None,
                "remaining": (limite - total) if limite else None,
                "should_alert": bool(limite and usado and usado >= ALERTA_A_PARTIR_DE),
            }
        )

    return {
        "year": ano,
        "total": sum((d["total"] for d in doadores), Decimal("0")) + Decimal(sem_doador),
        "sem_doador": Decimal(sem_doador),
        "sem_doador_lancamentos": [
            {
                "id": linha["id"],
                "booked_on": linha["booked_on"],
                "amount": linha["amount"],
                # o extrato costuma trazer agencia e conta na propria descricao
                "description": sem_digitos_sensiveis(linha["description"]),
            }
            for linha in pendentes
        ],
        "itcmd_state": familia.itcmd_state if familia else None,
        "itcmd_annual_exemption": limite,
        "donors": doadores,
        "aviso": (
            None
            if limite
            else (
                "O limite de isenção do ITCMD ainda não foi preenchido. Ele é "
                "estadual — muda de estado para estado e é corrigido todo ano — "
                "então não dá para presumir um número. Confirme o do seu estado "
                "com o contador e preencha aqui."
            )
        ),
    }
