from __future__ import annotations

import asyncio
import json
from uuid import uuid4
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from starlette.responses import StreamingResponse

from app.config import settings
from app.services.analysis_queue import analysis_queue
from app.services.engine_analysis import DEFAULT_MULTIPV, analyze_position, progressive_position_results

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


class PositionAnalysisRequest(BaseModel):
    fen: str
    depth: Optional[int] = Field(default=None, ge=1, le=30)
    multipv: int = Field(default=DEFAULT_MULTIPV, ge=1, le=5)
    request_id: Optional[str] = Field(default=None, max_length=100)


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
        return await asyncio.to_thread(
            analyze_position,
            payload.fen,
            payload.depth or settings.default_depth,
            payload.multipv,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/position/stream")
async def progressive_position_analysis(payload: PositionAnalysisRequest, request: Request) -> StreamingResponse:
    request_id = payload.request_id or str(uuid4())
    target_depth = payload.depth or settings.default_depth

    async def stream():
        try:
            async for result in progressive_position_results(
                payload.fen,
                target_depth,
                payload.multipv,
                is_cancelled=request.is_disconnected,
            ):
                yield json.dumps({**result, "request_id": request_id}, separators=(",", ":")) + "\n"
        except ValueError as exc:
            yield json.dumps({"status": "error", "request_id": request_id, "error": str(exc)}) + "\n"
        except Exception as exc:
            yield json.dumps({"status": "error", "request_id": request_id, "error": str(exc)}) + "\n"

    return StreamingResponse(
        stream(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
