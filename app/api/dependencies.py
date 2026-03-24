from __future__ import annotations

from functools import lru_cache

from app.core.config import Settings, get_settings
from app.services.moderation_service import ModerationService


def get_settings_dep() -> Settings:
    return get_settings()


@lru_cache(maxsize=1)
def get_moderation_service() -> ModerationService:
    return ModerationService(settings=get_settings())
