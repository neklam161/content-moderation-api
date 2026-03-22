from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_settings_dep
from app.core.config import Environment, LLMProvider, Settings, get_settings
from app.main import create_app


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    return Settings(
        llm_provider=LLMProvider.GOOGLE,
        openai_api_key="test-key-not-real",  # type: ignore[arg-type]
        llm_model="gemini-2.0-flash",
        environment=Environment.TEST,
        rate_limit_rpm=10,
        rate_limit_burst=3,
        log_level="WARNING",
        log_json=False,
    )


@pytest.fixture(scope="session")
def app(test_settings: Settings) -> FastAPI:
    get_settings.cache_clear()
    application = create_app(settings=test_settings)
    application.dependency_overrides[get_settings_dep] = lambda: test_settings
    return application


@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac
