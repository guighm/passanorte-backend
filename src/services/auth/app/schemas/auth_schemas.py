"""Schemas Pydantic do serviço auth (Princípio II)."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class TouristCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    surname: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8)
    phone: str = Field(min_length=5, max_length=40)
    country_of_origin: str = Field(min_length=2, max_length=120)
    cpf: str | None = Field(default=None, description="Cadastro único por CPF ou passaporte (RF22)")
    passport: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


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


class MeUpdate(BaseModel):
    name: str | None = None
    surname: str | None = None
    phone: str | None = None


class InterestsUpdate(BaseModel):
    category_ids: list[str] = Field(default_factory=list)


class InterestsResponse(BaseModel):
    category_ids: list[str]
