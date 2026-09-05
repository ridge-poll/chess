from app.pgn.parser import parse_pgn_text


SAMPLE_PGN = """
[Event "Live Chess"]
[Site "Chess.com"]
[Date "2024.01.02"]
[Round "-"]
[White "alice"]
[Black "bob"]
[Result "1-0"]
[ECO "C20"]
[Opening "King's Pawn Game"]
[TimeControl "600"]
[WhiteElo "1200"]
[BlackElo "1180"]

1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 1-0
"""


def test_parse_chess_com_metadata_and_moves() -> None:
    games, errors = parse_pgn_text(SAMPLE_PGN)

    assert errors == []
    assert len(games) == 1
    game = games[0]
    assert game.site == "Chess.com"
    assert game.played_at == "2024-01-02"
    assert game.result == "1-0"
    assert game.eco == "C20"
    assert game.opening == "King's Pawn Game"
    assert game.time_class == "Rapid"
    assert game.white_elo == 1200
    assert len(game.moves) == 6
    assert game.moves[0].san == "e4"
    assert game.moves[0].uci == "e2e4"


def test_parse_move_clock_comments() -> None:
    pgn = """
[Event "Live Chess"]
[Site "Chess.com"]
[Date "2024.01.02"]
[White "alice"]
[Black "bob"]
[Result "1-0"]
[TimeControl "600"]

1. e4 {[%clk 0:09:58.4]} e5 {[%clk 0:09:57]} 2. Nf3 {[%clk 9:55]} Nc6 1-0
"""

    games, errors = parse_pgn_text(pgn)

    assert not errors
    assert games[0].moves[0].clock_seconds == 598.4
    assert games[0].moves[1].clock_seconds == 597
    assert games[0].moves[2].clock_seconds == 595
    assert games[0].moves[3].clock_seconds is None
