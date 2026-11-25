from services.gamification.app.db import Base
from shared.audit_model import AuditFields


class AuditLog(AuditFields, Base):
    __tablename__ = "audit_logs"
