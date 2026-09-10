from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.profiles import (
    create_profile,
    get_active_profile,
    list_profiles,
    set_active_profile,
    update_sync_preferences,
)

router = APIRouter(prefix="/api/profiles", tags=["profiles"])


class ProfileCreatePayload(BaseModel):
    name: str


class ActiveProfilePayload(BaseModel):
    profile_id: int


class SyncPreferencesPayload(BaseModel):
    chesscom_username: Optional[str] = None
    chesscom_sync_days: Optional[int] = None


@router.get("")
async def profiles() -> list[dict[str, object]]:
    return list_profiles()


@router.post("")
async def create(payload: ProfileCreatePayload) -> dict[str, object]:
    try:
        profile = create_profile(payload.name)
        set_active_profile(int(profile["id"]))
        return profile
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/active")
async def active_profile() -> dict[str, object]:
    return get_active_profile()


@router.put("/active")
async def update_active_profile(payload: ActiveProfilePayload) -> dict[str, object]:
    try:
        return set_active_profile(payload.profile_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/{profile_id}/sync-preferences")
async def update_profile_sync_preferences(profile_id: int, payload: SyncPreferencesPayload) -> dict[str, object]:
    try:
        return update_sync_preferences(
            profile_id,
            payload.chesscom_username,
            payload.chesscom_sync_days,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
