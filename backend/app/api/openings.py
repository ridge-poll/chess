from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.pgn.openings import detect_opening_from_san
from app.services.opening_stats import opening_stats
from app.services.repertoire import repertoire_tree

router = APIRouter(prefix="/api/openings", tags=["openings"])


class OpeningDetectPayload(BaseModel):
    sans: list[str]


@router.get("")
async def openings(sort_by: str = "most_played", profile_id: Optional[int] = None) -> list[dict[str, object]]:
    return opening_stats(sort_by, profile_id)


@router.get("/tree")
async def opening_tree(profile_id: Optional[int] = None, max_depth: int = 18) -> dict[str, object]:
    return repertoire_tree(profile_id, max_depth)


@router.post("/detect")
async def detect_opening(payload: OpeningDetectPayload) -> dict[str, object]:
    opening = detect_opening_from_san(payload.sans)
    return {"opening": opening, "identified": opening is not None}
