"""Opt-in model configuration kept separate from Gmail application settings."""

from __future__ import annotations

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ModelSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=None,
        extra="ignore",
        populate_by_name=True,
    )

    provider: str = Field(
        default="disabled", validation_alias="GMAIL_ASSISTANT_MODEL_PROVIDER"
    )
    model: str = Field(
        default="gpt-5.6-terra",
        validation_alias=AliasChoices("GMAIL_ASSISTANT_MODEL", "GMAIL_ASSISTANT_MODEL_NAME"),
    )
    reasoning_effort: str = Field(
        default="medium", validation_alias="GMAIL_ASSISTANT_MODEL_REASONING"
    )
    service_tier: str = Field(
        default="default", validation_alias="GMAIL_ASSISTANT_MODEL_SERVICE_TIER"
    )
    request_timeout_seconds: float = Field(
        default=120.0,
        gt=0,
        le=300,
        validation_alias="GMAIL_ASSISTANT_MODEL_TIMEOUT_SECONDS",
    )
    max_workers: int = Field(
        default=4,
        ge=1,
        le=8,
        validation_alias="GMAIL_ASSISTANT_MODEL_MAX_WORKERS",
    )
    api_key: SecretStr | None = Field(default=None, validation_alias="OPENAI_API_KEY")

    @field_validator("provider")
    @classmethod
    def provider_is_opt_in(cls, value: str) -> str:
        normalized = value.casefold()
        if normalized not in {"disabled", "openai"}:
            raise ValueError("model provider must be disabled or openai")
        return normalized

    @field_validator("reasoning_effort")
    @classmethod
    def supported_reasoning(cls, value: str) -> str:
        normalized = value.casefold()
        if normalized not in {"none", "low", "medium", "high", "xhigh", "max"}:
            raise ValueError("unsupported reasoning effort")
        return normalized

    @field_validator("service_tier")
    @classmethod
    def standard_service_only(cls, value: str) -> str:
        normalized = value.casefold()
        if normalized != "default":
            raise ValueError("this milestone permits only service_tier=default")
        return normalized