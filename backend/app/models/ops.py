"""Alertas e observabilidade das sincronizacoes."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, PKUuid, pg_enum, uuid_fk
from app.models.enums import AlertSeverity


class Alert(PKUuid, Base):
    __tablename__ = "alerts"

    family_id: Mapped[UUID] = uuid_fk("families.id", nullable=False)
    member_id: Mapped[UUID | None] = uuid_fk("members.id")
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[AlertSeverity] = mapped_column(
        pg_enum(AlertSeverity, "alert_severity"), default=AlertSeverity.INFO
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SyncLog(PKUuid, Base):
    __tablename__ = "sync_logs"

    connection_id: Mapped[UUID | None] = uuid_fk("bank_connections.id")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(Text, default="EXECUTANDO")
    accounts_synced: Mapped[int] = mapped_column(Integer, default=0)
    transactions_created: Mapped[int] = mapped_column(Integer, default=0)
    transactions_updated: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)


class WebhookEvent(PKUuid, Base):
    __tablename__ = "webhook_events"

    provider: Mapped[str] = mapped_column(Text, nullable=False)
    event_id: Mapped[str | None] = mapped_column(Text)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    signature_ok: Mapped[bool] = mapped_column(Boolean, default=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
