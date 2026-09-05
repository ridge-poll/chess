from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException

from app.services.analysis_queue import analysis_queue

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


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
