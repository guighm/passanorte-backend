from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from services.benefits.app.db import Base


class LedgerEntry(Base):
    """Immutable economic record reserved for the Benefits use cases."""

    __tablename__ = "ledger"
    __table_args__ = (
        CheckConstraint("amount <> 0", name="ck_ledger_nonzero_amount"),
        UniqueConstraint("source_type", "source_id", name="uq_ledger_source"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tourist_id: Mapped[str] = mapped_column(String(36), index=True)
    amount: Mapped[int] = mapped_column(Integer)
    source_type: Mapped[str] = mapped_column(String(64))
    source_id: Mapped[str] = mapped_column(String(128))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
