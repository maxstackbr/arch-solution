"""The most important test in this repository.

It proves RNF-1 in code: if the broker is unreachable when the ledger tries to publish
the EntryCreated event, that failure must never surface as an error to the API caller.
See docs/adr/0005-outbox-vs-publish-best-effort.md.
"""

from decimal import Decimal
from unittest.mock import patch

from app.domain.models import Entry, EntryType
from app.infra.event_publisher import EventPublisher
from app.observability.metrics import event_publish_failures_total


def test_publish_failure_does_not_raise():
    entry = Entry.create(amount=Decimal("50.00"), type=EntryType.CREDIT, description="Venda")
    publisher = EventPublisher()

    with patch.object(publisher, "_client") as mock_client:
        mock_client.xadd.side_effect = ConnectionError("redis is down")

        result = publisher.publish_entry_created(entry)  # must not raise

    assert result is False


def _counter_value() -> float:
    return event_publish_failures_total.collect()[0].samples[0].value


def test_publish_failure_increments_failure_metric():
    entry = Entry.create(amount=Decimal("50.00"), type=EntryType.CREDIT, description="Venda")
    publisher = EventPublisher()
    before = _counter_value()

    with patch.object(publisher, "_client") as mock_client:
        mock_client.xadd.side_effect = ConnectionError("redis is down")
        publisher.publish_entry_created(entry)

    assert _counter_value() == before + 1


def test_publish_success_returns_true():
    entry = Entry.create(amount=Decimal("50.00"), type=EntryType.CREDIT, description="Venda")
    publisher = EventPublisher()

    with patch.object(publisher, "_client") as mock_client:
        result = publisher.publish_entry_created(entry)

    assert result is True
    mock_client.xadd.assert_called_once()
