from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.pgn.openings import detect_opening_from_san
from app.services.opening_stats import opening_stats

router = APIRouter(prefix="/api/openings", tags=["openings"])


class OpeningDetectPayload(BaseModel):
    sans: list[str]


@router.get("")
async def openings(sort_by: str = "most_played", profile_id: Optional[int] = None) -> list[dict[str, object]]:
    return opening_stats(sort_by, profile_id)


@router.post("/detect")
async def detect_opening(payload: OpeningDetectPayload) -> dict[str, object]:
    opening = detect_opening_from_san(payload.sans)
    return {"opening": opening, "identified": opening is not None}
