"""Application configuration with privacy-preserving defaults."""

from functools import lru_cache
from pathlib import Path

from dateutil.tz import gettz
from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


READONLY_GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
DEFAULT_TIMEZONE = "America/Los_Angeles"


class Settings(BaseSettings):
    """Configuration loaded from environment variables or a local .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="GMAIL_ASSISTANT_",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    credentials_path: Path = Path("credentials.json")
    token_path: Path = Path("token.json")
    query: str = Field(
        default="in:inbox is:unread",
        min_length=1,
        max_length=512,
        validation_alias=AliasChoices(
            "GMAIL_ASSISTANT_QUERY",
            "GMAIL_ASSISTANT_UNREAD_QUERY",
        ),
    )
    max_messages: int = Field(default=100, ge=1, le=500)
    default_timezone: str = DEFAULT_TIMEZONE
    log_level: str = "INFO"

    @field_validator("default_timezone")
    @classmethod
    def validate_default_timezone(cls, value: str) -> str:
        """Reject unknown zones instead of silently using the host timezone."""

        if gettz(value) is None:
            raise ValueError("default_timezone must be a recognized IANA timezone")
        return value

    @property
    def unread_query(self) -> str:
        """Compatibility alias for the original unread-only setting name."""

        return self.query

    @property
    def gmail_scopes(self) -> tuple[str, ...]:
        """Return the immutable minimum scope requested by Phase 1."""

        return (READONLY_GMAIL_SCOPE,)


@lru_cache
def get_settings() -> Settings:
    """Return one settings instance for the application process."""

    return Settings()
