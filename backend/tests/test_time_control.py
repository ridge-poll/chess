from app.pgn.time_control import classify_time_control


def test_classify_time_control() -> None:
    assert classify_time_control("60") == "Bullet"
    assert classify_time_control("180") == "Blitz"
    assert classify_time_control("300+5") == "Blitz"
    assert classify_time_control("600") == "Rapid"
    assert classify_time_control("3600") == "Classical"
    assert classify_time_control("1/86400") == "Daily / Correspondence"
    assert classify_time_control("-") is None
