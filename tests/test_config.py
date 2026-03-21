from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Environment, LLMProvider, Settings


def test_settings_valid_google_config() -> None:
    s = Settings(
        llm_provider=LLMProvider.GOOGLE,
        google_api_key="test-key",  # type: ignore[arg-type]
        environment=Environment.TEST,
    )
    assert s.llm_provider == LLMProvider.GOOGLE


def test_settings_google_requires_api_key() -> None:
    with pytest.raises(ValidationError, match="OPENAI_API_KEY is required"):
        Settings(
            llm_provider=LLMProvider.GOOGLE,
            openai_api_key=None,
            environment=Environment.TEST,
        )


def test_settings_invalid_log_level_raises() -> None:
    with pytest.raises(ValidationError):
        Settings(
            llm_provider=LLMProvider.GOOGLE,
            google_api_key="test-key",  # type: ignore[arg-type]
            log_level="VERBOSE",
            environment=Environment.TEST,
        )


def test_settings_api_key_masked_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    s = Settings(
        llm_provider=LLMProvider.GOOGLE,
        openai_api_key="super-secret-key",  # type: ignore[arg-type]
        environment=Environment.TEST,
    )
    assert "super-secret-key" not in repr(s)
    assert s.openai_api_key is not None
    assert s.openai_api_key.get_secret_value() == "super-secret-key"


def test_settings_rate_limit_below_minimum_raises() -> None:
    with pytest.raises(ValidationError):
        Settings(
            llm_provider=LLMProvider.GOOGLE,
            google_api_key="test-key",  # type: ignore[arg-type]
            rate_limit_rpm=0,
            environment=Environment.TEST,
        )


def test_settings_is_test_property() -> None:
    s = Settings(
        llm_provider=LLMProvider.GOOGLE,
        google_api_key="test-key",  # type: ignore[arg-type]
        environment=Environment.TEST,
    )
    assert s.is_test is True
    assert s.is_production is False


def test_settings_active_api_key_returns_google_key() -> None:
    s = Settings(
        llm_provider=LLMProvider.GOOGLE,
        openai_api_key="my-gemini-key",  # type: ignore[arg-type]
        environment=Environment.TEST,
    )
    assert s.active_api_key.get_secret_value() == "my-gemini-key"
