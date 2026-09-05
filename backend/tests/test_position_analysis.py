from pathlib import Path

import chess

import app.config as config
import app.db as db
from app.services.imports import import_pgn_text
from app.services.position_analysis import get_game_positions
from app.services.profiles import create_profile


SAMPLE_PGN = """
[Event "Live Chess"]
[Site "Chess.com"]
[Date "2024.01.02"]
[White "alice"]
[Black "bob"]
[Result "1-0"]
[TimeControl "600"]

1. e4 {[%clk 0:09:58]} e5 {[%clk 0:09:57]} 2. Nf3 {[%clk 0:09:54]} Nc6 1-0
"""


def _setup_db(tmp_path: Path, monkeypatch) -> Path:
    database_path = tmp_path / "test.sqlite3"
    monkeypatch.setattr(db, "settings", config.Settings(database_path=database_path))
    db.init_db(database_path)
    return database_path


def _insert_analysis(database_path: Path, game_id: int) -> None:
    rows = [
        (1, "e2e4", "e2e4", 20, 30, None, None, 0, "good"),
        (2, "e7e5", "c7c5", 30, 80, None, None, 50, "imprecision"),
        (3, "g1f3", "g1f3", 80, 75, None, None, 5, "good"),
        (4, "b8c6", "g8f6", 75, 420, None, None, 345, "blunder"),
    ]
    with db.get_connection(database_path) as conn:
        for row in rows:
            conn.execute(
                """
                INSERT INTO move_analyses (
                    game_id, ply, depth, played_uci, best_uci,
                    eval_before_cp, eval_after_cp, mate_before, mate_after,
                    centipawn_loss, classification
                )
                VALUES (?, ?, 10, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (game_id, *row),
            )


def test_positions_preserve_move_and_evaluation_order(tmp_path: Path, monkeypatch) -> None:
    database_path = _setup_db(tmp_path, monkeypatch)
    game_id = import_pgn_text(SAMPLE_PGN)["imported_game_ids"][0]
    _insert_analysis(database_path, game_id)

    result = get_game_positions(game_id)

    assert result is not None
    assert [position["ply"] for position in result["positions"]] == [1, 2, 3, 4]
    assert [point["eval_cp"] for point in result["evaluation_history"]] == [30, 80, 75, 420]
    assert result["evaluation_history"][3]["san"] == "Nc6"
    assert result["evaluation_summary"]["last_eval_cp"] == 420
    assert result["evaluation_summary"]["largest_swings"][0]["delta_cp"] == 345
    assert result["evaluation_summary"]["largest_swings"][0]["ply"] == 4
    assert result["quality_counts"]["white"]["good"] == 2
    assert result["quality_counts"]["black"]["imprecision"] == 1
    assert result["quality_counts"]["black"]["blunder"] == 1


def test_positions_handle_missing_analysis_and_clock_data(tmp_path: Path, monkeypatch) -> None:
    _setup_db(tmp_path, monkeypatch)
    game_id = import_pgn_text(SAMPLE_PGN)["imported_game_ids"][0]

    result = get_game_positions(game_id)

    assert result is not None
    assert result["depth"] is None
    assert result["positions"][0]["clock_seconds"] == 598
    assert result["positions"][3]["clock_seconds"] is None
    assert result["positions"][0]["eval_after_cp"] is None
    assert result["positions"][0]["classification"] == "unknown"
    assert result["quality_counts"]["white"]["unknown"] == 2
    assert result["quality_counts"]["black"]["unknown"] == 2


def test_positions_reconstruct_fen_after_each_ply(tmp_path: Path, monkeypatch) -> None:
    _setup_db(tmp_path, monkeypatch)
    game_id = import_pgn_text(SAMPLE_PGN)["imported_game_ids"][0]
    result = get_game_positions(game_id)

    board = chess.Board()
    expected_fens = []
    for move_uci in ["e2e4", "e7e5", "g1f3", "b8c6"]:
        board.push(chess.Move.from_uci(move_uci))
        expected_fens.append(board.fen())

    assert result is not None
    assert [position["fen"] for position in result["positions"]] == expected_fens


def test_position_analysis_is_profile_scoped(tmp_path: Path, monkeypatch) -> None:
    database_path = _setup_db(tmp_path, monkeypatch)
    profile_a_game = import_pgn_text(SAMPLE_PGN)["imported_game_ids"][0]
    profile_b = create_profile("Second profile")
    profile_b_game = import_pgn_text(SAMPLE_PGN, int(profile_b["id"]))["imported_game_ids"][0]
    _insert_analysis(database_path, profile_a_game)

    assert get_game_positions(profile_a_game, int(profile_b["id"])) is None
    profile_b_result = get_game_positions(profile_b_game, int(profile_b["id"]))

    assert profile_b_result is not None
    assert profile_b_result["quality_counts"]["white"]["unknown"] == 2
