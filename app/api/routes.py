from __future__ import annotations

import importlib.metadata

from fastapi import APIRouter, Depends
from fastapi import status as http_status

from app.api.dependencies import get_moderation_service, get_settings_dep
from app.core.config import Settings
from app.schemas.health import HealthResponse
from app.schemas.moderation import ModerationRequest, ModerationResponse
from app.services.moderation_service import ModerationService

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


@router.post(
    "/moderate",
    response_model=ModerationResponse,
    status_code=http_status.HTTP_200_OK,
    summary="Moderate content",
    description=(
        "Classifies text across toxicity, spam, PII, and off-topic categories."
        "Returns confidence scores and flags for each category."
    ),
    tags=["Moderation"],
)
async def moderate_content(
    request: ModerationRequest,
    service: ModerationService = Depends(get_moderation_service),
) -> ModerationResponse:
    return await service.moderate(request.text)
