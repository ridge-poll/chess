from app.analysis.metrics import (
    MAX_STATISTICAL_CPL,
    accuracy_from_acpl,
    centipawn_loss,
    classify_loss,
    move_loss,
)


def test_centipawn_loss_is_from_side_to_move_perspective() -> None:
    assert centipawn_loss(80, 20, "white") == 60
    assert centipawn_loss(20, 80, "black") == 60
    assert centipawn_loss(20, 80, "white") == 0


def test_classification_thresholds() -> None:
    assert classify_loss(10) == "good"
    assert classify_loss(80) == "inaccuracy"
    assert classify_loss(150) == "mistake"
    assert classify_loss(300) == "blunder"


def test_accuracy_from_acpl() -> None:
    assert accuracy_from_acpl(0) == 100.0
    assert accuracy_from_acpl(90) == 70.0


def test_mating_move_has_no_centipawn_loss() -> None:
    assert move_loss(500, None, None, 0, "white", is_checkmate_after=True) == 0


def test_mate_score_swings_are_capped_for_statistics() -> None:
    loss = move_loss(None, None, 1, -1, "white")

    assert loss == MAX_STATISTICAL_CPL
