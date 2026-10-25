from app.analysis.critical_moments import critical_moments


def _position(
    ply: int,
    *,
    color: str = "white",
    loss: int = 0,
    classification: str = "best",
    played: str = "e2e4",
    best: str = "e2e4",
) -> dict[str, object]:
    return {
        "ply": ply,
        "move_number": (ply + 1) // 2,
        "color": color,
        "san": "e4",
        "played_uci": played,
        "best_uci": best,
        "fen_before": f"before-{ply}",
        "fen_after": f"after-{ply}",
        "eval_after_display_cp": 20,
        "centipawn_loss": loss,
        "classification": classification,
        "volatility_cp": loss,
    }


def _candidates(best: int, second: int, third: int = 0) -> list[dict[str, object]]:
    return [
        {"rank": 1, "score_cp": best, "mate": None},
        {"rank": 2, "score_cp": second, "mate": None},
        {"rank": 3, "score_cp": third, "mate": None},
    ]


def test_selects_blunder_and_unique_strong_move() -> None:
    positions = [
        _position(1),
        _position(5, loss=430, classification="blunder", played="g1f3", best="d2d4"),
    ]
    candidates = {
        "before-1": _candidates(180, 10, -40),
        "before-5": _candidates(40, 0, -20),
    }

    moments = critical_moments(positions, "white", candidates)

    assert [(moment["ply"], moment["criticality_type"]) for moment in moments] == [
        (1, "Only Move"),
        (5, "Blunder"),
    ]
    assert moments[0]["polarity"] == "positive"
    assert moments[1]["polarity"] == "negative"


def test_ranking_suppresses_adjacent_redundant_events() -> None:
    positions = [
        _position(3, loss=180, classification="mistake", played="a2a3", best="e2e4"),
        _position(5, loss=420, classification="blunder", played="h2h3", best="d2d4"),
        _position(9, loss=220, classification="mistake", played="b2b3", best="g1f3"),
    ]

    moments = critical_moments(positions, "white", {})

    assert [moment["ply"] for moment in moments] == [5, 9]


def test_moments_are_limited_to_player_color_and_use_black_perspective() -> None:
    positions = [
        _position(1, color="white", loss=500, classification="blunder"),
        _position(2, color="black", played="e7e5", best="e7e5"),
    ]
    candidates = {"before-2": _candidates(-220, -20, 10)}

    moments = critical_moments(positions, "black", candidates)

    assert len(moments) == 1
    assert moments[0]["ply"] == 2
    assert moments[0]["criticality_type"] == "Only Move"


def test_all_threshold_worthy_nonadjacent_moments_are_returned() -> None:
    positions = [
        _position(ply, loss=180, classification="mistake", played=f"a2a{index}", best="e2e4")
        for index, ply in enumerate(range(1, 24, 4), start=1)
    ]

    moments = critical_moments(positions, "white", {})

    assert len(moments) == len(positions)
