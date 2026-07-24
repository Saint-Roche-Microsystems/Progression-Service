"""Router de logros: catálogo y logros de un usuario."""

from typing import Annotated

from fastapi import APIRouter, Depends

from progression_service.api.deps import get_progression_service
from progression_service.api.schemas.achievements import (
    AchievementResponse,
    AchievementsMeResponse,
    UserAchievementResponse,
)
from progression_service.application.services.progression_service import ProgressionService
from progression_service.domain.services.achievements_catalog import CATALOG

router = APIRouter(prefix="/achievements", tags=["achievements"])


@router.get(
    "",
    response_model=list[AchievementResponse],
    summary="Catálogo completo de logros",
)
async def list_achievements() -> list[AchievementResponse]:
    return [AchievementResponse.from_definition(a) for a in CATALOG]


@router.get(
    "/{user_id}",
    response_model=AchievementsMeResponse,
    summary="Logros desbloqueados y pendientes de un usuario",
)
async def get_user_achievements(
    user_id: str,
    service: Annotated[ProgressionService, Depends(get_progression_service)],
) -> AchievementsMeResponse:
    progression = await service.get_or_recalculate(user_id)
    unlocked = progression.unlocked
    achievements = [
        UserAchievementResponse.from_definition_state(a, unlocked.get(a.id)) for a in CATALOG
    ]
    return AchievementsMeResponse(
        unlocked_count=len(unlocked),
        total=len(CATALOG),
        achievements=achievements,
    )
