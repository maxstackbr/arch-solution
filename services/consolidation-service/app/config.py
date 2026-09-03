import socket

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./consolidation.db"
    redis_host: str = "localhost"
    redis_port: int = 6379
    event_stream_name: str = "ledger.entry.created"
    consumer_group: str = "consolidation-workers"
    # Must be unique per worker process: consumer groups track pending messages per
    # consumer name, so sharing one name across scaled-out replicas would make them
    # contend for each other's pending entries. The container hostname is unique per
    # replica under both `docker compose --scale` and ECS.
    consumer_name: str = f"worker-{socket.gethostname()}"
    api_key: str = "local-dev-key-change-me"
    # No browser client ships with this challenge, so cross-origin access is denied by
    # default and CORS_ORIGINS is the explicit opt-in (docs/05-security.md).
    cors_origins: list[str] = []
    max_concurrency: int = 50
    cache_ttl_today_seconds: int = 5
    cache_ttl_past_seconds: int = 86400


settings = Settings()
