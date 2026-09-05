from pathlib import Path

import app.config as config
import app.db as db
import app.services.imports as imports


SAMPLE_PGN = """
[Event "Live Chess"]
[Site "Chess.com"]
[Date "2024.01.02"]
[White "alice"]
[Black "bob"]
[Result "1-0"]

1. e4 e5 2. Nf3 Nc6 1-0
"""


def test_import_detects_duplicates(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "test.sqlite3"
    monkeypatch.setattr(db, "settings", config.Settings(database_path=database_path))
    db.init_db(database_path)

    first = imports.import_pgn_text(SAMPLE_PGN)
    second = imports.import_pgn_text(SAMPLE_PGN)

    assert first["imported"] == 1
    assert first["duplicates"] == 0
    assert second["imported"] == 0
    assert second["duplicates"] == 1
