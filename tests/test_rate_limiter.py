from __future__ import annotations

import time

import pytest

from app.core.config import Environment, LLMProvider, Settings
from app.middleware.rate_limiter import RateLimiterMiddleware


@pytest.fixture
def settings() -> Settings:
    return Settings(
        llm_provider=LLMProvider.GOOGLE,
        openai_api_key="test-key",  # type: ignore[arg-type]
        environment=Environment.TEST,
        rate_limit_rpm=60,
        rate_limit_burst=3,
    )


@pytest.fixture
def limiter(settings: Settings) -> RateLimiterMiddleware:
    return RateLimiterMiddleware(app=None, settings=settings)


def test_first_request_is_allowed(limiter: RateLimiterMiddleware) -> None:
    allowed, _ = limiter._consume("192.168.1.1")
    assert allowed is True


def test_requests_within_burst_are_allowed(limiter: RateLimiterMiddleware) -> None:
    for _ in range(3):
        allowed, _ = limiter._consume("192.168.1.1")
        assert allowed is True


def test_request_exceeding_burst_is_rejected(limiter: RateLimiterMiddleware) -> None:
    for _ in range(3):
        limiter._consume("192.168.1.1")

    allowed, retry_after = limiter._consume("192.168.1.1")
    assert allowed is False
    assert retry_after > 0


def test_different_ips_have_separate_buckets(limiter: RateLimiterMiddleware) -> None:
    for _ in range(3):
        limiter._consume("10.0.0.1")

    allowed, _ = limiter._consume("10.0.0.2")
    assert allowed is True


def test_tokens_refill_over_time(limiter: RateLimiterMiddleware) -> None:
    for _ in range(3):
        limiter._consume("192.168.1.1")

    rejected, _ = limiter._consume("192.168.1.1")
    assert rejected is False

    bucket = limiter._buckets["192.168.1.1"]
    bucket.last_refill = time.monotonic() - 10

    allowed, _ = limiter._consume("192.168.1.1")
    assert allowed is True


def test_retry_after_is_positive_when_rejected(limiter: RateLimiterMiddleware) -> None:
    for _ in range(3):
        limiter._consume("192.168.1.1")

    _, retry_after = limiter._consume("192.168.1.1")
    assert retry_after > 0


def test_bucket_tokens_decrease_on_consume(limiter: RateLimiterMiddleware) -> None:
    limiter._consume("192.168.1.1")
    bucket = limiter._buckets["192.168.1.1"]
    assert bucket.tokens == pytest.approx(limiter._max_tokens - 1, abs=0.01)
