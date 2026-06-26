from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "fastapi-pg-redis"
    environment: str = "development"
    log_level: str = "INFO"

    # Postgres. Railway/Heroku style "postgres://" is normalized in database.py.
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/app"
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_timeout: int = 30

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    cache_ttl_seconds: int = 60

    # HTTP/runtime
    request_timeout_seconds: float = 15.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
