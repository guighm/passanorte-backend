"""Modelos do serviço auth: imports registram as tabelas no metadata do Alembic."""
from services.auth.app.models.audit import AuditLog  # noqa: F401
from services.auth.app.models.user import TouristInterest, TouristProfile, User, UserRole  # noqa: F401
