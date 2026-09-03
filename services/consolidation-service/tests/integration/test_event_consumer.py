import json
from datetime import date
from decimal import Decimal

import fakeredis

from app.config import settings
from app.infra.db import SessionLocal
from app.infra.event_consumer import run_consumer_loop
from app.infra.repository import DailyBalanceRepository


def test_consumer_processes_message_and_acks_it(event_processor):
    fake_client = fakeredis.FakeRedis(decode_responses=True)
    event = {
        "event_id": "evt-e2e-1",
        "entry_id": "entry-e2e-1",
        "amount": "75.00",
        "type": "CREDIT",
        "occurred_date": "2026-04-01",
    }
    fake_client.xadd(settings.event_stream_name, {"data": json.dumps(event)})

    run_consumer_loop(event_processor, client=fake_client, max_iterations=1)

    with SessionLocal() as session:
        balance = DailyBalanceRepository(session).get(date(2026, 4, 1))

    assert balance is not None
    assert balance.total_credits == Decimal("75.00")

    pending = fake_client.xpending(settings.event_stream_name, settings.consumer_group)
    assert pending["pending"] == 0


def test_consumer_skips_malformed_message_without_crashing(event_processor):
    fake_client = fakeredis.FakeRedis(decode_responses=True)
    fake_client.xadd(settings.event_stream_name, {"data": "not-valid-json"})

    # Must not raise even though the payload can't be parsed — the loop logs and moves on.
    run_consumer_loop(event_processor, client=fake_client, max_iterations=1)


def test_applied_event_is_logged_with_event_id_and_entry_id(event_processor, caplog):
    """The other half of the end-to-end correlation promised in docs/04-observability.md:
    the worker logs the same entry_id the ledger logged when it created the lançamento."""
    import logging

    fake_client = fakeredis.FakeRedis(decode_responses=True)
    event = {
        "event_id": "evt-log-1",
        "entry_id": "entry-log-1",
        "amount": "10.00",
        "type": "CREDIT",
        "occurred_date": "2026-05-01",
    }
    fake_client.xadd(settings.event_stream_name, {"data": json.dumps(event)})

    with caplog.at_level(logging.INFO, logger="consolidation.event_consumer"):
        run_consumer_loop(event_processor, client=fake_client, max_iterations=1)

    record = next(r for r in caplog.records if r.message == "event_applied")
    assert record.event_id == "evt-log-1"
    assert record.entry_id == "entry-log-1"
