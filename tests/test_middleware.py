from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient

from app.api.dependencies import get_moderation_service
from app.middleware.rate_limiter import RateLimiterMiddleware
from app.schemas.moderation import CategoryScore, ModerationResponse
from app.services.moderation_service import ModerationService


def _mock_response() -> ModerationResponse:
    return ModerationResponse(
        scores=[
            CategoryScore(category="toxicity", score=0.0, flagged=False),
            CategoryScore(category="spam", score=0.0, flagged=False),
            CategoryScore(category="pii", score=0.0, flagged=False),
            CategoryScore(category="off_topic", score=0.0, flagged=False),
        ],
        overall_flagged=False,
        injection_detected=False,
        processing_ms=100,
        model_used="gemini-flash-latest",
    )


@pytest.fixture
def mock_service(app) -> MagicMock:
    service = MagicMock(spec=ModerationService)
    service.moderate = AsyncMock(return_value=_mock_response())
    app.dependency_overrides[get_moderation_service] = lambda: service
    yield service
    app.dependency_overrides.pop(get_moderation_service, None)


@pytest.mark.asyncio
async def test_health_endpoint_not_rate_limited(client: AsyncClient) -> None:
    for _ in range(20):
        response = await client.get("/health")
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_request_logger_logs_successful_request(
    client: AsyncClient,
    mock_service: MagicMock,
) -> None:
    response = await client.post(
        "/moderate",
        json={"text": "test content"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_rate_limiter_allows_requests_in_test_env(
    client: AsyncClient,
    mock_service: MagicMock,
) -> None:
    for _ in range(20):
        response = await client.post(
            "/moderate",
            json={"text": "test content"},
        )
        assert response.status_code == 200


def test_rate_limiter_rejects_after_burst_directly() -> None:
    from app.core.config import Environment, LLMProvider, Settings

    settings = Settings(
        llm_provider=LLMProvider.GOOGLE,
        openai_api_key="test-key",  # type: ignore[arg-type]
        environment=Environment.TEST,
        rate_limit_rpm=60,
        rate_limit_burst=3,
    )
    limiter = RateLimiterMiddleware(app=None, settings=settings)

    for _ in range(3):
        allowed, _ = limiter._consume("10.0.0.1")
        assert allowed is True

    allowed, retry_after = limiter._consume("10.0.0.1")
    assert allowed is False
    assert retry_after > 0
