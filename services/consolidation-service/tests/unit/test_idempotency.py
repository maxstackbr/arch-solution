"""The second most important test in this repository.

Redis Streams consumer groups deliver at-least-once: a crash between processing and ACKing a
message causes redelivery. Without the idempotency check, processing the same event twice would
double-count a lançamento in the daily balance. See docs/adr/0006-consumidor-idempotente.md.
"""

from datetime import date
from decimal import Decimal

from app.infra.db import SessionLocal
from app.infra.repository import DailyBalanceRepository


def _event(event_id: str, occurred_date: str, amount: str, entry_type: str) -> dict:
    return {
        "event_id": event_id,
        "event_type": "EntryCreated",
        "entry_id": "entry-1",
        "amount": amount,
        "type": entry_type,
        "occurred_date": occurred_date,
    }


def test_processing_same_event_twice_does_not_duplicate_balance(event_processor):
    event = _event("evt-1", "2026-08-31", "100.00", "CREDIT")

    first_result = event_processor.process(event)
    second_result = event_processor.process(event)

    assert first_result is True
    assert second_result is False

    with SessionLocal() as session:
        balance = DailyBalanceRepository(session).get(date(2026, 8, 31))

    assert balance.total_credits == Decimal("100.00")
    assert balance.entry_count == 1


def test_processing_distinct_events_accumulates_correctly(event_processor):
    event_processor.process(_event("evt-1", "2026-08-31", "100.00", "CREDIT"))
    event_processor.process(_event("evt-2", "2026-08-31", "30.00", "DEBIT"))

    with SessionLocal() as session:
        balance = DailyBalanceRepository(session).get(date(2026, 8, 31))

    assert balance.total_credits == Decimal("100.00")
    assert balance.total_debits == Decimal("30.00")
    assert balance.balance == Decimal("70.00")
    assert balance.entry_count == 2
