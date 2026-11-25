import uuid

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from services.benefits.app.db import Base
from shared.audit_model import AuditFields


class Partner(Base):
    __tablename__ = "partners"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255))
    cnpj: Mapped[str] = mapped_column(String(14), unique=True)
    contact: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class PartnerAuditLog(AuditFields, Base):
    __tablename__ = "audit_logs"
