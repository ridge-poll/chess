from __future__ import annotations

import chess


CENTRAL_FILES = {chess.FILE_NAMES.index(file_name) for file_name in ("c", "d", "e", "f")}


def openness_features(fen: str) -> dict[str, int | float]:
    board = chess.Board(fen)
    white_pawns = board.pieces(chess.PAWN, chess.WHITE)
    black_pawns = board.pieces(chess.PAWN, chess.BLACK)
    all_pawns = white_pawns | black_pawns
    open_files = 0
    semi_open_files = 0
    for file_index in range(8):
        has_white = any(chess.square_file(square) == file_index for square in white_pawns)
        has_black = any(chess.square_file(square) == file_index for square in black_pawns)
        if not has_white and not has_black:
            open_files += 1
        elif has_white != has_black:
            semi_open_files += 1

    central_pawns = sum(chess.square_file(square) in CENTRAL_FILES for square in all_pawns)
    locked_contacts = sum(
        chess.square(chess.square_file(square), chess.square_rank(square) + 1) in black_pawns
        for square in white_pawns
        if chess.square_rank(square) < 7
    )
    white_chain_links = _pawn_chain_links(board, chess.WHITE)
    black_chain_links = _pawn_chain_links(board, chess.BLACK)
    pawn_breaks = sum(
        board.is_capture(move) and board.piece_type_at(move.from_square) == chess.PAWN
        for move in board.legal_moves
    )

    pawn_removal = (16 - len(all_pawns)) / 16
    file_opening = open_files / 8
    semi_opening = semi_open_files / 8
    central_clearance = (8 - min(8, central_pawns)) / 8
    lock_penalty = min(1.0, locked_contacts / 4)
    score = 100 * (
        0.35 * pawn_removal
        + 0.30 * file_opening
        + 0.15 * semi_opening
        + 0.20 * central_clearance
        - 0.15 * lock_penalty
    )
    return {
        "score": round(max(0.0, min(100.0, score)), 1),
        "total_pawns": len(all_pawns),
        "open_files": open_files,
        "semi_open_files": semi_open_files,
        "central_pawns": central_pawns,
        "locked_pawn_contacts": locked_contacts,
        "white_pawn_chain_links": white_chain_links,
        "black_pawn_chain_links": black_chain_links,
        "available_pawn_breaks": pawn_breaks,
    }


def _pawn_chain_links(board: chess.Board, color: chess.Color) -> int:
    pawns = board.pieces(chess.PAWN, color)
    return sum(
        bool(board.attackers(color, square) & pawns)
        for square in pawns
    )
