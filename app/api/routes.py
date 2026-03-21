from __future__ import annotations

import importlib.metadata

from fastapi import APIRouter, Depends
from fastapi import status as http_status

from app.api.dependencies import get_settings_dep
from app.core.config import Settings
from app.schemas.health import HealthResponse

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=http_status.HTTP_200_OK,
    summary="Health check",
    description=("Returns the operational status of the service"),
    tags=["Observability"],
)
async def health_check(
    settings: Settings = Depends(get_settings_dep),
) -> HealthResponse:
    try:
        version = importlib.metadata.version("content-moderation-api")
    except importlib.metadata.PackageNotFoundError:
        version = "0.1.0-dev"

    return HealthResponse(
        status="ok",
        version=version,
        environment=settings.environment.value,
        dependencies=[],
    )
