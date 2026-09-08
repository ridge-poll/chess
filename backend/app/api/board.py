from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.board_workspace import build_position, load_game_workspace, play_move

router = APIRouter(prefix="/api/board", tags=["board"])


class BoardPositionRequest(BaseModel):
    moves: list[str] = Field(default_factory=list)
    starting_fen: Optional[str] = None
    selected_ply: Optional[int] = None
    include_engine: bool = False
    depth: Optional[int] = None


class BoardMoveRequest(BoardPositionRequest):
    move: str


@router.post("/position")
async def board_position(payload: BoardPositionRequest) -> dict[str, object]:
    try:
        return build_position(
            moves=payload.moves,
            starting_fen=payload.starting_fen,
            selected_ply=payload.selected_ply,
            include_engine=payload.include_engine,
            depth=payload.depth,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/move")
async def board_move(payload: BoardMoveRequest) -> dict[str, object]:
    try:
        return play_move(
            move=payload.move,
            moves=payload.moves,
            starting_fen=payload.starting_fen,
            selected_ply=payload.selected_ply,
            include_engine=payload.include_engine,
            depth=payload.depth,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/games/{game_id}")
async def game_board(game_id: int, profile_id: Optional[int] = None) -> dict[str, object]:
    workspace = load_game_workspace(game_id, profile_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Game not found")
    return workspace
