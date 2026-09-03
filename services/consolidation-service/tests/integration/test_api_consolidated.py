from datetime import date
from decimal import Decimal
from unittest.mock import patch

import fakeredis

from app.infra.db import SessionLocal
from app.infra.models_orm import DailyBalanceORM
from app.infra.repository import EventProcessor


def _amount(json_value) -> Decimal:
    return Decimal(str(json_value))


def test_get_consolidated_for_a_day_with_no_entries_returns_zeroed_balance(client):
    response = client.get("/consolidated/2026-01-01")

    assert response.status_code == 200
    body = response.json()
    assert _amount(body["total_credits"]) == Decimal("0")
    assert body["entry_count"] == 0


def test_get_consolidated_without_api_key_is_unauthorized(client):
    response = client.get("/consolidated/2026-01-01", headers={"X-API-Key": ""})

    assert response.status_code == 401


def test_get_consolidated_reflects_processed_events(client, event_processor):
    event_processor.process(
        {
            "event_id": "evt-100",
            "entry_id": "entry-100",
            "amount": "250.00",
            "type": "CREDIT",
            "occurred_date": "2026-02-01",
        }
    )

    response = client.get("/consolidated/2026-02-01")

    assert response.status_code == 200
    body = response.json()
    assert _amount(body["total_credits"]) == Decimal("250.00")
    assert _amount(body["balance"]) == Decimal("250.00")


def test_health_endpoint_reports_ok(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["database"] == "ok"


def test_second_read_is_served_from_cache_not_database(client, event_processor):
    """Proves the cache-aside behaviour from ADR 0007: patch in a fake broker-free Redis,
    populate the read model, read it once (populates the cache), then delete the underlying
    row directly. If the second read still returns the original value, it came from cache."""
    fake_client = fakeredis.FakeRedis(decode_responses=True)
    event_processor.process(
        {
            "event_id": "evt-200",
            "entry_id": "entry-200",
            "amount": "10.00",
            "type": "CREDIT",
            "occurred_date": "2026-03-01",
        }
    )

    with patch("app.infra.cache._client", fake_client):
        first = client.get("/consolidated/2026-03-01")
        assert _amount(first.json()["total_credits"]) == Decimal("10.00")

        with SessionLocal() as session:
            row = session.get(DailyBalanceORM, date(2026, 3, 1))
            session.delete(row)
            session.commit()

        second = client.get("/consolidated/2026-03-01")

    assert second.status_code == 200
    assert _amount(second.json()["total_credits"]) == Decimal("10.00")


def test_non_ascii_api_key_is_rejected_with_401_not_500():
    """Same regression as the ledger's: a non-ASCII header byte must fail the comparison,
    not raise TypeError out of secrets.compare_digest."""
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as raw_client:
        response = raw_client.get(
            "/consolidated/2026-01-01",
            headers={"X-API-Key": "chave-inválida".encode("latin-1")},
        )

    assert response.status_code == 401


def test_response_carries_a_request_id(client):
    response = client.get("/consolidated/2026-01-01")

    assert response.headers["X-Request-ID"]
