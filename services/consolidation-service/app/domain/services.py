from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal

from app.domain.models import DailyBalance


def entry_deltas(*, amount: Decimal, entry_type: str) -> tuple[Decimal, Decimal]:
    """How much one EntryCreated event adds to (total_credits, total_debits).

    Kept separate from apply_entry so the repository can turn the same rule into an atomic
    `SET total_credits = total_credits + :delta` UPDATE, without loading the row first.
    """
    if entry_type == "CREDIT":
        return amount, Decimal("0")
    if entry_type == "DEBIT":
        return Decimal("0"), amount
    raise ValueError(f"unknown entry type: {entry_type!r}")


def apply_entry(balance: DailyBalance, *, amount: Decimal, entry_type: str) -> DailyBalance:
    """Incrementally folds one EntryCreated event into a DailyBalance (ADR 0003).

    Pure function, no I/O — this is what test_domain_services.py exercises directly.
    """
    credit_delta, debit_delta = entry_deltas(amount=amount, entry_type=entry_type)
    return replace(
        balance,
        total_credits=balance.total_credits + credit_delta,
        total_debits=balance.total_debits + debit_delta,
        entry_count=balance.entry_count + 1,
        last_updated_at=datetime.now(timezone.utc),
    )
