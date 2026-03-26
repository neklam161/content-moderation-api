from __future__ import annotations

import time

from app.core.config import Settings
from app.core.exceptions import InjectionError
from app.core.logging import get_logger
from app.schemas.moderation import ModerationResponse
from app.services.injection_detector import InjectionDetector
from app.services.llm_client import LLMClient
from app.services.output_validator import OutputValidator

log = get_logger(__name__)


class ModerationService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._llm_client = LLMClient(settings)
        self._injection_detector = InjectionDetector()
        self._output_validator = OutputValidator(
            llm_client=self._llm_client,
            max_retries=settings.max_retries,
        )

    async def moderate(self, text: str, context: str | None = None) -> ModerationResponse:
        start = time.monotonic()

        detected, confidence, patterns = self._injection_detector.detect(text)

        if confidence >= self._settings.injection_confidence_threshold:
            log.warning(
                "request_rejected_injection",
                confidence=confidence,
                patterns=patterns,
            )
            raise InjectionError(confidence=confidence, patterns=patterns)

        log.info("moderation_started", text_length=len(text), has_context=context is not None)

        raw = await self._llm_client.classify(text, context=context)

        response = await self._output_validator.validate(
            raw=raw,
            text=text,
            context=context,
            start_time=start,
            injection_detected=detected,
            model_used=self._settings.llm_model,
        )

        log.info(
            "moderation_complete",
            overall_flagged=response.overall_flagged,
            processing_ms=response.processing_ms,
            injection_detected=detected,
        )

        return response
