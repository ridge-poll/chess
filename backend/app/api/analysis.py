from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import settings
from app.services.analysis_queue import analysis_queue
from app.services.engine_analysis import DEFAULT_MULTIPV, analyze_position

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


class PositionAnalysisRequest(BaseModel):
    fen: str
    depth: Optional[int] = None
    multipv: int = Field(default=DEFAULT_MULTIPV, ge=1, le=5)


@router.get("/jobs")
async def jobs(profile_id: Optional[int] = None) -> dict[str, object]:
    return analysis_queue.status(profile_id)


@router.post("/games/{game_id}")
async def enqueue_game(game_id: int, depth: Optional[int] = None, profile_id: Optional[int] = None) -> dict[str, object]:
    try:
        return analysis_queue.enqueue_game(game_id, depth, profile_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/all")
async def enqueue_all(depth: Optional[int] = None, profile_id: Optional[int] = None) -> dict[str, object]:
    return analysis_queue.enqueue_all(depth, profile_id)


@router.post("/position")
async def position_analysis(payload: PositionAnalysisRequest) -> dict[str, object]:
    try:
        return analyze_position(payload.fen, payload.depth or settings.default_depth, payload.multipv)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
