from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient

from app.api.dependencies import get_moderation_service
from app.schemas.moderation import CategoryScore, ModerationResponse
from app.services.moderation_service import ModerationService


def _mock_response(overall_flagged: bool = False) -> ModerationResponse:
    return ModerationResponse(
        scores=[
            CategoryScore(category="toxicity", score=0.01, flagged=False),
            CategoryScore(
                category="spam",
                score=0.95 if overall_flagged else 0.02,
                flagged=overall_flagged,
                reason="Spam detected." if overall_flagged else None,
            ),
            CategoryScore(category="pii", score=0.00, flagged=False),
            CategoryScore(category="off_topic", score=0.05, flagged=False),
        ],
        overall_flagged=overall_flagged,
        injection_detected=False,
        processing_ms=500,
        model_used="gemini-flash-latest",
    )


@pytest.fixture
def mock_service(app) -> MagicMock:
    service = MagicMock(spec=ModerationService)
    service.moderate = AsyncMock(return_value=_mock_response())
    app.dependency_overrides[get_moderation_service] = lambda: service
    yield service
    app.dependency_overrides.pop(get_moderation_service, None)


@pytest.fixture
def mock_service_flagged(app) -> MagicMock:
    service = MagicMock(spec=ModerationService)
    service.moderate = AsyncMock(return_value=_mock_response(overall_flagged=True))
    app.dependency_overrides[get_moderation_service] = lambda: service
    yield service
    app.dependency_overrides.pop(get_moderation_service, None)


@pytest.mark.asyncio
async def test_moderate_returns_200(
    client: AsyncClient,
    mock_service: MagicMock,
) -> None:
    response = await client.post(
        "/moderate",
        json={"text": "This is a normal review."},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_moderate_response_has_required_fields(
    client: AsyncClient,
    mock_service: MagicMock,
) -> None:
    response = await client.post(
        "/moderate",
        json={"text": "This is a normal review."},
    )
    body = response.json()

    assert "scores" in body
    assert "overall_flagged" in body
    assert "injection_detected" in body
    assert "processing_ms" in body
    assert "model_used" in body


@pytest.mark.asyncio
async def test_moderate_returns_four_categories(
    client: AsyncClient,
    mock_service: MagicMock,
) -> None:
    response = await client.post(
        "/moderate",
        json={"text": "This is a normal review."},
    )
    categories = [s["category"] for s in response.json()["scores"]]
    assert set(categories) == {"toxicity", "spam", "pii", "off_topic"}


@pytest.mark.asyncio
async def test_moderate_empty_text_returns_422(
    client: AsyncClient,
    mock_service: MagicMock,
) -> None:
    response = await client.post("/moderate", json={"text": "   "})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_moderate_missing_text_returns_422(
    client: AsyncClient,
    mock_service: MagicMock,
) -> None:
    response = await client.post("/moderate", json={})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_moderate_flagged_response(
    client: AsyncClient,
    mock_service_flagged: MagicMock,
) -> None:
    response = await client.post(
        "/moderate",
        json={"text": "Buy cheap meds at discount-pharma.biz!!!"},
    )
    body = response.json()

    assert response.status_code == 200
    assert body["overall_flagged"] is True
    spam = next(s for s in body["scores"] if s["category"] == "spam")
    assert spam["flagged"] is True
    assert spam["reason"] == "Spam detected."


@pytest.mark.asyncio
async def test_moderate_calls_service_with_text(
    client: AsyncClient,
    mock_service: MagicMock,
) -> None:
    await client.post("/moderate", json={"text": "some user content"})
    mock_service.moderate.assert_called_once_with("some user content", context=None)


@pytest.mark.asyncio
async def test_moderate_also_reachable_at_versioned_path(
    client: AsyncClient,
    mock_service: MagicMock,
) -> None:
    response = await client.post(
        "/api/v1/moderate",
        json={"text": "some user content"},
    )
    assert response.status_code == 200
