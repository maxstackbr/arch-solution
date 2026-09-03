import logging

from app.config import settings
from app.infra.db import Base, SessionLocal, engine
from app.infra.event_consumer import run_consumer_loop
from app.infra.repository import EventProcessor
from app.observability.logging import configure_logging

configure_logging("consolidation-worker")
logger = logging.getLogger("consolidation-worker")


def main() -> None:
    Base.metadata.create_all(bind=engine)
    processor = EventProcessor(SessionLocal)
    logger.info(
        "consumer_starting",
        extra={"stream": settings.event_stream_name, "group": settings.consumer_group},
    )
    run_consumer_loop(processor)


if __name__ == "__main__":
    main()
