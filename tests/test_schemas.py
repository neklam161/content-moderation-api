from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.moderation import CategoryScore, ModerationRequest, ModerationResponse


def test_moderation_request_valid() -> None:
    req = ModerationRequest(text="This is a normal review.")
    assert req.text == "This is a normal review."
    assert req.context is None
    assert req.metadata == {}


def test_moderation_request_empty_text_raises() -> None:
    with pytest.raises(ValidationError, match="cannot be empty"):
        ModerationRequest(text="   ")


def test_moderation_request_too_long_raises() -> None:
    with pytest.raises(ValidationError, match="exceeds maximum length"):
        ModerationRequest(text="x" * 10_001)


def test_moderation_request_exactly_max_length_passes() -> None:
    req = ModerationRequest(text="x" * 10_000)
    assert len(req.text) == 10_000


def test_category_score_valid() -> None:
    score = CategoryScore(category="spam", score=0.95, flagged=True, reason="Spam detected.")
    assert score.score == 0.95
    assert score.flagged is True


def test_category_score_out_of_range_raises() -> None:
    with pytest.raises(ValidationError):
        CategoryScore(category="spam", score=1.5, flagged=True)


def test_moderation_response_overall_flagged() -> None:
    response = ModerationResponse(
        scores=[
            CategoryScore(category="toxicity", score=0.1, flagged=False),
            CategoryScore(category="spam", score=0.9, flagged=True, reason="Spam."),
            CategoryScore(category="pii", score=0.0, flagged=False),
            CategoryScore(category="off_topic", score=0.0, flagged=False),
        ],
        overall_flagged=True,
        injection_detected=False,
        processing_ms=500,
        model_used="gemini-2.0-flash",
    )
    assert response.overall_flagged is True
    assert response.processing_ms == 500
