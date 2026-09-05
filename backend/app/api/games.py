from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.services.analysis_queue import analysis_queue
from app.services.games import delete_game, get_game_detail, list_games
from app.services.position_analysis import get_game_positions

router = APIRouter(prefix="/api/games", tags=["games"])


@router.get("")
async def games(profile_id: Optional[int] = None) -> list[dict[str, object]]:
    try:
        return list_games(profile_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{game_id}/positions")
async def game_positions(
    game_id: int,
    profile_id: Optional[int] = None,
    depth: Optional[int] = None,
) -> dict[str, object]:
    try:
        positions = get_game_positions(game_id, profile_id, depth)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not positions:
        raise HTTPException(status_code=404, detail="Game not found.")
    return positions


@router.get("/{game_id}")
async def game_detail(game_id: int, profile_id: Optional[int] = None) -> dict[str, object]:
    try:
        detail = get_game_detail(game_id, profile_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not detail:
        raise HTTPException(status_code=404, detail="Game not found.")
    return detail


@router.delete("/{game_id}")
async def delete_one(game_id: int, profile_id: Optional[int] = None) -> dict[str, object]:
    try:
        deleted = delete_game(game_id, profile_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Game not found.")
    return {"deleted": True, "game_id": game_id}


@router.post("/{game_id}/analyze")
async def analyze_one(game_id: int, depth: Optional[int] = None, profile_id: Optional[int] = None) -> dict[str, object]:
    try:
        return analysis_queue.enqueue_game(game_id, depth or settings.default_depth, profile_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/analyze-all")
async def analyze_everything(depth: Optional[int] = None, profile_id: Optional[int] = None) -> dict[str, object]:
    try:
        return analysis_queue.enqueue_all(depth or settings.default_depth, profile_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
