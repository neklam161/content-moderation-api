from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ModerationRequest(BaseModel):
    text: str = Field(description="the text content to moderate.")
    context: str | None = Field(
        default=None,
        description="Optional context about where this text came from.",
    )
    metadata: dict[str, str] = Field(
        default_factory=dict,
        description="Optional key-value metadata attached to the request",
    )

    @field_validator("text")
    @classmethod
    def validate_text(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("text cannot be empty or whitespace only.")
        if len(v) > 10_000:
            raise ValueError(f"text exceeds maximum length of 10,000 characters (got {len(v)}).")
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "text": "Buy cheap mded at discount-pharma.biz - limited offer!!",
                "context": "product_review",
                "metadata": {"user_id": "u_123", "platform": "marketplace"},
            }
        }
    }


class CategoryScore(BaseModel):
    category: Literal["toxicity", "spam", "pii", "off_topic"] = Field(
        description="The moderation category being scored."
    )
    score: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score between 0.0 (clean) and 1.0 (definite violation).",
    )
    flagged: bool = Field(description="True if this category is flagged for review or rejection")
    reason: str | None = Field(
        default=None,
        description="Human-readable explanation of why this category was flagged.",
    )


class ModerationResponse(BaseModel):
    scores: list[CategoryScore] = Field(description="Score for each moderation category")
    overall_flagged: bool = Field(description="True if any category is flagged")
    injection_detected: bool = Field(
        description="True if a prompt injection attempt was detected in the input."
    )
    processing_ms: int = Field(
        description="Total time taken taken to processs the request in milliseconds"
    )
    model_used: str = Field(description="The LLM model identifier used to classify this request")

    model_config = {
        "json_schema_extra": {
            "example": {
                "scores": [
                    {
                        "category": "toxicity",
                        "score": 0.05,
                        "flagged": False,
                        "reason": None,
                    },
                    {
                        "category": "spam",
                        "score": 0.94,
                        "flagged": True,
                        "reason": "Contains promotional language and suspicious URL.",
                    },
                    {
                        "category": "pii",
                        "score": 0.02,
                        "flagged": False,
                        "reason": None,
                    },
                    {
                        "category": "off_topic",
                        "score": 0.10,
                        "flagged": False,
                        "reason": None,
                    },
                ],
                "overall_flagged": True,
                "injection_detected": False,
                "processing_ms": 1243,
                "model_used": "gemini-2.0-flash",
            }
        }
    }
