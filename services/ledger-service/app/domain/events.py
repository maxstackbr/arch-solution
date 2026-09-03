from datetime import datetime, timezone
from uuid import uuid4

from app.domain.models import Entry


def build_entry_created_payload(entry: Entry) -> dict:
    """Builds the wire format for the EntryCreated event (contract in docs/03-api-contracts.md).

    event_id is generated here (not reused from entry.id) because it identifies this specific
    publication attempt, which is what the consumer's idempotency check keys off of (ADR 0006).
    """
    return {
        "event_id": str(uuid4()),
        "event_type": "EntryCreated",
        "entry_id": str(entry.id),
        "amount": str(entry.amount),
        "type": entry.type.value,
        "occurred_at": entry.occurred_at.isoformat(),
        "occurred_date": entry.occurred_at.date().isoformat(),
        "published_at": datetime.now(timezone.utc).isoformat(),
    }
