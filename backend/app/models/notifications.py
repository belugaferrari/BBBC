"""Para onde os avisos vao: aparelhos com push e enderecos de e-mail."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, SmallInteger, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, PKUuid, pg_enum, uuid_fk
from app.models.enums import NotificationChannel


class NotificationTarget(PKUuid, Base):
    __tablename__ = "notification_targets"

    family_id: Mapped[UUID] = uuid_fk("families.id", nullable=False)
    member_id: Mapped[UUID] = uuid_fk("members.id", nullable=False)
    channel: Mapped[NotificationChannel] = mapped_column(
        pg_enum(NotificationChannel, "notification_channel"), nullable=False
    )
    # token do Expo (push) ou endereco de e-mail
    address: Mapped[str] = mapped_column(Text, nullable=False)
    device_name: Mapped[str | None] = mapped_column(Text)
    platform: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class NotificationDelivery(PKUuid, Base):
    """Uma linha por (alerta, destino): e o que impede o mesmo aviso de chegar
    duas vezes no mesmo aparelho quando o envio e reexecutado."""

    __tablename__ = "notification_deliveries"

    alert_id: Mapped[UUID] = uuid_fk("alerts.id", nullable=False)
    target_id: Mapped[UUID] = uuid_fk("notification_targets.id", nullable=False)
    status: Mapped[str] = mapped_column(Text, default="PENDENTE")
    attempts: Mapped[int] = mapped_column(SmallInteger, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
