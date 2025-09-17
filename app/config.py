from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "namaste-fhir"
    app_env: str = "dev"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "info"
    allowed_origins: str = "*"

    oauth2_issuer: str = "https://abha.mock"
    oauth2_audience: str = "namaste-fhir"
    jwt_secret: str = "change-me"
    jwt_alg: str = "HS256"
    access_token_expire_minutes: int = 60

    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/namaste_fhir"
    )
    elasticsearch_url: str = "http://localhost:9200"
    redis_url: str = "redis://localhost:6379/0"

    who_api_base: str = "https://id.who.int/icd/release/11/2024-01"
    who_api_token: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
