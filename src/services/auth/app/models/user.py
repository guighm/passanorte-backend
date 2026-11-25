"""Modelos de identidade do serviço auth (T015, data-model.md).

Regras de unicidade: email único; CPF OU passaporte único via hash HMAC
(FR-006) — os valores sensíveis ficam criptografados (Fernet, RNF08).
"""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from services.auth.app.db import Base


class UserRole(str, enum.Enum):
    admin = "admin"
    supplier = "supplier"
    tourist = "tourist"


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role != 'supplier' OR partner_id IS NOT NULL OR NOT is_active",
                        name="ck_active_supplier_partner"),
        Index("uq_users_email_lower", text("lower(email)"), unique=True),
        Index("uq_users_normalized_document", text("coalesce(cpf_hash, passport_hash)"), unique=True),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    surname: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    # PII criptografado (RNF08) + hashes HMAC de unicidade (FR-006)
    phone_encrypted: Mapped[str | None] = mapped_column(String(512))
    cpf_encrypted: Mapped[str | None] = mapped_column(String(512))
    cpf_hash: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    passport_encrypted: Mapped[str | None] = mapped_column(String(512))
    passport_hash: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    country_of_origin: Mapped[str] = mapped_column(String(120), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    partner_id: Mapped[str | None] = mapped_column(String(36), index=True)


class TouristProfile(Base):
    """Preferências do turista (1:1 com User turista)."""

    __tablename__ = "tourist_profiles"

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), primary_key=True)
    consent_version: Mapped[str | None] = mapped_column(String(40))
    consent_at: Mapped[object | None] = mapped_column(DateTime(timezone=True))


class TouristInterest(Base):
    """Inscrição de interesse do turista (RF25); category_id vem do catálogo."""

    __tablename__ = "tourist_interests"
    __table_args__ = (UniqueConstraint("user_id", "category_id", name="uq_user_category"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("tourist_profiles.user_id"), index=True)
    category_id: Mapped[str] = mapped_column(String(36), index=True)
