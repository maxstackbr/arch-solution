import json
import logging
from datetime import date, datetime, timezone
from decimal import Decimal

import redis

from app.config import settings
from app.domain.models import ConsolidationStatus, DailyBalance

logger = logging.getLogger("consolidation.cache")

_client = redis.Redis(host=settings.redis_host, port=settings.redis_port, decode_responses=True)


def _cache_key(for_date: date) -> str:
    return f"consolidated:{for_date.isoformat()}"


def get_cached_balance(for_date: date) -> DailyBalance | None:
    try:
        raw = _client.get(_cache_key(for_date))
    except Exception:
        logger.warning("cache_read_failed", extra={"date": for_date.isoformat()})
        return None
    if raw is None:
        return None
    data = json.loads(raw)
    return DailyBalance(
        date=date.fromisoformat(data["date"]),
        total_credits=Decimal(data["total_credits"]),
        total_debits=Decimal(data["total_debits"]),
        entry_count=data["entry_count"],
        last_updated_at=datetime.fromisoformat(data["last_updated_at"]),
    )


def set_cached_balance(balance: DailyBalance) -> None:
    # Today's balance still changes as new events arrive, so it gets a short TTL; past days
    # are immutable once written, so a long TTL just avoids serving indefinitely stale data
    # if a manual reconciliation ever rewrites history (see ADR 0007).
    ttl = settings.cache_ttl_today_seconds if balance.status == ConsolidationStatus.PARTIAL else settings.cache_ttl_past_seconds
    payload = {
        "date": balance.date.isoformat(),
        "total_credits": str(balance.total_credits),
        "total_debits": str(balance.total_debits),
        "entry_count": balance.entry_count,
        "last_updated_at": balance.last_updated_at.isoformat(),
    }
    try:
        _client.set(_cache_key(balance.date), json.dumps(payload), ex=ttl)
    except Exception:
        logger.warning("cache_write_failed", extra={"date": balance.date.isoformat()})


def cache_health() -> bool:
    try:
        return bool(_client.ping())
    except Exception:
        return False
