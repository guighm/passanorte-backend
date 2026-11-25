from typing import Annotated

from pydantic import AwareDatetime, BaseModel, Field, field_validator


class LedgerEntryInput(BaseModel):
    tourist_id: Annotated[str, Field(min_length=1, max_length=36)]
    source_type: Annotated[str, Field(min_length=1, max_length=64)]
    source_id: Annotated[str, Field(min_length=1, max_length=128)]
    amount: int
    occurred_at: AwareDatetime

    @field_validator("amount")
    @classmethod
    def require_nonzero_amount(cls, amount: int) -> int:
        if amount == 0:
            raise ValueError("Ledger entry amount must be nonzero")
        return amount


class LedgerEntryRecord(LedgerEntryInput):
    id: str
