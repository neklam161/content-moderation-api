from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse


class AppError(Exception):
    def __init__(self, message: str, **context: object) -> None:
        super().__init__(message)
        self.message = message
        self.context = context


class LLMError(AppError):
    pass


class LLMOutputError(LLMError):
    def __init__(self, *, raw_output: str, attempts: int) -> None:
        super().__init__(
            "LLM output could not be parsed after retries",
            raw_output=raw_output[:200],
            attempts=attempts,
        )
        self.raw_output = raw_output
        self.attempts = attempts


class LLMTimeoutError(LLMError):
    def __init__(self, *, timeout_seconds: float, provider: str) -> None:
        super().__init__(
            f"LLM API call timed out after {timeout_seconds}s",
            timeout_seconds=timeout_seconds,
            provider=provider,
        )


class InjectionError(AppError):
    def __init__(self, *, confidence: float, patterns: list[str]) -> None:
        super().__init__(
            "Request rejected: prompt injection detected",
            confidence=confidence,
            patterns_matched=patterns,
        )
        self.confidence = confidence
        self.patterns = patterns


class RateLimitError(AppError):
    def __init__(self, *, retry_after_seconds: float, client_ip: str) -> None:
        super().__init__(
            "Rate limit exceeded",
            retry_after_seconds=retry_after_seconds,
            client_ip=client_ip,
        )
        self.retry_after_seconds = retry_after_seconds


# ── FastAPI exception handlers ─────────────────────────────────────────────────


def _error_body(error_type: str, message: str, **extra: object) -> dict[str, object]:

    return {"error": {"type": error_type, "message": message, **extra}}

async def injection_error_handler(
    request: Request, exc: InjectionError
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=_error_body(
            "injection_detected",
            exc.message,
            confidence=exc.confidence,
        ),
    )


async def rate_limit_error_handler(
    request: Request, exc: RateLimitError
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content=_error_body("rate_limit_exceeded", exc.message),
        headers={"Retry-After": str(int(exc.retry_after_seconds))},
    )


async def llm_output_error_handler(
    request: Request, exc: LLMOutputError
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content=_error_body(
            "llm_output_error",
            "The AI model returned an unexpected response. Please try again.",
            # Don't expose raw_output to callers — it may contain sensitive content.
        ),
    )


async def llm_timeout_error_handler(
    request: Request, exc: LLMTimeoutError
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_504_GATEWAY_TIMEOUT,
        content=_error_body("llm_timeout", "The AI model took too long to respond."),
    )


async def generic_app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Catch-all for any AppError subclass not handled above."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_error_body("internal_error", "An unexpected error occurred."),
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all custom exception handlers with the FastAPI app.

    Called once in main.py — keeps main.py clean.
    """
    app.add_exception_handler(InjectionError, injection_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RateLimitError, rate_limit_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(LLMOutputError, llm_output_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(LLMTimeoutError, llm_timeout_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(AppError, generic_app_error_handler)  # type: ignore[arg-type]
