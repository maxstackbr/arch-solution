from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./ledger.db"
    redis_host: str = "localhost"
    redis_port: int = 6379
    event_stream_name: str = "ledger.entry.created"
    api_key: str = "local-dev-key-change-me"
    # No browser client ships with this challenge, so cross-origin access is denied by
    # default and CORS_ORIGINS is the explicit opt-in (docs/05-security.md).
    cors_origins: list[str] = []


settings = Settings()
