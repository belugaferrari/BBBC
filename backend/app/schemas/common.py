"""Schemas compartilhados."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    member_id: UUID
    family_id: UUID
    full_name: str


class LoginRequest(BaseModel):
    email: str
    password: str


class Money(BaseModel):
    amount: Decimal = Field(decimal_places=2)
    currency: str = "BRL"


class PeriodQuery(BaseModel):
    start: date
    end: date
    scope: str = "familia"  # familia | individual
