"""Importacao de extratos bancarios (OFX, CSV, PDF).

Dois passos por seguranca: `POST /imports` le o arquivo e devolve a
pre-visualizacao sem gravar nada; `POST /imports/{id}/confirm` grava o que voce
conferiu.
"""

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import delete, select

from app.api.deps import CurrentMember, DbSession, owned_account, owned_category
from app.models import StatementImport, Transaction
from app.services.import_service import build_preview, confirm_import
from app.services.importers.base import StatementParseError
from app.services.importers.detect import MAX_FILE_BYTES, SUPPORTED

router = APIRouter(prefix="/imports", tags=["importacao"])


def _rotulo(row: StatementImport) -> str:
    """Como o lote aparece na tela, sem o nome do arquivo.

    Nome de arquivo de extrato costuma trazer o banco e o numero da conta no
    proprio nome ("extrato-itau-12345.pdf"). Esconder os digitos nao bastaria:
    o nome do banco ficaria. O periodo e o formato identificam o lote sem
    contar nada que nao precise ser contado. O nome original continua no banco
    de dados, em casa, para quando for preciso investigar.
    """
    if row.period_start and row.period_end:
        inicio = row.period_start.strftime("%d/%m")
        fim = row.period_end.strftime("%d/%m/%Y")
        return f"Extrato {row.file_format} de {inicio} a {fim}"
    return f"Extrato {row.file_format}"


def _vencimento_da_fatura(row: StatementImport) -> str | None:
    """A data em que todas as compras deste lote saem da conta, quando ha uma.

    Nao e coluna no banco: e o que as linhas de SAIDA tem em comum. Numa fatura
    de cartao elas compartilham o vencimento, e e isso que a tela precisa
    mostrar ("tudo aqui conta em janeiro"). Em extrato de conta corrente cada
    linha tem a sua data, nao ha nada em comum, e a tela nao mostra nada.
    """
    datas = {
        linha.get("paid_on")
        for linha in (row.preview or [])
        if linha.get("direction") == "SAIDA" and linha.get("paid_on")
    }
    return datas.pop() if len(datas) == 1 else None


def _serialize(row: StatementImport) -> dict:
    return {
        "id": row.id,
        "account_id": row.account_id,
        "rotulo": _rotulo(row),
        "file_format": row.file_format,
        "status": row.status,
        "period_start": row.period_start,
        "period_end": row.period_end,
        "rows_detected": row.rows_detected,
        "rows_duplicated": row.rows_duplicated,
        "rows_imported": row.rows_imported,
        "warnings": row.warnings,
        "vencimento_da_fatura": _vencimento_da_fatura(row),
        "preview": row.preview,
        "created_at": row.created_at,
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload_statement(
    current: CurrentMember,
    db: DbSession,
    account_id: Annotated[UUID, Form()],
    file: Annotated[UploadFile, File()],
) -> dict:
    """Envia o extrato e recebe a pre-visualizacao. **Nao grava lancamento.**"""
    account = owned_account(db, account_id, current)
    content = await file.read()

    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"arquivo maior que {MAX_FILE_BYTES // (1024 * 1024)} MB",
        )

    try:
        row = build_preview(
            db,
            family_id=current.family_id,
            account=account,
            member_id=current.id,
            filename=file.filename or "extrato",
            content=content,
        )
    except StatementParseError as exc:
        # 422: o arquivo chegou inteiro, mas nao da para extrair lancamentos
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"{exc} (formatos aceitos: {', '.join(SUPPORTED)})",
        ) from exc

    return _serialize(row)


class ConfirmIn(BaseModel):
    """Quais linhas gravar. Omitir `selected_indexes` grava o que veio marcado
    na pre-visualizacao (tudo que nao foi detectado como duplicado).

    Numa conta da empresa, confirmar uma linha quer dizer "isto e meu": o que
    fica de fora pertence a empresa e nao entra em nada da familia.
    """

    selected_indexes: list[int] | None = None
    category_overrides: dict[int, UUID] | None = None
    # Por linha: ENTRADA ou SAIDA, quando o arquivo disse o contrario. O sistema
    # ja corrige o sinal invertido da fatura de cartao sozinho (ver
    # app/services/importers/fatura.py), mas leiaute de banco nao acaba - e a
    # ultima vez que uma linha entrou do lado errado, nao havia como consertar
    # pela tela, so no banco de dados.
    direction_overrides: dict[int, str] | None = None
    # Quando a fatura vence - e, portanto, em que mes TODAS as compras dela
    # contam. O arquivo quase sempre diz, e a tela mostra o que leu; isto aqui e
    # para quando ele precisa corrigir, ou quando o arquivo nao disse nada.
    vencimento_da_fatura: date | None = None
    # Por linha: PRO_LABORE, LUCROS ou ADIANTAMENTO. Decide o IR da entrada que
    # cobre a despesa; so vale em conta da empresa. Omitido, vai o padrao, que e
    # o unico que nao afirma nada sobre imposto.
    contrapartidas: dict[int, str] | None = None


@router.post("/{import_id}/confirm")
def confirm(
    import_id: UUID, payload: ConfirmIn, current: CurrentMember, db: DbSession
) -> dict:
    row = db.get(StatementImport, import_id)
    if not row or row.family_id != current.family_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Importacao nao encontrada")

    for category_id in (payload.category_overrides or {}).values():
        owned_category(db, category_id, current)

    for linha, direcao in (payload.direction_overrides or {}).items():
        if direcao not in ("ENTRADA", "SAIDA"):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"linha {linha}: '{direcao}' nao e ENTRADA nem SAIDA",
            )

    try:
        confirm_import(
            db,
            row,
            selected_indexes=payload.selected_indexes,
            category_overrides=payload.category_overrides,
            direction_overrides=payload.direction_overrides,
            vencimento_da_fatura=payload.vencimento_da_fatura,
            contrapartidas=payload.contrapartidas,
        )
    # ContrapartidaDesconhecida e ValueError: cai aqui junto com os demais
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    return _serialize(row)


@router.post("/{import_id}/discard")
def discard(import_id: UUID, current: CurrentMember, db: DbSession) -> dict:
    row = db.get(StatementImport, import_id)
    if not row or row.family_id != current.family_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Importacao nao encontrada")
    if row.status == "CONFIRMADO":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "esta importacao ja foi confirmada; apague os lancamentos se quiser desfazer",
        )
    row.status = "DESCARTADO"
    db.flush()
    return _serialize(row)


@router.post("/{import_id}/desfazer")
def desfazer(import_id: UUID, current: CurrentMember, db: DbSession) -> dict:
    """Apaga os lancamentos que ESTA importacao criou.

    Existe por causa de um caso concreto: a fatura do cartao entrou com o sinal
    invertido, as compras viraram renda, e a unica saida era apagar linha por
    linha - dezenas delas - ou mexer no banco de dados. Pior ainda, reimportar o
    mesmo arquivo depois da correcao nao resolveria: a direcao entra na impressao
    digital, entao as linhas corrigidas NAO sao reconhecidas como repetidas, e a
    familia terminaria com as duas versoes somadas.

    Apaga so o que veio do arquivo (`import_id`), e nada do que foi lancado a
    mao. Lancamento editado depois tambem vai: ele continua sendo aquela linha do
    extrato, e deixa-lo orfao seria guardar justamente o numero errado.

    O lote fica como DESCARTADO, e nao apagado: ele e o registro de que aquele
    arquivo passou por aqui, com os avisos que apareceram na conferencia.
    """
    row = db.get(StatementImport, import_id)
    if not row or row.family_id != current.family_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Importacao nao encontrada")

    apagados = db.execute(
        delete(Transaction).where(
            Transaction.import_id == row.id,
            Transaction.family_id == current.family_id,
        )
    ).rowcount
    row.status = "DESCARTADO"
    row.rows_imported = 0
    db.flush()

    return {
        "desfeita": True,
        "lancamentos_apagados": apagados,
        "importacao": _serialize(row),
    }


@router.get("")
def list_imports(current: CurrentMember, db: DbSession, limit: int = 20) -> list[dict]:
    rows = db.scalars(
        select(StatementImport)
        .where(StatementImport.family_id == current.family_id)
        .order_by(StatementImport.created_at.desc())
        .limit(limit)
    ).all()
    # a listagem nao carrega o preview inteiro: sao centenas de linhas por lote
    return [{k: v for k, v in _serialize(row).items() if k != "preview"} for row in rows]


@router.get("/{import_id}")
def get_import(import_id: UUID, current: CurrentMember, db: DbSession) -> dict:
    row = db.get(StatementImport, import_id)
    if not row or row.family_id != current.family_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Importacao nao encontrada")
    return _serialize(row)
