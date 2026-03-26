from __future__ import annotations

import json
import time

from app.core.exceptions import LLMOutputError
from app.core.logging import get_logger
from app.schemas.moderation import CategoryScore, ModerationResponse
from app.services.llm_client import LLMClient

log = get_logger(__name__)

EXPECTED_CATEGORIES = {"toxicity", "spam", "pii", "off_topic"}


class OutputValidator:
    def __init__(self, llm_client: LLMClient, max_retries: int = 2) -> None:
        self._llm_client = llm_client
        self._max_retries = max_retries

    async def validate(
        self,
        raw: str,
        text: str,
        context: str | None,
        start_time: float,
        injection_detected: bool,
        model_used: str,
    ) -> ModerationResponse:
        for attempt in range(self._max_retries + 1):
            try:
                return self._parse(
                    raw=raw,
                    start_time=start_time,
                    injection_detected=injection_detected,
                    model_used=model_used,
                )
            except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
                log.warning(
                    "output_validation_failed",
                    attempt=attempt + 1,
                    error=str(exc),
                    raw_preview=raw[:100],
                )

                if attempt >= self._max_retries:
                    raise LLMOutputError(
                        raw_output=raw,
                        attempts=attempt + 1,
                    ) from exc

                raw = await self._llm_client.correct(
                    original_text=text,
                    bad_output=raw,
                    parse_error=str(exc),
                    context=context,
                )

        raise LLMOutputError(raw_output=raw, attempts=self._max_retries + 1)

    def _parse(
        self,
        raw: str,
        start_time: float,
        injection_detected: bool,
        model_used: str,
    ) -> ModerationResponse:
        cleaned = self._strip_fences(raw)

        data = json.loads(cleaned)

        scores_data = data["scores"]

        if not isinstance(scores_data, list):
            raise ValueError("scores must be a list")

        scores = [CategoryScore(**item) for item in scores_data]

        found_categories = {s.category for s in scores}
        missing = EXPECTED_CATEGORIES - found_categories
        if missing:
            raise ValueError(f"Missing categories in response: {missing}")

        overall_flagged = any(s.flagged for s in scores)
        processing_ms = int((time.monotonic() - start_time) * 1000)

        return ModerationResponse(
            scores=scores,
            overall_flagged=overall_flagged,
            injection_detected=injection_detected,
            processing_ms=processing_ms,
            model_used=model_used,
        )

    @staticmethod
    def _strip_fences(raw: str) -> str:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            cleaned = "\n".join(lines[1:-1]).strip()
        return cleaned
