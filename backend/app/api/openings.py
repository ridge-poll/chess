from __future__ import annotations

from typing import Literal, Optional

import asyncio

from fastapi import APIRouter
from pydantic import BaseModel

from app.pgn.openings import detect_opening_from_san
from app.services.opening_stats import opening_stats
from app.services.master_openings import MasterExplorerUnavailable, master_opening_position
from app.services.repertoire import repertoire_graph, repertoire_tree

router = APIRouter(prefix="/api/openings", tags=["openings"])


class OpeningDetectPayload(BaseModel):
    sans: list[str]


@router.get("")
async def openings(sort_by: str = "most_played", profile_id: Optional[int] = None) -> list[dict[str, object]]:
    return opening_stats(sort_by, profile_id)


@router.get("/tree")
async def opening_tree(profile_id: Optional[int] = None, max_depth: int = 18) -> dict[str, object]:
    return repertoire_tree(profile_id, max_depth)


@router.get("/repertoire")
async def opening_repertoire(
    color: Literal["white", "black"],
    profile_id: Optional[int] = None,
    max_depth: int = 24,
) -> dict[str, object]:
    return repertoire_graph(color, profile_id, max_depth)


@router.get("/masters")
async def master_openings(fen: str, moves: int = 12) -> dict[str, object]:
    try:
        return await asyncio.to_thread(master_opening_position, fen, moves)
    except ValueError as exc:
        return {"status": "invalid", "source": "masters", "moves": [], "error": str(exc)}
    except MasterExplorerUnavailable as exc:
        return {"status": "unavailable", "source": "masters", "moves": [], "error": str(exc)}


@router.post("/detect")
async def detect_opening(payload: OpeningDetectPayload) -> dict[str, object]:
    opening = detect_opening_from_san(payload.sans)
    return {"opening": opening, "identified": opening is not None}
