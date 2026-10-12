"""Modelos do serviço notifications: imports registram as tabelas no metadata do Alembic."""
from services.notifications.app.models.notification import (  # noqa: F401
    Notification,
    NotificationSubscription,
)
