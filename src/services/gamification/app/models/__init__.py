"""Modelos do serviço gamification: imports registram as tabelas no metadata do Alembic."""
from services.gamification.app.models.enrollment import (  # noqa: F401
    Badge,
    CodeStatus,
    EnrollmentStatus,
    RedeemCode,
    RouteEnrollment,
)
from services.gamification.app.models.route import Prize, Route, RoutePoint  # noqa: F401
