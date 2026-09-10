from pathlib import Path

import app.config as config
import app.db as db
from app.pgn.openings import detect_opening_from_san
from app.services.imports import import_pgn_text
from app.services.opening_stats import opening_stats


PGN = """
[Event "Live Chess"]
[Site "Chess.com"]
[Date "2026.06.01"]
[White "ridgepoll1"]
[Black "opponent1"]
[Result "1-0"]
[TimeControl "600"]

1. e4 c5 2. Nf3 d6 3. d4 cxd4 1-0

[Event "Live Chess"]
[Site "Chess.com"]
[Date "2026.06.02"]
[White "opponent2"]
[Black "ridgepoll1"]
[Result "0-1"]
[TimeControl "600"]

1. e4 e6 2. d4 d5 3. Nc3 Nf6 0-1
"""


def test_detects_openings_and_reports_opening_stats(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "test.sqlite3"
    monkeypatch.setattr(db, "settings", config.Settings(database_path=database_path))
    db.init_db(database_path)
    import_pgn_text(PGN)

    rows = opening_stats()
    by_name = {row["opening"]: row for row in rows}

    assert "Sicilian Defense" in by_name
    assert "French Defense" in by_name
    assert by_name["Sicilian Defense"]["games"] == 1
    assert by_name["Sicilian Defense"]["win_pct"] == 100.0
    assert by_name["French Defense"]["win_pct"] == 100.0


def test_live_opening_detection_gets_more_specific() -> None:
    assert detect_opening_from_san(["e4"]) == "King's Pawn Opening"
    assert detect_opening_from_san(["e4", "c5"]) == "Sicilian Defense"
    assert detect_opening_from_san(["e4", "c5", "Nf3", "Nc6"]) == "Sicilian Defense — Old Sicilian Variation"
    assert detect_opening_from_san(["h4"]) is None
