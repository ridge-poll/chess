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

OLD_PGN = """
[Event "Live Chess"]
[Site "Chess.com"]
[Date "2020.05.30"]
[UTCDate "2020.05.30"]
[UTCTime "12:00:00"]
[White "ridgepoll1"]
[Black "opponent"]
[Result "0-1"]

1. d4 d5 0-1
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


def test_sync_chesscom_archives_filters_recent_games_and_saves_preferences(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "test.sqlite3"
    monkeypatch.setattr(db, "settings", config.Settings(database_path=database_path))
    db.init_db(database_path)

    def fake_json(url: str) -> dict[str, object]:
        return {"archives": [ARCHIVE_URL]}

    def fake_text(url: str) -> str:
        return f"{OLD_PGN}\n\n{PGN}"

    monkeypatch.setattr(chesscom_sync, "_get_json", fake_json)
    monkeypatch.setattr(chesscom_sync, "_get_text", fake_text)
    monkeypatch.setattr(
        chesscom_sync,
        "datetime",
        type(
            "FixedDatetime",
            (),
            {
                "now": staticmethod(lambda tz=None: __import__("datetime").datetime(2026, 6, 1, tzinfo=tz)),
                "strptime": staticmethod(__import__("datetime").datetime.strptime),
            },
        ),
    )

    result = sync_chesscom_archives(SyncOptions(username="RidgePoll1", days=7))

    with db.get_connection(database_path) as conn:
        profile = conn.execute("SELECT * FROM profiles ORDER BY id LIMIT 1").fetchone()
        games = conn.execute("SELECT * FROM games").fetchall()

    assert result["imported"] == 1
    assert profile["chesscom_username"] == "ridgepoll1"
    assert profile["chesscom_sync_days"] == 7
    assert len(games) == 1
    assert games[0]["played_at"].startswith("2026-05-30")
