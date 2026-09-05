from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.services.imports import import_pgn_text, preview_pgn_text

router = APIRouter(prefix="/api/imports", tags=["imports"])


class PgnPayload(BaseModel):
    pgn: str
    profile_id: Optional[int] = None


@router.post("/pgn")
async def import_pgn(payload: PgnPayload) -> dict[str, object]:
    if not payload.pgn.strip():
        raise HTTPException(status_code=400, detail="PGN content is empty.")
    try:
        return import_pgn_text(payload.pgn, payload.profile_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/pgn-file")
async def import_pgn_file(file: UploadFile = File(...), profile_id: Optional[int] = None) -> dict[str, object]:
    content = await file.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        text = content.decode("latin-1")
    if not text.strip():
        raise HTTPException(status_code=400, detail="PGN file is empty.")
    try:
        return import_pgn_text(text, profile_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/preview")
async def preview_pgn(payload: PgnPayload) -> dict[str, object]:
    return preview_pgn_text(payload.pgn)
