from pathlib import Path

import app.config as config
import app.db as db
import app.services.chesscom_sync as chesscom_sync
from app.services.chesscom_sync import SyncOptions, get_chesscom_syncs, sync_chesscom_archives


ARCHIVE_URL = "https://api.chess.com/pub/player/ridgepoll1/games/2026/05"
PGN = """
[Event "Live Chess"]
[Site "Chess.com"]
[Date "2026.05.30"]
[White "ridgepoll1"]
[Black "opponent"]
[Result "1-0"]

1. e4 e5 2. Nf3 Nc6 1-0
"""


def test_sync_chesscom_archives_imports_and_records_archive(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "test.sqlite3"
    monkeypatch.setattr(db, "settings", config.Settings(database_path=database_path))
    db.init_db(database_path)

    def fake_json(url: str) -> dict[str, object]:
        assert url.endswith("/games/archives")
        return {"archives": [ARCHIVE_URL]}

    def fake_text(url: str) -> str:
        assert url == f"{ARCHIVE_URL}/pgn"
        return PGN

    monkeypatch.setattr(chesscom_sync, "_get_json", fake_json)
    monkeypatch.setattr(chesscom_sync, "_get_text", fake_text)

    first = sync_chesscom_archives(SyncOptions(username="RidgePoll1", limit=1))
    second = sync_chesscom_archives(SyncOptions(username="RidgePoll1", limit=1))
    syncs = get_chesscom_syncs("ridgepoll1")

    assert first["imported"] == 1
    assert second["results"][0]["status"] == "skipped"
    assert len(syncs) == 1
    assert syncs[0]["status"] == "complete"
