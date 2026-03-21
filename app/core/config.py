# core/config.py
from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from typing import Annotated

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMProvider(StrEnum):
    OPENAI = "openai"
    GOOGLE = "google"
    OLLAMA = "ollama"


class Environment(StrEnum):
    DEVELOPMENT = "development"
    PRODUCTION = "production"
    TEST = "test"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    llm_provider: LLMProvider = Field(
        default=LLMProvider.GOOGLE,
        description="Which LLM provider to use.",
    )
    openai_api_key: SecretStr | None = Field(
        default=None,
        description="API key for OpenAI or Gemini (Google).",
    )
    llm_base_url: str | None = Field(
        default=None,
        description="Override API base URL. Required for Gemini and local Ollama.",
    )
    llm_model: str = Field(
        default="gemini-2.0-flash",
        description="Model identifier.",
    )
    llm_max_tokens: Annotated[int, Field(ge=64, le=4096)] = Field(
        default=512,
        description="Max tokens in LLM response.",
    )
    llm_timeout_seconds: Annotated[float, Field(ge=1.0, le=60.0)] = Field(
        default=10.0,
        description="HTTP timeout for LLM API calls.",
    )
    max_retries: Annotated[int, Field(ge=0, le=5)] = Field(
        default=2,
        description="Max retry attempts when LLM returns malformed output.",
    )
    rate_limit_rpm: Annotated[int, Field(ge=1, le=10_000)] = Field(
        default=60,
        description="Max requests per minute per IP address.",
    )
    rate_limit_burst: Annotated[int, Field(ge=1, le=1_000)] = Field(
        default=10,
        description="Token bucket burst capacity.",
    )
    environment: Environment = Field(
        default=Environment.DEVELOPMENT,
        description="Runtime environment.",
    )
    max_input_chars: Annotated[int, Field(ge=100, le=100_000)] = Field(
        default=10_000,
        description="Maximum allowed characters in a moderation request.",
    )
    injection_confidence_threshold: Annotated[float, Field(ge=0.0, le=1.0)] = Field(
        default=0.8,
        description=(
            "Injection confidence score at or above which the request is rejected."
        ),
    )
    log_level: str = Field(
        default="INFO",
        description="structlog log level: DEBUG, INFO, WARNING, ERROR, CRITICAL.",
    )
    log_json: bool = Field(
        default=False,
        description="True: JSON logs. False: human-readable coloured logs.",
    )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in allowed:
            raise ValueError(f"log_level must be one of {allowed}, got {v!r}")
        return upper

    @model_validator(mode="after")
    def validate_api_key_present(self) -> Settings:
        if (
            self.llm_provider in (LLMProvider.OPENAI, LLMProvider.GOOGLE)
            and not self.openai_api_key
        ):
            raise ValueError(
                "OPENAI_API_KEY is required for openai and google providers."
            )
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == Environment.PRODUCTION

    @property
    def is_test(self) -> bool:
        return self.environment == Environment.TEST

    @property
    def active_api_key(self) -> SecretStr:
        match self.llm_provider:
            case LLMProvider.OPENAI | LLMProvider.GOOGLE:
                assert self.openai_api_key is not None
                return self.openai_api_key
            case LLMProvider.OLLAMA:
                return SecretStr("ollama")
            case _:
                raise NotImplementedError(
                    f"No API key configured for provider: {self.llm_provider}"
                )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
