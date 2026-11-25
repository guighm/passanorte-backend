"""Persistent refresh-token families; raw tokens are never stored."""
from sqlalchemy import BigInteger, Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from services.auth.app.db import Base


class RefreshSession(Base):
    __tablename__ = "refresh_sessions"
    jti_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    family_id: Mapped[str] = mapped_column(String(32), index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    expires_at: Mapped[int] = mapped_column(BigInteger)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
