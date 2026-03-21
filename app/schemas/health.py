from __future__ import annotations

from pydantic import BaseModel, Field


class DependencyStatus(BaseModel):
    name: str
    healthy: bool
    latency_ms: int | None = None
    error: str | None = None


class HealthResponse(BaseModel):
    status: str = Field(
    description="'ok' when healthy, 'degraded' when some deps are unhealthy."
    )
    version: str = Field(description="Application version string from pyproject.toml")
    environment: str = Field(
        description="Runtime environment (development / production / test)."
    )

    dependencies: list[DependencyStatus] = Field(
        default_factory=list, description="Status of downstream dependencies."
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "ok",
                "version": "0.1.1",
                "environment": "development",
                "dependencies": [],
            }
        }
    }
