from __future__ import annotations

from fastapi import APIRouter
from typing import Optional

from app.services.opening_stats import opening_stats

router = APIRouter(prefix="/api/openings", tags=["openings"])


@router.get("")
async def openings(sort_by: str = "most_played", profile_id: Optional[int] = None) -> list[dict[str, object]]:
    return opening_stats(sort_by, profile_id)
