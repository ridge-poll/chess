from pathlib import Path

import app.config as config
import app.db as db
from app.services.imports import import_pgn_text
from app.services.profiles import create_profile, get_active_profile
from app.services.repertoire import normalize_position_fen, repertoire_graph


COLOR_PGN = """
[Event "White win"]
[Date "2026.07.01"]
[White "hero"]
[Black "alpha"]
[User "hero"]
[Result "1-0"]

1. e4 c5 2. Nf3 d6 1-0

[Event "White loss"]
[Date "2026.07.02"]
[White "hero"]
[Black "beta"]
[User "hero"]
[Result "0-1"]

1. e4 e5 2. Nf3 Nc6 0-1

[Event "Black win"]
[Date "2026.07.03"]
[White "gamma"]
[Black "hero"]
[User "hero"]
[Result "0-1"]

1. d4 Nf6 2. c4 e6 0-1
"""

TRANSPOSITION_PGN = """
[Event "Route one"]
[Date "2026.08.01"]
[White "hero"]
[Black "route-one"]
[User "hero"]
[Result "1-0"]

1. Nf3 d5 2. d4 Nf6 1-0

[Event "Route two"]
[Date "2026.08.02"]
[White "hero"]
[Black "route-two"]
[User "hero"]
[Result "0-1"]

1. d4 Nf6 2. Nf3 d5 0-1
"""


def _prepare_database(tmp_path: Path, monkeypatch, name: str = "repertoire.sqlite3") -> None:
    database_path = tmp_path / name
    monkeypatch.setattr(db, "settings", config.Settings(database_path=database_path))
    db.init_db(database_path)


def _edges_from(graph: dict[str, object], position_id: str) -> list[dict[str, object]]:
    position = graph["positions"][position_id]
    return [graph["edges"][edge_id] for edge_id in position["outgoing_edge_ids"]]


def test_white_and_black_repertoires_are_isolated_and_conditional(tmp_path: Path, monkeypatch) -> None:
    _prepare_database(tmp_path, monkeypatch)
    import_pgn_text(COLOR_PGN)

    white = repertoire_graph("white")
    black = repertoire_graph("black")

    assert white["games"] == 2
    assert black["games"] == 1

    white_root_edges = _edges_from(white, white["root_position_id"])
    assert [(edge["san"], edge["games"], edge["frequency"]) for edge in white_root_edges] == [("e4", 2, 1.0)]
    e4 = white_root_edges[0]
    assert e4["is_user_move"] is True
    assert (e4["wins"], e4["draws"], e4["losses"]) == (1, 0, 1)

    replies = _edges_from(white, e4["child_position_id"])
    assert {edge["san"]: edge["frequency"] for edge in replies} == {"c5": 0.5, "e5": 0.5}
    assert all(edge["is_user_move"] is False for edge in replies)

    black_root_edges = _edges_from(black, black["root_position_id"])
    assert [(edge["san"], edge["is_user_move"]) for edge in black_root_edges] == [("d4", False)]
    black_reply = _edges_from(black, black_root_edges[0]["child_position_id"])[0]
    assert black_reply["san"] == "Nf6"
    assert black_reply["is_user_move"] is True
    assert (black_reply["wins"], black_reply["losses"]) == (1, 0)


def test_position_identity_merges_transpositions_but_preserves_routes(tmp_path: Path, monkeypatch) -> None:
    _prepare_database(tmp_path, monkeypatch, "transpositions.sqlite3")
    import_pgn_text(TRANSPOSITION_PGN)

    graph = repertoire_graph("white")
    transpositions = [position for position in graph["positions"].values() if position["is_transposition"]]

    assert len(transpositions) == 1
    transposed = transpositions[0]
    assert transposed["games"] == 2
    assert len(transposed["incoming_edge_ids"]) == 2
    incoming_sans = {graph["edges"][edge_id]["san"] for edge_id in transposed["incoming_edge_ids"]}
    assert incoming_sans == {"Nf6", "d5"}


def test_position_identity_ignores_move_counters() -> None:
    first = "8/8/8/8/8/8/8/K6k w - - 0 1"
    later = "8/8/8/8/8/8/8/K6k w - - 87 55"
    assert normalize_position_fen(first) == normalize_position_fen(later)


def test_repertoire_graph_remains_profile_scoped(tmp_path: Path, monkeypatch) -> None:
    _prepare_database(tmp_path, monkeypatch, "profiles.sqlite3")
    first = get_active_profile()
    second = create_profile("Second")
    import_pgn_text(COLOR_PGN, int(first["id"]))
    import_pgn_text(TRANSPOSITION_PGN, int(second["id"]))

    first_graph = repertoire_graph("white", int(first["id"]))
    second_graph = repertoire_graph("white", int(second["id"]))

    assert first_graph["games"] == 2
    assert second_graph["games"] == 2
    assert {edge["san"] for edge in _edges_from(first_graph, first_graph["root_position_id"])} == {"e4"}
    assert {edge["san"] for edge in _edges_from(second_graph, second_graph["root_position_id"])} == {"Nf3", "d4"}
