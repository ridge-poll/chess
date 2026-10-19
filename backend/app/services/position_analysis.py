from __future__ import annotations

import chess

from app.analysis.critical_moments import critical_moments
from app.analysis.metrics import MOVE_CLASSIFICATIONS, accuracy_from_acpl, score_to_cp
from app.analysis.position_features import openness_features
from app.db import get_connection
from app.services.profiles import resolve_profile_id


QUALITY_BUCKETS = list(MOVE_CLASSIFICATIONS)


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
        game = dict(game)
        if not game.get("player_color"):
            profile = conn.execute(
                "SELECT chesscom_username FROM profiles WHERE id = ?",
                (selected_profile_id,),
            ).fetchone()
            username = profile["chesscom_username"] if profile else None
            if username and game.get("white") and str(game["white"]).lower() == str(username).lower():
                game["player_color"] = "white"
            elif username and game.get("black") and str(game["black"]).lower() == str(username).lower():
                game["player_color"] = "black"

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
        candidate_rows = []
        if selected_depth is not None:
            candidate_rows = conn.execute(
                """
                SELECT DISTINCT pe.fen, pec.rank, pec.score_cp, pec.mate
                FROM position_evaluations pe
                JOIN position_evaluation_candidates pec ON pec.evaluation_id = pe.id
                JOIN moves m ON m.fen_before = pe.fen
                WHERE m.game_id = ? AND pe.depth = ?
                ORDER BY pe.fen, pec.rank
                """,
                (game_id, selected_depth),
            ).fetchall()

    positions = [_serialize_position(row) for row in rows]
    time_usage = _time_usage(positions, game["time_control"])
    volatility = _volatility(positions)
    openness = _openness_trajectory(positions)
    candidates_by_fen: dict[str, list[dict[str, object]]] = {}
    for candidate in candidate_rows:
        candidates_by_fen.setdefault(str(candidate["fen"]), []).append(candidate)
    return {
        "profile_id": selected_profile_id,
        "game": game,
        "depth": selected_depth,
        "starting_fen": rows[0]["fen_before"] if rows else chess.STARTING_FEN,
        "positions": positions,
        "evaluation_history": _evaluation_history(positions),
        "evaluation_summary": _evaluation_summary(positions),
        "quality_counts": _quality_counts(positions),
        "time_usage": time_usage,
        "volatility": volatility,
        "openness": openness,
        "phase_performance": _phase_performance(positions),
        "critical_moments": critical_moments(positions, game["player_color"], candidates_by_fen),
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
        "classification": row["classification"],
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
        classification = position["classification"]
        if classification not in counts[side]:
            continue
        counts[side][classification] += 1
    return counts


def _time_usage(
    positions: list[dict[str, object]],
    time_control: object,
) -> list[dict[str, object]]:
    base_seconds, increment_seconds = _parse_time_control(time_control)
    previous_clock: dict[str, tuple[int, float]] = {}
    usage: list[dict[str, object]] = []
    for position in positions:
        side = str(position["side"])
        ply = int(position["ply"])
        clock_value = position["clock_seconds"]
        spent: float | None = None
        if clock_value is not None:
            clock = float(clock_value)
            previous = previous_clock.get(side)
            if previous and previous[0] == ply - 2:
                spent = max(0.0, previous[1] + increment_seconds - clock)
            elif ply <= 2 and base_seconds is not None:
                spent = max(0.0, base_seconds + increment_seconds - clock)
            previous_clock[side] = (ply, clock)
        position["time_spent_seconds"] = spent
        usage.append(
            {
                "ply": ply,
                "move_number": position["move_number"],
                "side": side,
                "san": position["san"],
                "clock_seconds": clock_value,
                "time_spent_seconds": spent,
            }
        )
    return usage


def _parse_time_control(time_control: object) -> tuple[float | None, float]:
    value = str(time_control or "").strip()
    if not value or "/" in value:
        return None, 0.0
    first_period = value.split(":", 1)[0]
    base_text, separator, increment_text = first_period.partition("+")
    try:
        base = float(base_text)
        increment = float(increment_text) if separator else 0.0
    except ValueError:
        return None, 0.0
    return base, increment


def _volatility(positions: list[dict[str, object]]) -> dict[str, object]:
    points: list[dict[str, object]] = []
    previous: int | None = None
    contributions: list[int] = []
    for position in positions:
        current_value = position["eval_after_display_cp"]
        contribution: int | None = None
        if current_value is not None:
            current = max(-1000, min(1000, int(current_value)))
            if previous is None and position["eval_before_display_cp"] is not None:
                previous = max(-1000, min(1000, int(position["eval_before_display_cp"])))
            if previous is not None:
                contribution = abs(current - previous)
                contributions.append(contribution)
            previous = current
        position["volatility_cp"] = contribution
        points.append(
            {
                "ply": position["ply"],
                "move_number": position["move_number"],
                "side": position["side"],
                "san": position["san"],
                "volatility_cp": contribution,
            }
        )
    return {
        "average_cp": round(sum(contributions) / len(contributions), 1) if contributions else None,
        "points": points,
    }


def _openness_trajectory(positions: list[dict[str, object]]) -> list[dict[str, object]]:
    trajectory: list[dict[str, object]] = []
    for position in positions:
        features = openness_features(str(position["fen"]))
        position["openness"] = features
        trajectory.append(
            {
                "ply": position["ply"],
                "move_number": position["move_number"],
                "side": position["side"],
                "san": position["san"],
                **features,
            }
        )
    return trajectory


def _phase_performance(positions: list[dict[str, object]]) -> dict[str, list[dict[str, object]]]:
    result: dict[str, list[dict[str, object]]] = {"white": [], "black": []}
    for side in result:
        for phase in ("opening", "middlegame", "endgame"):
            phase_positions = [
                position
                for position in positions
                if position["side"] == side and position["phase"] == phase
            ]
            losses = [
                int(position["centipawn_loss"])
                for position in phase_positions
                if position["centipawn_loss"] is not None
            ]
            acpl = round(sum(losses) / len(losses), 1) if losses else None
            result[side].append(
                {
                    "phase": phase,
                    "moves": len(phase_positions),
                    "analyzed_moves": len(losses),
                    "acpl": acpl,
                    "accuracy": accuracy_from_acpl(acpl),
                    "mistakes": sum(
                        position["classification"] in {"inaccuracy", "mistake", "blunder"}
                        for position in phase_positions
                    ),
                }
            )
    return result
