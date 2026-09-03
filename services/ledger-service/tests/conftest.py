import os
from pathlib import Path

_TEST_DB_PATH = Path(__file__).parent / "test_ledger.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB_PATH}"
os.environ["API_KEY"] = "test-api-key"
# The integration tests must exercise the "broker unreachable" path for real, so they point at
# a port nothing listens on. Port 6379 would silently connect to a local `docker compose up`
# Redis and quietly stop testing what these tests claim to test.
os.environ["REDIS_HOST"] = "localhost"
os.environ["REDIS_PORT"] = "6399"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.infra.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def _clean_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app, headers={"X-API-Key": "test-api-key"})
