from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

log = get_logger(__name__)


@dataclass
class BucketState:
    tokens: float
    last_refill: float = field(default_factory=time.monotonic)


class RateLimiterMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, settings: Settings | None = None) -> None:
        super().__init__(app)
        s = settings or get_settings()
        self._max_tokens: float = float(s.rate_limit_burst)
        self._refill_rate: float = s.rate_limit_rpm / 60.0
        self._buckets: dict[str, BucketState] = {}

    def _get_client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _consume(self, ip: str) -> tuple[bool, float]:
        now = time.monotonic()

        if ip not in self._buckets:
            self._buckets[ip] = BucketState(tokens=self._max_tokens)

        bucket = self._buckets[ip]

        elapsed = now - bucket.last_refill
        bucket.tokens = min(
            self._max_tokens,
            bucket.tokens + elapsed * self._refill_rate,
        )
        bucket.last_refill = now

        if bucket.tokens >= 1.0:
            bucket.tokens -= 1.0
            return True, 0.0

        wait = (1.0 - bucket.tokens) / self._refill_rate
        return False, wait

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        if request.url.path == "/health":
            return await call_next(request)

        ip = self._get_client_ip(request)
        allowed, retry_after = self._consume(ip)

        if not allowed:
            log.warning(
                "rate_limit_exceeded",
                client_ip=ip,
                retry_after_seconds=round(retry_after, 2),
            )
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "type": "rate_limit_exceeded",
                        "message": "Too many requests. Please slow down.",
                    }
                },
                headers={"Retry-After": str(int(retry_after) + 1)},
            )

        return await call_next(request)
