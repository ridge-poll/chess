from pathlib import Path

import app.config as config
import app.db as db
from app.services.analysis_jobs import get_analysis_jobs, prepare_queued_job
from app.services.imports import import_pgn_text


SAMPLE_PGN = """
[Event "Live Chess"]
[Site "Chess.com"]
[Date "2024.01.02"]
[White "alice"]
[Black "bob"]
[Result "1-0"]

1. e4 e5 2. Nf3 Nc6 1-0
"""


def test_prepare_queued_job_records_resumable_progress(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "test.sqlite3"
    monkeypatch.setattr(db, "settings", config.Settings(database_path=database_path))
    db.init_db(database_path)
    result = import_pgn_text(SAMPLE_PGN)
    game_id = result["imported_game_ids"][0]

    job = prepare_queued_job(game_id, depth=8)
    jobs = get_analysis_jobs()

    assert job["status"] == "queued"
    assert job["total_plies"] == 4
    assert jobs[0]["status"] == "queued"
    assert jobs[0]["progress"] == 0.0


def test_prepare_queued_job_skips_completed_games(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "test.sqlite3"
    monkeypatch.setattr(db, "settings", config.Settings(database_path=database_path))
    db.init_db(database_path)
    result = import_pgn_text(SAMPLE_PGN)
    game_id = result["imported_game_ids"][0]

    with db.get_connection(database_path) as conn:
        moves = conn.execute("SELECT * FROM moves WHERE game_id = ?", (game_id,)).fetchall()
        for move in moves:
            conn.execute(
                """
                INSERT INTO move_analyses (
                    game_id, ply, depth, played_uci, classification, centipawn_loss
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (game_id, move["ply"], 8, move["uci"], "good", 0),
            )

    job = prepare_queued_job(game_id, depth=8)

    assert job["status"] == "complete"
    assert job["analyzed_plies"] == 4
