from __future__ import annotations

import re

from app.core.logging import get_logger

log = get_logger(__name__)

_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"ignore\s+(all\s+)?previous", re.I),
    re.compile(r"disregard\s+(your\s+)?system", re.I),
    re.compile(r"you\s+are\s+now\s+\w+", re.I),
    re.compile(r"act\s+as\s+(if\s+you\s+are|a)\s+", re.I),
    re.compile(r"system\s*prompt\s*:", re.I),
    re.compile(r"jailbreak", re.I),
    re.compile(r"dan\s+mode", re.I),
    re.compile(r"pretend\s+(you\s+are|to\s+be)", re.I),
]


class InjectionDetector:
    def detect(self, text: str) -> tuple[bool, float, list[str]]:
        matched = [p.pattern for p in _PATTERNS if p.search(text)]
        confidence = min(len(matched) * 0.4, 1.0)
        detected = confidence >= 0.4

        if detected:
            log.warning(
                "injection_attempt_detected",
                confidence=confidence,
                patterns_matched=matched,
                text_preview=text[:100],
            )

        return detected, confidence, matched
