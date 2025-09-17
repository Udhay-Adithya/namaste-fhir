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
    search_index_name: str = "namaste-concepts"
    redis_url: str = "redis://localhost:6379/0"

    # ICD-API config (v2.5.0 OAS)
    who_api_base: str = "https://id.who.int/icd/release/11/2025-01"
    who_api_version: str = "v2"
    who_language: str = "en"
    who_release_id: str = "2025-01"
    who_api_token: str | None = None
    who_token_url: str | None = None
    who_client_id: str | None = None
    who_client_secret: str | None = None
    who_scope: str = "icdapi_access"


@lru_cache
def get_settings() -> Settings:
    return Settings()
