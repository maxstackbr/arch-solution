import json
import logging

import redis

from app.config import settings
from app.domain.events import build_entry_created_payload
from app.domain.models import Entry
from app.observability.metrics import event_publish_failures_total

logger = logging.getLogger("ledger.event_publisher")


class EventPublisher:
    """Publishes EntryCreated events best-effort (see ADR 0005).

    publish() MUST NEVER raise: a broker outage is not allowed to turn into a failed
    POST /entries response, since that would violate RNF-1 (the ledger must stay available
    even if the consolidation side — and the broker it depends on — is down).
    """

    def __init__(self):
        self._client = redis.Redis(
            host=settings.redis_host, port=settings.redis_port, decode_responses=True
        )

    def publish_entry_created(self, entry: Entry) -> bool:
        payload = build_entry_created_payload(entry)
        try:
            self._client.xadd(settings.event_stream_name, {"data": json.dumps(payload)})
            return True
        except Exception:
            logger.exception("event_publish_failed", extra={"entry_id": str(entry.id)})
            event_publish_failures_total.inc()
            return False


publisher = EventPublisher()
