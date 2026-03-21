from __future__ import annotations

from app.core.exceptions import (
    AppError,
    InjectionError,
    LLMOutputError,
    LLMTimeoutError,
    RateLimitError,
)


def test_injection_error_stores_fields() -> None:
    exc = InjectionError(confidence=0.9, patterns=["ignore previous"])
    assert exc.confidence == 0.9
    assert exc.patterns == ["ignore previous"]


def test_rate_limit_error_stores_fields() -> None:
    exc = RateLimitError(retry_after_seconds=5.0, client_ip="127.0.0.1")
    assert exc.retry_after_seconds == 5.0


def test_llm_output_error_stores_fields() -> None:
    exc = LLMOutputError(raw_output="broken json", attempts=2)
    assert exc.attempts == 2


def test_llm_timeout_error_stores_fields() -> None:
    exc = LLMTimeoutError(timeout_seconds=10.0, provider="google")
    assert "10.0" in str(exc)


def test_app_error_base() -> None:
    exc = AppError("something failed", key="value")
    assert exc.message == "something failed"
    assert exc.context == {"key": "value"}
