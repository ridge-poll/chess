from __future__ import annotations

from fastapi import APIRouter
from typing import Optional

from app.services.games import dashboard

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("")
async def get_dashboard(profile_id: Optional[int] = None) -> dict[str, object]:
    return dashboard(profile_id)
