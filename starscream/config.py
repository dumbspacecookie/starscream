from functools import lru_cache
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg://starscream:starscream@localhost:5432/starscream"
    meilisearch_url: str = "http://localhost:7700"
    meilisearch_api_key: str = ""

    s3_endpoint: str = "http://localhost:9000"
    s3_access_key: str = "starscream"
    s3_secret_key: str = "starscream"
    s3_bucket: str = "starscream-audio"
    s3_region: str = "us-east-1"

    # JSON list of secondary S3-compatible mirrors, e.g. R2 / B2 / Wasabi.
    # [{"name":"r2","endpoint":"https://...","access_key":"...","secret_key":"...","bucket":"..."}]
    mirror_endpoints: list[dict[str, Any]] = []

    api_rate_limit_per_min: int = 1000
    redis_url: str = ""
    peer_review_max_flags_per_recording_per_day: int = 15
    peer_review_max_flags_per_reviewer_per_day: int = 10
    api_trust_proxy_headers: bool = False
    cors_origins: str = "*"
    debug: bool = False
    admin_api_key: str = ""

    freesound_api_key: str = ""
    xeno_canto_api_key: str = ""
    # Catalog-only: federation harvest + export use metadata pointers (no local audio).
    catalog_only: bool = True

    enrich_geocode: bool = True
    enrich_habitat: bool = True
    enrich_weather: bool = True
    enrich_osm: bool = True
    nominatim_user_agent: str = (
        "Starscream/0.1 (sound catalog; https://github.com/dumbspacecookie/starscream)"
    )
    nominatim_rate_limit_s: float = 1.0

    @field_validator("mirror_endpoints", mode="before")
    @classmethod
    def parse_mirror_endpoints(cls, value: Any) -> list[dict[str, Any]]:
        if value is None or value == "":
            return []
        if isinstance(value, str):
            import json

            parsed = json.loads(value)
            if not isinstance(parsed, list):
                raise ValueError("mirror_endpoints must be a JSON array")
            return parsed
        if isinstance(value, list):
            return value
        raise ValueError("mirror_endpoints must be a JSON array or list")


@lru_cache
def get_settings() -> Settings:
    return Settings()
