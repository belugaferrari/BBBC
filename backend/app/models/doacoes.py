"""Quem doa dinheiro para a familia.

Existe como tabela propria, e nao como mais um `Member`, porque sogro e sogra nao
sao da casa: nao tem conta, nao tem gasto, nao entram em "quanto cada um gastou"
nem na visao individual. O que se quer deles e uma coisa so - somar por pessoa e
por ano, porque o limite de isencao do ITCMD e por doador.

Sem CPF, de proposito. O sistema nao declara nada por ninguem, e guardar o
documento de terceiro so aumentaria o estrago de um vazamento.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, PKUuid, TimestampMixin, uuid_fk


class Donor(PKUuid, TimestampMixin, Base):
    __tablename__ = "donors"

    family_id: Mapped[UUID] = uuid_fk("families.id", nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    # "sogro", "mae", "padrinho" - para a tela dizer de quem se trata sem exigir
    # que o nome carregue isso
    relationship: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
