"""Router interno: recálculo de progresión de un usuario (servicio a servicio / pruebas).

El secreto de servicio se exige a nivel de router: dispara trabajo de recálculo, así que no
debe poder invocarse desde fuera de la red interna aunque alguien alcance el puerto.
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from progression_service.api.deps import get_progression_service, require_internal_key
from progression_service.api.schemas.ranks import RankMeResponse, RankResponse
from progression_service.application.services.progression_service import ProgressionService
from progression_service.domain.services import rank_evaluator

router = APIRouter(
    prefix="/internal",
    tags=["internal"],
    dependencies=[Depends(require_internal_key)],
)


@router.post(
    "/recalculate/{user_id}",
    response_model=RankMeResponse,
    summary="Recalcular stats + rango + logros + ranking de un usuario",
)
async def recalculate(
    user_id: str,
    service: Annotated[ProgressionService, Depends(get_progression_service)],
) -> RankMeResponse:
    progression = await service.recalculate(user_id)
    current, nxt, progress = rank_evaluator.rank_progress(progression.rank_score)
    return RankMeResponse(
        rank_score=progression.rank_score,
        current=RankResponse.from_definition(current),
        next=RankResponse.from_definition(nxt) if nxt else None,
        progress=progress,
        rank_updated_at=progression.rank_updated_at,
    )
