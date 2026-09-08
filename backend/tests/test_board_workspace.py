from pathlib import Path

import chess
import pytest

import app.config as config
import app.db as db
from app.services.board_workspace import STARTING_FEN, build_position, load_game_workspace, play_move
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

1. e4 e5 2. Nf3 Nc6 1-0
"""


def _setup_db(tmp_path: Path, monkeypatch) -> Path:
    database_path = tmp_path / "test.sqlite3"
    monkeypatch.setattr(db, "settings", config.Settings(database_path=database_path))
    db.init_db(database_path)
    return database_path


def test_board_workspace_starts_from_standard_position() -> None:
    workspace = build_position()

    assert workspace["fen"] == STARTING_FEN
    assert workspace["selected_ply"] == 0
    assert workspace["turn"] == "white"
    assert len(workspace["legal_moves"]) == 20


def test_board_workspace_accepts_legal_moves() -> None:
    workspace = play_move("e2e4")
    board = chess.Board(str(workspace["fen"]))

    assert workspace["selected_ply"] == 1
    assert workspace["moves"] == ["e2e4"]
    assert board.piece_at(chess.E4) == chess.Piece(chess.PAWN, chess.WHITE)


def test_board_workspace_rejects_illegal_moves() -> None:
    with pytest.raises(ValueError):
        play_move("e2e5")


def test_board_workspace_handles_castling() -> None:
    workspace = build_position(["e2e4", "e7e5", "g1f3", "b8c6", "f1e2", "g8f6", "e1g1"])
    board = chess.Board(str(workspace["fen"]))

    assert board.piece_at(chess.G1) == chess.Piece(chess.KING, chess.WHITE)
    assert board.piece_at(chess.F1) == chess.Piece(chess.ROOK, chess.WHITE)


def test_board_workspace_handles_promotion() -> None:
    workspace = play_move("a7a8q", starting_fen="8/P7/8/8/8/8/8/4k2K w - - 0 1")
    board = chess.Board(str(workspace["fen"]))

    assert board.piece_at(chess.A8) == chess.Piece(chess.QUEEN, chess.WHITE)


def test_board_workspace_handles_en_passant() -> None:
    workspace = play_move("e5d6", starting_fen="8/8/8/3pP3/8/8/8/4k2K w - d6 0 1")
    board = chess.Board(str(workspace["fen"]))

    assert board.piece_at(chess.D6) == chess.Piece(chess.PAWN, chess.WHITE)
    assert board.piece_at(chess.D5) is None


def test_board_workspace_steps_without_losing_future_moves() -> None:
    workspace = build_position(["e2e4", "e7e5"], selected_ply=1)
    board = chess.Board(str(workspace["fen"]))

    assert workspace["selected_ply"] == 1
    assert workspace["moves"] == ["e2e4", "e7e5"]
    assert board.turn == chess.BLACK
    assert board.piece_at(chess.E5) is None


def test_board_workspace_branches_without_mutating_saved_game(tmp_path: Path, monkeypatch) -> None:
    _setup_db(tmp_path, monkeypatch)
    game_id = import_pgn_text(SAMPLE_PGN)["imported_game_ids"][0]
    saved_workspace = load_game_workspace(game_id)

    assert saved_workspace is not None
    branch = play_move(
        "d2d4",
        moves=[str(move) for move in saved_workspace["moves"]],
        starting_fen=str(saved_workspace["starting_fen"]),
        selected_ply=2,
    )
    persisted = get_game_positions(game_id)

    assert branch["moves"] == ["e2e4", "e7e5", "d2d4"]
    assert persisted is not None
    assert [position["uci"] for position in persisted["positions"]] == ["e2e4", "e7e5", "g1f3", "b8c6"]


def test_game_workspace_is_profile_scoped(tmp_path: Path, monkeypatch) -> None:
    _setup_db(tmp_path, monkeypatch)
    profile_b = create_profile("Second profile")
    game_id = import_pgn_text(SAMPLE_PGN)["imported_game_ids"][0]

    assert load_game_workspace(game_id, int(profile_b["id"])) is None
    assert load_game_workspace(game_id) is not None
