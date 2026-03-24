from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import Settings, get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.middleware.rate_limiter import RateLimiterMiddleware
from app.middleware.request_logger import RequestLoggerMiddleware

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings

    configure_logging(
        log_level=settings.log_level,
        json_logs=settings.log_json,
    )
    log.info(
        "server_starting",
        provider=settings.llm_provider,
        model=settings.llm_model,
        environment=settings.environment.value,
        rate_limit_rpm=settings.rate_limit_rpm,
    )

    yield

    log.info("server_shutting_down")


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = get_settings()

    app = FastAPI(
        title="Content Moderation API",
        description=(
            "LLM-powered content moderation service. Classifies text across "
            "toxicity, spam, PII, and off-topic categories with confidence scores."
        ),
        version="0.1.0",
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None if settings.is_production else "/redoc",
        lifespan=lifespan,
    )
    app.state.settings = settings

    register_exception_handlers(app)

    allowed_origins = ["*"] if not settings.is_production else []
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    app.add_middleware(RateLimiterMiddleware, settings=settings)
    app.add_middleware(RequestLoggerMiddleware)
    app.include_router(router, prefix="/api/v1")
    app.include_router(router, prefix="", include_in_schema=False)

    return app


app = create_app()
