from __future__ import annotations

from typing import Any

import chess

from app.analysis.stockfish import StockfishClient
from app.config import settings
from app.services.position_analysis import get_game_positions

STARTING_FEN = chess.STARTING_FEN


def build_position(
    moves: list[str] | None = None,
    starting_fen: str | None = None,
    selected_ply: int | None = None,
    include_engine: bool = False,
    depth: int | None = None,
) -> dict[str, object]:
    start_board = _board_from_fen(starting_fen)
    start_fen = start_board.fen()
    replay_board = chess.Board(start_fen)
    normalized_moves: list[str] = []
    positions: list[dict[str, object]] = [_position_snapshot(replay_board, 0, None, None)]
    history: list[dict[str, object]] = []

    requested_moves = moves or []
    for ply, move_text in enumerate(requested_moves, start=1):
        move = _parse_legal_move(replay_board, move_text)
        san = replay_board.san(move)
        replay_board.push(move)
        normalized_moves.append(move.uci())
        color = "white" if ply % 2 == 1 else "black"
        history.append(
            {
                "ply": ply,
                "move_number": (ply + 1) // 2,
                "color": color,
                "side": color,
                "san": san,
                "uci": move.uci(),
            }
        )
        positions.append(_position_snapshot(replay_board, ply, san, move.uci()))

    selected_index = len(normalized_moves) if selected_ply is None else max(0, min(selected_ply, len(normalized_moves)))
    selected_board = chess.Board(start_fen)
    for move_text in normalized_moves[:selected_index]:
        selected_board.push(chess.Move.from_uci(move_text))

    result: dict[str, object] = {
        "starting_fen": start_fen,
        "fen": selected_board.fen(),
        "selected_ply": selected_index,
        "moves": normalized_moves,
        "move_history": history,
        "positions": positions,
        "legal_moves": _legal_moves(selected_board),
        "turn": "white" if selected_board.turn == chess.WHITE else "black",
        "is_check": selected_board.is_check(),
        "is_checkmate": selected_board.is_checkmate(),
        "is_stalemate": selected_board.is_stalemate(),
        "result": selected_board.result(claim_draw=True) if selected_board.is_game_over(claim_draw=True) else None,
    }
    if include_engine:
        result["engine"] = _engine_snapshot(selected_board.fen(), depth or settings.default_depth)
    return result


def play_move(
    move: str,
    moves: list[str] | None = None,
    starting_fen: str | None = None,
    selected_ply: int | None = None,
    include_engine: bool = False,
    depth: int | None = None,
) -> dict[str, object]:
    board_state = build_position(moves, starting_fen, selected_ply, False)
    board = chess.Board(str(board_state["fen"]))
    legal_move = _parse_legal_move(board, move)
    selected = int(board_state["selected_ply"])
    next_moves = list(board_state["moves"])[:selected] + [legal_move.uci()]
    return build_position([str(item) for item in next_moves], str(board_state["starting_fen"]), None, include_engine, depth)


def load_game_workspace(game_id: int, profile_id: int | None = None) -> dict[str, object] | None:
    detail = get_game_positions(game_id, profile_id)
    if not detail:
        return None
    positions = detail["positions"]
    moves = [str(position["uci"]) for position in positions]
    move_history = [
        {
            "ply": position["ply"],
            "move_number": position["move_number"],
            "color": position["color"],
            "side": position["side"],
            "san": position["san"],
            "uci": position["uci"],
        }
        for position in positions
    ]
    snapshots = [
        _snapshot_from_fen(str(detail["starting_fen"]), 0, None, None),
        *[
            _snapshot_from_fen(str(position["fen"]), int(position["ply"]), str(position["san"]), str(position["uci"]))
            for position in positions
        ],
    ]
    final_board = chess.Board(str(snapshots[-1]["fen"])) if snapshots else chess.Board(STARTING_FEN)
    return {
        "game": detail["game"],
        "starting_fen": detail["starting_fen"],
        "fen": final_board.fen(),
        "selected_ply": len(moves),
        "moves": moves,
        "move_history": move_history,
        "positions": snapshots,
        "legal_moves": _legal_moves(final_board),
        "turn": "white" if final_board.turn == chess.WHITE else "black",
        "is_check": final_board.is_check(),
        "is_checkmate": final_board.is_checkmate(),
        "is_stalemate": final_board.is_stalemate(),
        "result": final_board.result(claim_draw=True) if final_board.is_game_over(claim_draw=True) else None,
    }


def _board_from_fen(fen: str | None) -> chess.Board:
    try:
        return chess.Board(fen or STARTING_FEN)
    except ValueError as exc:
        raise ValueError("Invalid FEN.") from exc


def _parse_legal_move(board: chess.Board, move_text: str) -> chess.Move:
    text = move_text.strip()
    try:
        move = chess.Move.from_uci(text)
        if move in board.legal_moves:
            return move
    except ValueError:
        pass
    try:
        move = board.parse_san(text)
    except ValueError as exc:
        raise ValueError(f"Illegal move: {move_text}") from exc
    if move not in board.legal_moves:
        raise ValueError(f"Illegal move: {move_text}")
    return move


def _legal_moves(board: chess.Board) -> list[dict[str, object]]:
    moves = []
    for move in board.legal_moves:
        moves.append(
            {
                "uci": move.uci(),
                "from": chess.square_name(move.from_square),
                "to": chess.square_name(move.to_square),
                "promotion": chess.piece_symbol(move.promotion) if move.promotion else None,
                "san": board.san(move),
            }
        )
    return moves


def _position_snapshot(board: chess.Board, ply: int, san: str | None, uci: str | None) -> dict[str, object]:
    return _snapshot_from_fen(board.fen(), ply, san, uci)


def _snapshot_from_fen(fen: str, ply: int, san: str | None, uci: str | None) -> dict[str, object]:
    board = chess.Board(fen)
    return {
        "ply": ply,
        "move_number": (ply + 1) // 2 if ply else 0,
        "color": "white" if ply % 2 == 1 else "black",
        "side": "white" if ply % 2 == 1 else "black",
        "san": san,
        "uci": uci,
        "fen": fen,
        "turn": "white" if board.turn == chess.WHITE else "black",
        "is_check": board.is_check(),
        "is_checkmate": board.is_checkmate(),
        "is_stalemate": board.is_stalemate(),
    }


def _engine_snapshot(fen: str, depth: int) -> dict[str, Any]:
    try:
        with StockfishClient() as engine:
            evaluation = engine.evaluate(fen, depth)
    except Exception as exc:
        return {"status": "unavailable", "error": str(exc)}
    return {
        "status": "ok",
        "depth": evaluation.depth,
        "best_move": evaluation.best_move,
        "score_cp": evaluation.score_cp,
        "mate": evaluation.mate,
    }
