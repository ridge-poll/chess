from __future__ import annotations

from math import sqrt
from statistics import mean, median


ESTIMATOR_VERSION = "heuristic-v1"
MIN_DECISIONS = 8


def estimate_game_performance(
    positions: list[dict[str, object]],
    game: dict[str, object],
) -> dict[str, object]:
    """Estimate each side's demonstrated level from a modest, transparent heuristic.

    This is deliberately not an accuracy-to-Elo lookup. It combines the loss
    distribution, error frequency, game context, and a rating prior. The result
    is rounded heavily and omitted when the game offers too little evidence.
    """
    return {
        "version": ESTIMATOR_VERSION,
        "white": _estimate_side(positions, game, "white"),
        "black": _estimate_side(positions, game, "black"),
    }


def _estimate_side(
    positions: list[dict[str, object]],
    game: dict[str, object],
    color: str,
) -> dict[str, object]:
    moves = [
        position
        for position in positions
        if position.get("color") == color and position.get("centipawn_loss") is not None
    ]
    losses = [min(1_000, max(0, int(position["centipawn_loss"]))) for position in moves]
    count = len(losses)
    confidence = min(1.0, max(0.0, (count - 4) / 20))
    sample_quality = "insufficient" if count < MIN_DECISIONS else "low" if confidence < 0.55 else "moderate"
    inputs: dict[str, object] = {"decision_count": count, "time_class": game.get("time_class")}
    if count < MIN_DECISIONS:
        return {
            "estimated_rating": None,
            "confidence": round(confidence, 2),
            "sample_quality": sample_quality,
            "inputs": inputs,
        }

    average_loss = mean(losses)
    median_loss = median(losses)
    severe_rate = sum(loss >= 150 for loss in losses) / count
    blunder_rate = sum(loss >= 300 for loss in losses) / count
    clean_rate = sum(loss <= 30 for loss in losses) / count

    # The loss curve supplies the behavioral signal; error shape prevents one
    # average from treating a steady game and a one-blunder game as identical.
    behavior_level = (
        2_350
        - 72 * sqrt(average_loss)
        - 1.8 * median_loss
        - 360 * severe_rate
        - 300 * blunder_rate
        + 140 * clean_rate
    )
    own_rating = _numeric(game.get(f"{color}_elo"))
    opponent_color = "black" if color == "white" else "white"
    opponent_rating = _numeric(game.get(f"{opponent_color}_elo"))
    known_ratings = [rating for rating in (own_rating, opponent_rating) if rating is not None]
    context_level = mean(known_ratings) if known_ratings else behavior_level
    time_adjustment = {
        "Bullet": -120,
        "Blitz": -55,
        "Rapid": 0,
        "Classical": 35,
        "Daily / Correspondence": 45,
    }.get(str(game.get("time_class") or ""), 0)
    estimate = behavior_level * 0.68 + context_level * 0.32 + time_adjustment
    estimate = max(400, min(2_800, estimate))
    rounded = int(round(estimate / 50) * 50)
    inputs.update(
        {
            "average_cpl": round(average_loss, 1),
            "median_cpl": round(float(median_loss), 1),
            "severe_error_rate": round(severe_rate, 3),
            "blunder_rate": round(blunder_rate, 3),
            "clean_move_rate": round(clean_rate, 3),
            "player_rating": own_rating,
            "opponent_rating": opponent_rating,
        }
    )
    return {
        "estimated_rating": rounded,
        "confidence": round(confidence, 2),
        "sample_quality": sample_quality,
        "inputs": inputs,
    }


def _numeric(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
