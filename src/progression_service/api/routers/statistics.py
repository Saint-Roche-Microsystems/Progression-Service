"""Router de estadísticas de un usuario."""

from typing import Annotated

from fastapi import APIRouter, Depends

from progression_service.api.deps import get_statistics_service
from progression_service.api.schemas.statistics import StatisticsResponse
from progression_service.application.services.statistics_service import StatisticsService

router = APIRouter(prefix="/statistics", tags=["statistics"])


@router.get(
    "/{user_id}",
    response_model=StatisticsResponse,
    summary="Estadísticas de un usuario",
)
async def get_statistics(
    user_id: str,
    service: Annotated[StatisticsService, Depends(get_statistics_service)],
) -> StatisticsResponse:
    stats = await service.get_or_recalculate(user_id)
    return StatisticsResponse.from_entity(stats)
