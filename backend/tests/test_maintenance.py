from pathlib import Path

import app.config as config
import app.db as db
from app.services.imports import import_pgn_text
from app.services.maintenance import repair_analysis_metrics


MATE_PGN = """
[Event "Mate"]
[Site "Chess.com"]
[Date "2024.01.03"]
[White "alice"]
[Black "bob"]
[Result "0-1"]

1. f3 e5 2. g4 Qh4# 0-1
"""


def test_repair_analysis_metrics_normalizes_existing_giant_losses(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "test.sqlite3"
    monkeypatch.setattr(db, "settings", config.Settings(database_path=database_path))
    db.init_db(database_path)
    result = import_pgn_text(MATE_PGN)
    game_id = result["imported_game_ids"][0]

    with db.get_connection(database_path) as conn:
        move = conn.execute(
            "SELECT * FROM moves WHERE game_id = ? ORDER BY ply DESC LIMIT 1",
            (game_id,),
        ).fetchone()
        conn.execute(
            """
            INSERT INTO move_analyses (
                game_id, ply, depth, played_uci, mate_before, mate_after,
                centipawn_loss, classification
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (game_id, move["ply"], 10, move["uci"], 1, 0, 199900, "blunder"),
        )

    repaired = repair_analysis_metrics()

    with db.get_connection(database_path) as conn:
        row = conn.execute("SELECT * FROM move_analyses").fetchone()

    assert repaired == 1
    assert row["centipawn_loss"] == 0
    assert row["classification"] == "good"
