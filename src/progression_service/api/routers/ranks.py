"""Router de rangos: catálogo y rango de un usuario."""

from typing import Annotated

from fastapi import APIRouter, Depends

from progression_service.api.deps import get_progression_service
from progression_service.api.schemas.ranks import RankMeResponse, RankResponse
from progression_service.application.services.progression_service import ProgressionService
from progression_service.domain.services import rank_evaluator
from progression_service.domain.services.ranks_config import RANKS

router = APIRouter(prefix="/ranks", tags=["ranks"])


@router.get(
    "",
    response_model=list[RankResponse],
    summary="Listar todos los rangos disponibles",
)
async def list_ranks() -> list[RankResponse]:
    return [RankResponse.from_definition(r) for r in RANKS]


@router.get(
    "/{user_id}",
    response_model=RankMeResponse,
    summary="Rango actual de un usuario y progreso hacia el siguiente",
)
async def get_user_rank(
    user_id: str,
    service: Annotated[ProgressionService, Depends(get_progression_service)],
) -> RankMeResponse:
    progression = await service.get_or_recalculate(user_id)
    current, nxt, progress = rank_evaluator.rank_progress(progression.rank_score)
    return RankMeResponse(
        rank_score=progression.rank_score,
        current=RankResponse.from_definition(current),
        next=RankResponse.from_definition(nxt) if nxt else None,
        progress=progress,
        rank_updated_at=progression.rank_updated_at,
    )
