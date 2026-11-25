from uuid import uuid4

from sqlalchemy.orm import Session

from services.benefits.app.models import LedgerEntry
from services.benefits.app.schemas import LedgerEntryInput, LedgerEntryRecord


def append_ledger_entry(db: Session, entry: LedgerEntryInput) -> LedgerEntryRecord:
    """Stage an immutable posting in the caller's transaction."""
    record = LedgerEntryRecord(id=str(uuid4()), **entry.model_dump())
    db.add(LedgerEntry(**record.model_dump()))
    db.flush()
    return record
