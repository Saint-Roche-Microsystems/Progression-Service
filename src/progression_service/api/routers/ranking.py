"""Router del ranking global de usuarios."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from progression_service.api.deps import get_ranking_service
from progression_service.api.schemas.ranking import RankingEntry, RankingPage, RankingPosition
from progression_service.application.services.ranking_service import RankingService

router = APIRouter(prefix="/ranking", tags=["ranking"])


@router.get(
    "",
    response_model=RankingPage,
    summary="Ranking global paginado (orden por ranking_score)",
)
async def get_ranking(
    service: Annotated[RankingService, Depends(get_ranking_service)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> RankingPage:
    items, total, start = await service.get_ranking(page=page, page_size=page_size)
    return RankingPage(
        items=[RankingEntry.from_entity(s, start + i) for i, s in enumerate(items)],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/top",
    response_model=list[RankingEntry],
    summary="Top de usuarios (por defecto Top 10)",
)
async def get_top(
    service: Annotated[RankingService, Depends(get_ranking_service)],
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
) -> list[RankingEntry]:
    items = await service.get_top(limit)
    return [RankingEntry.from_entity(s, i + 1) for i, s in enumerate(items)]


@router.get(
    "/{user_id}",
    response_model=RankingPosition,
    summary="Posición de un usuario en el ranking",
)
async def get_user_position(
    user_id: str,
    service: Annotated[RankingService, Depends(get_ranking_service)],
) -> RankingPosition:
    position, stats = await service.get_user_position(user_id)
    entry = RankingEntry.from_entity(stats, position) if stats and position else None
    return RankingPosition(position=position, entry=entry)
