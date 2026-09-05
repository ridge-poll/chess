from __future__ import annotations


MAX_STATISTICAL_CPL = 1_000
MATE_SCORE = 10_000


def score_to_cp(score_cp: int | None, mate: int | None) -> int | None:
    if score_cp is not None:
        return score_cp
    if mate is None:
        return None
    sign = 1 if mate > 0 else -1
    return sign * (MATE_SCORE - min(abs(mate), 100) * 100)


def centipawn_loss(
    eval_before_cp: int | None,
    eval_after_cp: int | None,
    color: str,
) -> int | None:
    if eval_before_cp is None or eval_after_cp is None:
        return None
    if color == "white":
        loss = eval_before_cp - eval_after_cp
    else:
        loss = eval_after_cp - eval_before_cp
    return clamp_statistical_loss(loss)


def clamp_statistical_loss(loss: int | float | None) -> int | None:
    if loss is None:
        return None
    return max(0, min(MAX_STATISTICAL_CPL, int(loss)))


def move_loss(
    eval_before_cp: int | None,
    eval_after_cp: int | None,
    mate_before: int | None,
    mate_after: int | None,
    color: str,
    is_checkmate_after: bool = False,
) -> int | None:
    if is_checkmate_after:
        return 0
    before = score_to_cp(eval_before_cp, mate_before)
    after = score_to_cp(eval_after_cp, mate_after)
    return centipawn_loss(before, after, color)


def classify_loss(loss: int | None) -> str:
    if loss is None:
        return "unknown"
    if loss >= 300:
        return "blunder"
    if loss >= 150:
        return "mistake"
    if loss >= 75:
        return "inaccuracy"
    if loss >= 30:
        return "imprecision"
    return "good"


def accuracy_from_acpl(acpl: float | None) -> float | None:
    if acpl is None:
        return None
    return round(max(0.0, min(100.0, 100.0 - acpl / 3.0)), 1)
