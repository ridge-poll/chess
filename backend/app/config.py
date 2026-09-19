from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    app_name: str = "Chess Analytics"
    database_path: Path = Path(
        os.environ.get(
            "CHESS_ANALYTICS_DB",
            Path(__file__).resolve().parents[1] / "data" / "chess_analytics.sqlite3",
        )
    )
    stockfish_path: str = os.environ.get("STOCKFISH_PATH", "stockfish")
    default_depth: int = int(os.environ.get("STOCKFISH_DEPTH", "10"))
    lichess_api_token: str = os.environ.get("LICHESS_API_TOKEN", "")
    lichess_explorer_url: str = os.environ.get(
        "LICHESS_EXPLORER_URL",
        "https://explorer.lichess.org/masters",
    )
    opening_explorer_cache_seconds: int = int(os.environ.get("OPENING_EXPLORER_CACHE_SECONDS", "21600"))


settings = Settings()
