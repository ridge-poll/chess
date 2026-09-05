from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.analysis import router as analysis_router
from app.api.chesscom import router as chesscom_router
from app.api.dashboard import router as dashboard_router
from app.api.games import router as games_router
from app.api.imports import router as imports_router
from app.api.openings import router as openings_router
from app.api.profiles import router as profiles_router
from app.config import settings
from app.db import init_db
from app.logging_config import configure_logging
from app.services.analysis_jobs import mark_interrupted_jobs_failed
from app.services.maintenance import backfill_openings, backfill_time_classes, repair_analysis_metrics

configure_logging()
init_db()
mark_interrupted_jobs_failed()
repair_analysis_metrics()
backfill_time_classes()
backfill_openings()

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(imports_router)
app.include_router(analysis_router)
app.include_router(chesscom_router)
app.include_router(games_router)
app.include_router(openings_router)
app.include_router(dashboard_router)
app.include_router(profiles_router)

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend" / "static"
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
