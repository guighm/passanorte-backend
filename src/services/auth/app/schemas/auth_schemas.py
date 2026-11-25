"""Schemas Pydantic do serviço auth (Princípio II)."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, EmailStr, Field, model_validator

from shared.documents import normalize_passport, normalize_tax_id
from shared.security import validate_password

CONSENT_VERSION = "1"


class TouristCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    surname: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: Annotated[str, AfterValidator(validate_password)] = Field(min_length=8)
    phone: str = Field(min_length=5, max_length=40)
    country_of_origin: str = Field(min_length=2, max_length=120)
    cpf: str | None = Field(default=None, description="Cadastro único por CPF ou passaporte (RF22)")
    passport: str | None = None
    consent_version: Literal["1"]
    accept_terms: Literal[True]
    accept_privacy: Literal[True]
    category_ids: list[str] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def normalize_documents(self) -> TouristCreate:
        if (self.cpf is None) == (self.passport is None):
            raise ValueError("Informe exatamente um CPF ou passaporte.")
        if self.cpf is not None:
            self.cpf = normalize_tax_id(self.cpf)
        if self.passport is not None:
            self.passport = normalize_passport(self.passport)
        return self


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    panel: bool = False


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str = "bearer"


class MeResponse(BaseModel):
    id: str
    role: str
    name: str
    surname: str
    email: EmailStr
    country_of_origin: str
    partner_id: str | None = None


class MeUpdate(BaseModel):
    name: str | None = None
    surname: str | None = None
    phone: str | None = None


class InterestsUpdate(BaseModel):
    category_ids: list[str] = Field(default_factory=list)


class InterestsResponse(BaseModel):
    category_ids: list[str]
