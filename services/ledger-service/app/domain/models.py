from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from uuid import UUID, uuid4


class EntryType(str, Enum):
    CREDIT = "CREDIT"
    DEBIT = "DEBIT"


class EntryValidationError(ValueError):
    pass


@dataclass(frozen=True)
class Entry:
    """A single, immutable ledger entry. There is no update/delete by design —
    corrections are made by recording a new reversing entry (see docs/00-domain-mapping.md)."""

    id: UUID
    amount: Decimal
    type: EntryType
    description: str
    occurred_at: datetime
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def create(
        cls,
        *,
        amount: Decimal,
        type: EntryType,
        description: str,
        occurred_at: datetime | None = None,
    ) -> "Entry":
        if amount <= 0:
            raise EntryValidationError("amount must be greater than zero")
        if not description or not description.strip():
            raise EntryValidationError("description must not be empty")
        return cls(
            id=uuid4(),
            amount=amount,
            type=type,
            description=description.strip(),
            occurred_at=occurred_at or datetime.now(timezone.utc),
        )
