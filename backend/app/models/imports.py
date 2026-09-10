"""Importacao de extratos: o lote enviado e o que foi extraido dele."""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import Date, DateTime, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, PKUuid, uuid_fk


class StatementImport(PKUuid, Base):
    """Um arquivo enviado. Nasce em CRIADO (nada gravado) e so vira
    CONFIRMADO depois que o usuario confere a pre-visualizacao."""

    __tablename__ = "statement_imports"

    family_id: Mapped[UUID] = uuid_fk("families.id", nullable=False)
    account_id: Mapped[UUID] = uuid_fk("accounts.id", nullable=False)
    uploaded_by: Mapped[UUID] = uuid_fk("members.id", nullable=False)

    filename: Mapped[str] = mapped_column(Text, nullable=False)
    file_format: Mapped[str] = mapped_column(Text, nullable=False)
    file_hash: Mapped[str] = mapped_column(Text, nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)

    status: Mapped[str] = mapped_column(Text, default="CRIADO")

    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    rows_detected: Mapped[int] = mapped_column(Integer, default=0)
    rows_duplicated: Mapped[int] = mapped_column(Integer, default=0)
    rows_imported: Mapped[int] = mapped_column(Integer, default=0)

    preview: Mapped[list] = mapped_column(JSONB, default=list)
    warnings: Mapped[list] = mapped_column(JSONB, default=list)
    error_message: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
