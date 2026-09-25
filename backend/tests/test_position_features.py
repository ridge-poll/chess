import chess

from app.analysis.position_features import openness_features


def test_starting_position_is_structurally_closed() -> None:
    features = openness_features(chess.STARTING_FEN)

    assert features["score"] == 0.0
    assert features["total_pawns"] == 16
    assert features["open_files"] == 0
    assert features["central_pawns"] == 8


def test_openness_retains_raw_pawn_structure_features() -> None:
    features = openness_features("8/8/3p4/3P4/8/8/8/4K2k w - - 0 1")

    assert features["total_pawns"] == 2
    assert features["open_files"] == 7
    assert features["locked_pawn_contacts"] == 1
    assert "available_pawn_breaks" in features
