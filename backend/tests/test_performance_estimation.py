from app.analysis.performance import ESTIMATOR_VERSION, estimate_game_performance


def _positions(white_losses: list[int], black_losses: list[int]) -> list[dict[str, object]]:
    positions: list[dict[str, object]] = []
    for index in range(max(len(white_losses), len(black_losses))):
        if index < len(white_losses):
            positions.append({"ply": index * 2 + 1, "color": "white", "centipawn_loss": white_losses[index]})
        if index < len(black_losses):
            positions.append({"ply": index * 2 + 2, "color": "black", "centipawn_loss": black_losses[index]})
    return positions


def test_estimates_each_player_from_their_own_decisions() -> None:
    result = estimate_game_performance(
        _positions([8] * 12, [80, 20, 250, 70, 10, 330, 45, 95, 160, 40, 70, 25]),
        {"white_elo": 1800, "black_elo": 1800, "time_class": "Rapid"},
    )

    assert result["version"] == ESTIMATOR_VERSION
    assert result["white"]["estimated_rating"] > result["black"]["estimated_rating"]
    assert result["white"]["inputs"]["decision_count"] == 12


def test_short_game_declines_to_make_a_precise_estimate() -> None:
    result = estimate_game_performance(
        _positions([0, 5, 0], [0, 10, 0]),
        {"white_elo": 2100, "black_elo": 1900, "time_class": "Blitz"},
    )

    assert result["white"]["estimated_rating"] is None
    assert result["black"]["estimated_rating"] is None
    assert result["white"]["sample_quality"] == "insufficient"
