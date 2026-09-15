from functools import lru_cache
from zoneinfo import ZoneInfo

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    discord_bot_token: str
    discord_guild_id: int | None = None

    google_client_id: str
    google_client_secret: str
    google_redirect_uri: str = "http://localhost:8000/oauth/google/callback"

    token_encryption_key: str
    oauth_state_secret: str = Field(min_length=32)

    database_url: str = "sqlite:///data/app.db"
    default_timezone: str = "Asia/Tokyo"
    public_base_url: str = "http://localhost:8000"
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"

    @field_validator("default_timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        ZoneInfo(value)
        return value

    @field_validator("public_base_url")
    @classmethod
    def trim_public_base_url(cls, value: str) -> str:
        return value.rstrip("/")


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
