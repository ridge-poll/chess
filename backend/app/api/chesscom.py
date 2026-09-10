from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.chesscom_sync import SyncOptions, get_chesscom_syncs, sync_chesscom_archives

router = APIRouter(prefix="/api/chesscom", tags=["chesscom"])


class ChessComSyncPayload(BaseModel):
    username: str
    limit: Optional[int] = None
    days: Optional[int] = 7
    force: bool = False
    profile_id: Optional[int] = None


@router.post("/sync")
async def sync(payload: ChessComSyncPayload) -> dict[str, object]:
    try:
        return sync_chesscom_archives(
            SyncOptions(
                username=payload.username,
                limit=payload.limit,
                days=payload.days,
                force=payload.force,
                profile_id=payload.profile_id,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/syncs")
async def syncs(username: Optional[str] = None, profile_id: Optional[int] = None) -> list[dict[str, object]]:
    return get_chesscom_syncs(username, profile_id)
