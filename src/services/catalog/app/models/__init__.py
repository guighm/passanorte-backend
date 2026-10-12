"""Modelos do serviço catalog: imports registram as tabelas no metadata do Alembic."""
from services.catalog.app.models.audit import AuditLog  # noqa: F401
from services.catalog.app.models.spot import (  # noqa: F401
    Category,
    Event,
    OpeningSchedule,
    SpotCategory,
    SpotStatus,
    TouristSpot,
)
