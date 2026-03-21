from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_returns_200(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_response_has_required_fields(client: AsyncClient) -> None:
    response = await client.get("/health")
    body = response.json()

    assert "status" in body
    assert "version" in body
    assert "environment" in body
    assert "dependencies" in body
    assert isinstance(body["dependencies"], list)


@pytest.mark.asyncio
async def test_health_status_is_ok(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_health_environment_is_test(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.json()["environment"] == "test"


@pytest.mark.asyncio
async def test_health_also_reachable_at_versioned_path(client: AsyncClient) -> None:
    r1 = await client.get("/health")
    r2 = await client.get("/api/v1/health")

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json() == r2.json()


@pytest.mark.asyncio
async def test_health_content_type_is_json(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert "application/json" in response.headers["content-type"]
