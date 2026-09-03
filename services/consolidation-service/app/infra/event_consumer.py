import json
import logging
import time

import redis

from app.config import settings
from app.infra.repository import EventProcessor
from app.observability.logging import correlation_id
from app.observability.metrics import event_duplicate_total, event_processed_total

logger = logging.getLogger("consolidation.event_consumer")


def ensure_consumer_group(client: redis.Redis) -> None:
    try:
        client.xgroup_create(settings.event_stream_name, settings.consumer_group, id="0", mkstream=True)
    except redis.ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise


def run_consumer_loop(
    processor: EventProcessor,
    *,
    client: redis.Redis | None = None,
    max_iterations: int | None = None,
) -> None:
    """Blocking loop: reads from the shared stream via a consumer group (at-least-once
    delivery), applies each event idempotently, and only ACKs after a successful apply (or a
    confirmed duplicate) — an exception during processing leaves the message pending for
    redelivery instead of being silently dropped.
    """
    client = client or redis.Redis(host=settings.redis_host, port=settings.redis_port, decode_responses=True)
    ensure_consumer_group(client)

    iterations = 0
    while max_iterations is None or iterations < max_iterations:
        iterations += 1
        try:
            response = client.xreadgroup(
                settings.consumer_group,
                settings.consumer_name,
                {settings.event_stream_name: ">"},
                count=10,
                block=5000,
            )
        except redis.ConnectionError:
            logger.warning("event_consumer_broker_unreachable")
            time.sleep(2)
            continue

        if not response:
            continue

        for _stream_name, messages in response:
            for message_id, fields in messages:
                _handle_message(client, processor, message_id, fields)


def _handle_message(client: redis.Redis, processor: EventProcessor, message_id: str, fields: dict) -> None:
    try:
        event = json.loads(fields["data"])
        # The event_id becomes this unit of work's correlation id, and entry_id is logged
        # alongside it so one lançamento can be followed from the ledger's `entry_created`
        # line through to here (docs/04-observability.md).
        correlation_id.set(event.get("event_id"))
        log_context = {"event_id": event.get("event_id"), "entry_id": event.get("entry_id")}

        applied = processor.process(event)
        if applied:
            event_processed_total.inc()
            logger.info("event_applied", extra=log_context)
        else:
            event_duplicate_total.inc()
            logger.info("event_duplicate_skipped", extra=log_context)
        client.xack(settings.event_stream_name, settings.consumer_group, message_id)
    except Exception:
        # Deliberately not ACKed: the message stays pending and is redelivered to this consumer
        # group. Reclaiming pending messages from a *dead* consumer (XCLAIM) is out of scope for
        # the challenge's simplified implementation — see docs/08-future-work.md.
        logger.exception("event_processing_failed", extra={"message_id": message_id})
