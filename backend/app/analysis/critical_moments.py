from __future__ import annotations

from dataclasses import dataclass

from app.analysis.metrics import score_to_cp


NEGATIVE_MIN_CPL = 75
POSITIVE_MIN_GAP_CP = 80
ONLY_MOVE_GAP_CP = 150
ADJACENT_PLY_WINDOW = 2


@dataclass(frozen=True)
class CandidateShape:
    best_eval: int | None
    second_best_eval: int | None
    spread: int | None


def critical_moments(
    positions: list[dict[str, object]],
    player_color: str | None,
    candidates_by_fen: dict[str, list[dict[str, object]]],
) -> list[dict[str, object]]:
    """Rank review-worthy player decisions without confusing volatility with quality.

    Negative moments are driven primarily by evaluation loss. Positive moments
    require a good move plus a meaningful gap to the next engine candidate, which
    is a conservative first approximation of an only-move or great-find decision.
    """
    if player_color not in {"white", "black"}:
        return []

    ranked: list[dict[str, object]] = []
    for position in positions:
        if position.get("color") != player_color:
            continue
        loss_value = position.get("centipawn_loss")
        loss = int(loss_value) if loss_value is not None else None
        shape = _candidate_shape(candidates_by_fen.get(str(position["fen_before"]), []), player_color)
        classification = str(position.get("classification") or "")
        volatility = int(position.get("volatility_cp") or 0)

        if loss is not None and loss >= NEGATIVE_MIN_CPL:
            moment_type = _negative_type(classification, loss)
            score = float(loss) + min(volatility, 500) * 0.12
            ranked.append(
                _moment(
                    position,
                    polarity="negative",
                    moment_type=moment_type,
                    score=score,
                    explanation=f"{loss / 100:.1f} evaluation loss",
                    shape=shape,
                )
            )
            continue

        candidate_gap = None
        if shape.best_eval is not None and shape.second_best_eval is not None:
            candidate_gap = max(0, shape.best_eval - shape.second_best_eval)
        played_best = bool(position.get("best_uci")) and position.get("played_uci") == position.get("best_uci")
        if played_best and loss is not None and loss <= 29 and candidate_gap is not None and candidate_gap >= POSITIVE_MIN_GAP_CP:
            moment_type = "Only Move" if candidate_gap >= ONLY_MOVE_GAP_CP else "Great Find"
            score = candidate_gap * 0.85 + min(volatility, 500) * 0.08
            explanation = (
                "Only move preserving the position"
                if moment_type == "Only Move"
                else f"Next-best choice was {candidate_gap / 100:.1f} worse"
            )
            ranked.append(
                _moment(
                    position,
                    polarity="positive",
                    moment_type=moment_type,
                    score=score,
                    explanation=explanation,
                    shape=shape,
                )
            )

    ranked.sort(key=lambda item: (-float(item["criticality_score"]), int(item["ply"])))
    selected: list[dict[str, object]] = []
    for moment in ranked:
        if any(abs(int(moment["ply"]) - int(existing["ply"])) <= ADJACENT_PLY_WINDOW for existing in selected):
            continue
        selected.append(moment)
    return sorted(selected, key=lambda item: int(item["ply"]))


def _candidate_shape(rows: list[dict[str, object]], color: str) -> CandidateShape:
    values = []
    for row in sorted(rows, key=lambda item: int(item["rank"])):
        value = score_to_cp(row.get("score_cp"), row.get("mate"))  # type: ignore[arg-type]
        if value is not None:
            values.append(value if color == "white" else -value)
    return CandidateShape(
        best_eval=values[0] if values else None,
        second_best_eval=values[1] if len(values) > 1 else None,
        spread=(max(values) - min(values)) if len(values) > 1 else None,
    )


def _negative_type(classification: str, loss: int) -> str:
    if classification == "blunder" or loss >= 300:
        return "Blunder"
    if classification == "mistake" or loss >= 150:
        return "Mistake"
    return "Missed Opportunity"


def _moment(
    position: dict[str, object],
    *,
    polarity: str,
    moment_type: str,
    score: float,
    explanation: str,
    shape: CandidateShape,
) -> dict[str, object]:
    return {
        "ply": position["ply"],
        "move_number": position["move_number"],
        "color": position["color"],
        "san": position["san"],
        "fen_before": position["fen_before"],
        "fen_after": position["fen_after"],
        "played_eval": position.get("eval_after_display_cp"),
        "best_eval": shape.best_eval,
        "second_best_eval": shape.second_best_eval,
        "eval_loss": position.get("centipawn_loss"),
        "candidate_spread": shape.spread,
        "classification": position.get("classification"),
        "criticality_score": round(score, 1),
        "criticality_type": moment_type,
        "polarity": polarity,
        "explanation": explanation,
    }
