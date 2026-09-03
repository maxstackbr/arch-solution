def test_create_entry_returns_201(client):
    response = client.post(
        "/entries",
        json={"amount": "150.00", "type": "CREDIT", "description": "Venda balcão"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["amount"] == "150.00"
    assert body["type"] == "CREDIT"
    assert body["id"]


def test_create_entry_succeeds_even_though_no_broker_is_running(client):
    """No Redis is available in the test environment (see conftest.py) — this proves
    RNF-1 end-to-end through the real HTTP layer, not just against the publisher in isolation."""
    response = client.post(
        "/entries",
        json={"amount": "10.00", "type": "DEBIT", "description": "Pagamento fornecedor"},
    )

    assert response.status_code == 201


def test_create_entry_rejects_non_positive_amount(client):
    response = client.post(
        "/entries", json={"amount": "0", "type": "CREDIT", "description": "Inválido"}
    )

    assert response.status_code == 422


def test_create_entry_without_api_key_is_unauthorized(client):
    response = client.post(
        "/entries",
        json={"amount": "10.00", "type": "CREDIT", "description": "Venda"},
        headers={"X-API-Key": ""},
    )

    assert response.status_code == 401


def test_get_entry_by_id(client):
    created = client.post(
        "/entries", json={"amount": "20.00", "type": "CREDIT", "description": "Venda"}
    ).json()

    response = client.get(f"/entries/{created['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_get_entry_not_found(client):
    response = client.get("/entries/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404


def test_list_entries_returns_created_entries(client):
    client.post("/entries", json={"amount": "5.00", "type": "CREDIT", "description": "A"})
    client.post("/entries", json={"amount": "7.00", "type": "DEBIT", "description": "B"})

    response = client.get("/entries")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 2
    assert len(body["items"]) >= 2


def test_health_endpoint(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_non_ascii_api_key_is_rejected_with_401_not_500():
    """Header values reach the app latin-1 decoded, so a non-ASCII byte used to make the
    constant-time comparison raise TypeError — surfacing as a 500 with a stack trace instead
    of a plain 401. Sent as raw bytes here because that is how it arrives on the wire."""
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as raw_client:
        response = raw_client.post(
            "/entries",
            json={"amount": "10.00", "type": "CREDIT", "description": "Venda"},
            headers={"X-API-Key": "chave-inválida".encode("latin-1")},
        )

    assert response.status_code == 401


def test_response_carries_a_request_id(client):
    response = client.get("/entries")

    assert response.headers["X-Request-ID"]


def test_client_supplied_request_id_is_echoed_back(client):
    response = client.get("/entries", headers={"X-Request-ID": "req-abc-123"})

    assert response.headers["X-Request-ID"] == "req-abc-123"


def test_entry_created_is_logged_with_entry_id_and_request_id(client, caplog):
    """docs/04-observability.md promises a lançamento can be followed end to end by
    entry_id, with a request_id correlating everything logged for one request."""
    import logging

    with caplog.at_level(logging.INFO, logger="ledger.entries"):
        created = client.post(
            "/entries",
            json={"amount": "12.00", "type": "CREDIT", "description": "Venda"},
            headers={"X-Request-ID": "req-log-1"},
        ).json()

    record = next(r for r in caplog.records if r.message == "entry_created")
    assert record.entry_id == created["id"]
    assert record.request_id == "req-log-1"
