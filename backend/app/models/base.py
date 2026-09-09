"""Helpers comuns aos modelos ORM."""

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, func, text
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base

__all__ = ["Base", "PKUuid", "TimestampMixin", "pg_enum", "uuid_fk"]


def pg_enum(enum_cls: type[StrEnum], name: str) -> PGEnum:
    """Mapeia um StrEnum para um tipo ENUM ja criado pela migration."""
    return PGEnum(
        enum_cls,
        name=name,
        create_type=False,
        values_callable=lambda e: [m.value for m in e],
    )


def uuid_fk(target: str, **kwargs: Any) -> Any:
    from sqlalchemy import ForeignKey

    return mapped_column(PGUUID(as_uuid=True), ForeignKey(target), **kwargs)


class PKUuid:
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4,
        server_default=text("gen_random_uuid()"),
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
