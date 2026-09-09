"""Importacao de extratos bancarios (OFX, CSV, PDF).

Dois passos por seguranca: `POST /imports` le o arquivo e devolve a
pre-visualizacao sem gravar nada; `POST /imports/{id}/confirm` grava o que voce
conferiu.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import CurrentMember, DbSession, owned_account, owned_category
from app.models import StatementImport
from app.services.import_service import build_preview, confirm_import
from app.services.importers.base import StatementParseError
from app.services.importers.detect import MAX_FILE_BYTES, SUPPORTED

router = APIRouter(prefix="/imports", tags=["importacao"])


def _serialize(row: StatementImport) -> dict:
    return {
        "id": row.id,
        "account_id": row.account_id,
        "filename": row.filename,
        "file_format": row.file_format,
        "status": row.status,
        "period_start": row.period_start,
        "period_end": row.period_end,
        "rows_detected": row.rows_detected,
        "rows_duplicated": row.rows_duplicated,
        "rows_imported": row.rows_imported,
        "warnings": row.warnings,
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
    na pre-visualizacao (tudo que nao foi detectado como duplicado)."""

    selected_indexes: list[int] | None = None
    category_overrides: dict[int, UUID] | None = None


@router.post("/{import_id}/confirm")
def confirm(
    import_id: UUID, payload: ConfirmIn, current: CurrentMember, db: DbSession
) -> dict:
    row = db.get(StatementImport, import_id)
    if not row or row.family_id != current.family_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Importacao nao encontrada")

    for category_id in (payload.category_overrides or {}).values():
        owned_category(db, category_id, current)

    try:
        confirm_import(
            db,
            row,
            selected_indexes=payload.selected_indexes,
            category_overrides=payload.category_overrides,
        )
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
