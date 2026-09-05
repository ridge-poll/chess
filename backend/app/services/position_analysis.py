from __future__ import annotations

import chess

from app.analysis.metrics import score_to_cp
from app.db import get_connection
from app.services.profiles import resolve_profile_id


QUALITY_BUCKETS = ["good", "imprecision", "inaccuracy", "mistake", "blunder", "unknown"]


def get_game_positions(
    game_id: int,
    profile_id: int | None = None,
    depth: int | None = None,
) -> dict[str, object] | None:
    selected_profile_id = resolve_profile_id(profile_id)
    with get_connection() as conn:
        game = conn.execute(
            "SELECT * FROM games WHERE id = ? AND profile_id = ?",
            (game_id, selected_profile_id),
        ).fetchone()
        if not game:
            return None

        selected_depth = depth
        if selected_depth is None:
            row = conn.execute(
                "SELECT MAX(depth) AS depth FROM move_analyses WHERE game_id = ?",
                (game_id,),
            ).fetchone()
            selected_depth = int(row["depth"]) if row and row["depth"] is not None else None

        params: tuple[object, ...]
        if selected_depth is None:
            analysis_join = """
                LEFT JOIN move_analyses ma
                    ON 1 = 0
            """
            params = (game_id,)
        else:
            analysis_join = """
                LEFT JOIN move_analyses ma
                    ON ma.game_id = m.game_id
                    AND ma.ply = m.ply
                    AND ma.depth = ?
            """
            params = (selected_depth, game_id)

        rows = conn.execute(
            f"""
            SELECT
                m.ply,
                m.move_number,
                m.color,
                m.san,
                m.uci,
                m.fen_before,
                m.fen_after,
                m.phase,
                m.clock_seconds,
                ma.depth,
                ma.played_uci,
                ma.best_uci,
                ma.eval_before_cp,
                ma.eval_after_cp,
                ma.mate_before,
                ma.mate_after,
                ma.centipawn_loss,
                ma.classification
            FROM moves m
            {analysis_join}
            WHERE m.game_id = ?
            ORDER BY m.ply
            """,
            params,
        ).fetchall()

    positions = [_serialize_position(row) for row in rows]
    return {
        "profile_id": selected_profile_id,
        "game": game,
        "depth": selected_depth,
        "starting_fen": rows[0]["fen_before"] if rows else chess.STARTING_FEN,
        "positions": positions,
        "evaluation_history": _evaluation_history(positions),
        "evaluation_summary": _evaluation_summary(positions),
        "quality_counts": _quality_counts(positions),
    }


def _serialize_position(row: dict[str, object]) -> dict[str, object]:
    eval_after_cp = score_to_cp(row["eval_after_cp"], row["mate_after"])
    eval_before_cp = score_to_cp(row["eval_before_cp"], row["mate_before"])
    return {
        "ply": row["ply"],
        "move_number": row["move_number"],
        "color": row["color"],
        "side": row["color"],
        "san": row["san"],
        "uci": row["uci"],
        "played_uci": row["played_uci"] or row["uci"],
        "fen_before": row["fen_before"],
        "fen_after": row["fen_after"],
        "fen": row["fen_after"],
        "phase": row["phase"],
        "clock_seconds": row["clock_seconds"],
        "depth": row["depth"],
        "best_uci": row["best_uci"],
        "eval_before_cp": row["eval_before_cp"],
        "eval_after_cp": row["eval_after_cp"],
        "eval_before_display_cp": eval_before_cp,
        "eval_after_display_cp": eval_after_cp,
        "mate_before": row["mate_before"],
        "mate_after": row["mate_after"],
        "centipawn_loss": row["centipawn_loss"],
        "classification": row["classification"] or "unknown",
    }


def _evaluation_history(positions: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        {
            "ply": position["ply"],
            "move_number": position["move_number"],
            "side": position["side"],
            "san": position["san"],
            "classification": position["classification"],
            "centipawn_loss": position["centipawn_loss"],
            "eval_cp": position["eval_after_display_cp"],
            "mate": position["mate_after"],
        }
        for position in positions
    ]


def _evaluation_summary(positions: list[dict[str, object]]) -> dict[str, object]:
    points = [
        position
        for position in positions
        if position["eval_after_display_cp"] is not None
    ]
    if not points:
        return {
            "first_eval_cp": None,
            "last_eval_cp": None,
            "max_eval_cp": None,
            "min_eval_cp": None,
            "largest_swings": [],
        }

    swings = []
    previous = None
    for position in points:
        current = int(position["eval_after_display_cp"])
        if previous is not None:
            delta = current - int(previous["eval_after_display_cp"])
            swings.append(
                {
                    "ply": position["ply"],
                    "move_number": position["move_number"],
                    "side": position["side"],
                    "san": position["san"],
                    "delta_cp": delta,
                    "abs_delta_cp": abs(delta),
                    "eval_cp": current,
                    "classification": position["classification"],
                }
            )
        previous = position

    return {
        "first_eval_cp": points[0]["eval_after_display_cp"],
        "last_eval_cp": points[-1]["eval_after_display_cp"],
        "max_eval_cp": max(int(position["eval_after_display_cp"]) for position in points),
        "min_eval_cp": min(int(position["eval_after_display_cp"]) for position in points),
        "largest_swings": sorted(
            swings,
            key=lambda swing: int(swing["abs_delta_cp"]),
            reverse=True,
        )[:3],
    }


def _quality_counts(positions: list[dict[str, object]]) -> dict[str, dict[str, int]]:
    counts = {
        "white": {bucket: 0 for bucket in QUALITY_BUCKETS},
        "black": {bucket: 0 for bucket in QUALITY_BUCKETS},
    }
    for position in positions:
        side = str(position["side"])
        if side not in counts:
            continue
        classification = str(position["classification"] or "unknown")
        if classification not in counts[side]:
            classification = "unknown"
        counts[side][classification] += 1
    return counts
