from __future__ import annotations

import logging

import chess

from app.analysis.metrics import classify_loss, move_loss
from app.db import get_connection
from app.models import ParsedMove
from app.pgn.openings import detect_opening
from app.pgn.time_control import classify_time_control

logger = logging.getLogger(__name__)


def repair_analysis_metrics() -> int:
    repaired = 0
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                ma.id,
                ma.eval_before_cp,
                ma.eval_after_cp,
                ma.mate_before,
                ma.mate_after,
                ma.centipawn_loss,
                ma.classification,
                m.color,
                m.fen_after
            FROM move_analyses ma
            JOIN moves m ON m.game_id = ma.game_id AND m.ply = ma.ply
            """
        ).fetchall()

        for row in rows:
            try:
                is_checkmate_after = chess.Board(str(row["fen_after"])).is_checkmate()
            except ValueError:
                is_checkmate_after = False

            loss = move_loss(
                row["eval_before_cp"],
                row["eval_after_cp"],
                row["mate_before"],
                row["mate_after"],
                str(row["color"]),
                is_checkmate_after,
            )
            classification = classify_loss(loss)
            if loss != row["centipawn_loss"] or classification != row["classification"]:
                conn.execute(
                    """
                    UPDATE move_analyses
                    SET centipawn_loss = ?, classification = ?
                    WHERE id = ?
                    """,
                    (loss, classification, row["id"]),
                )
                repaired += 1

    if repaired:
        logger.info("Repaired %s analysis metric rows", repaired)
    return repaired


def backfill_time_classes() -> int:
    updated = 0
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, time_control, time_class
            FROM games
            WHERE time_class IS NULL OR time_class = ''
            """
        ).fetchall()
        for row in rows:
            time_class = classify_time_control(row["time_control"])
            if time_class:
                conn.execute(
                    "UPDATE games SET time_class = ? WHERE id = ?",
                    (time_class, row["id"]),
                )
                updated += 1
    if updated:
        logger.info("Backfilled %s game time classes", updated)
    return updated


def backfill_openings() -> int:
    updated = 0
    with get_connection() as conn:
        games = conn.execute(
            """
            SELECT id, opening, eco, raw_pgn
            FROM games
            WHERE opening IS NULL OR opening = '' OR opening = 'Unknown'
            """
        ).fetchall()
        for game in games:
            moves = conn.execute(
                "SELECT * FROM moves WHERE game_id = ? ORDER BY ply",
                (game["id"],),
            ).fetchall()
            parsed_moves = [
                ParsedMove(
                    ply=int(move["ply"]),
                    move_number=int(move["move_number"]),
                    color=str(move["color"]),
                    san=str(move["san"]),
                    uci=str(move["uci"]),
                    fen_before=str(move["fen_before"]),
                    fen_after=str(move["fen_after"]),
                    phase=str(move["phase"]),
                    clock_seconds=move["clock_seconds"],
                )
                for move in moves
            ]
            eco_url = _extract_header(str(game["raw_pgn"]), "ECOUrl")
            opening = detect_opening(parsed_moves, None, eco_url) or game["eco"]
            if opening:
                conn.execute("UPDATE games SET opening = ? WHERE id = ?", (opening, game["id"]))
                updated += 1
    if updated:
        logger.info("Backfilled %s game openings", updated)
    return updated


def _extract_header(raw_pgn: str, name: str) -> str | None:
    prefix = f'[{name} "'
    for line in raw_pgn.splitlines():
        if line.startswith(prefix) and line.endswith('"]'):
            return line[len(prefix) : -2]
    return None
