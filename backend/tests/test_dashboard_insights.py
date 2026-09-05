from pathlib import Path

import app.config as config
import app.db as db
from app.services.games import dashboard
from app.services.imports import import_pgn_text


PGN = """
[Event "Live Chess"]
[Site "Chess.com"]
[Date "2026.05.30"]
[White "ridgepoll1"]
[Black "opponent1"]
[Result "1-0"]
[WhiteElo "1500"]
[BlackElo "1490"]
[ECO "D30"]
[TimeControl "180"]

1. d4 d5 2. c4 e6 1-0

[Event "Live Chess"]
[Site "Chess.com"]
[Date "2026.05.31"]
[White "opponent2"]
[Black "ridgepoll1"]
[Result "0-1"]
[WhiteElo "1505"]
[BlackElo "1510"]
[ECO "D30"]
[TimeControl "600"]

1. e4 e5 2. Nf3 Nc6 0-1
"""


def test_dashboard_includes_stage_three_insights(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "test.sqlite3"
    monkeypatch.setattr(db, "settings", config.Settings(database_path=database_path))
    db.init_db(database_path)
    result = import_pgn_text(PGN)

    with db.get_connection(database_path) as conn:
        for game_id in result["imported_game_ids"]:
            moves = conn.execute("SELECT * FROM moves WHERE game_id = ?", (game_id,)).fetchall()
            for move in moves:
                conn.execute(
                    """
                    INSERT INTO move_analyses (
                        game_id, ply, depth, played_uci, centipawn_loss, classification,
                        eval_before_cp, eval_after_cp
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        game_id,
                        move["ply"],
                        10,
                        move["uci"],
                        25,
                        "good",
                        100,
                        75,
                    ),
                )
            conn.execute(
                """
                INSERT INTO analysis_jobs (game_id, depth, status, analyzed_plies, total_plies)
                VALUES (?, ?, ?, ?, ?)
                """,
                (game_id, 10, "complete", len(moves), len(moves)),
            )

    data = dashboard()

    assert data["player"] == "ridgepoll1"
    assert data["totals"]["wins"] == 2
    assert [row["rating"] for row in data["rating_trend"]] == [1500, 1510]
    assert "opening_summary" in data
    assert "mistake_breakdown" in data
    assert isinstance(data["insights"], list)


def test_dashboard_splits_statistics_by_time_control(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "test.sqlite3"
    monkeypatch.setattr(db, "settings", config.Settings(database_path=database_path))
    db.init_db(database_path)
    import_pgn_text(PGN)

    data = dashboard()
    stats = {row["time_class"]: row for row in data["time_control_stats"]}

    assert stats["Overall"]["games"] == 2
    assert stats["Blitz"]["games"] == 1
    assert stats["Rapid"]["games"] == 1
    assert stats["Blitz"]["average_game_length"] == 2.0
    assert stats["Rapid"]["average_game_length"] == 2.0
