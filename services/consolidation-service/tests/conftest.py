import os
from pathlib import Path

_TEST_DB_PATH = Path(__file__).parent / "test_consolidation.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB_PATH}"
os.environ["API_KEY"] = "test-api-key"
os.environ["REDIS_HOST"] = "localhost"
os.environ["REDIS_PORT"] = "6399"
os.environ["MAX_CONCURRENCY"] = "50"

from unittest.mock import patch  # noqa: E402

import fakeredis  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.infra.db import Base, SessionLocal, engine  # noqa: E402
from app.infra.repository import EventProcessor  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def _clean_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def _isolated_cache():
    """Every test gets an empty in-process cache.

    Without this the cache client points at a real Redis, so a local `docker compose up`
    would let cached balances survive _clean_database and leak between tests and between
    runs — a test could pass or fail depending on what an earlier run left behind.
    """
    with patch("app.infra.cache._client", fakeredis.FakeRedis(decode_responses=True)):
        yield


@pytest.fixture
def client() -> TestClient:
    return TestClient(app, headers={"X-API-Key": "test-api-key"})


@pytest.fixture
def event_processor() -> EventProcessor:
    return EventProcessor(SessionLocal)
