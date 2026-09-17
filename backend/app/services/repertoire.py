from __future__ import annotations

from collections import defaultdict
from statistics import mean
from typing import Any

from app.analysis.metrics import accuracy_from_acpl
from app.db import get_connection
from app.pgn.openings import detect_opening_from_san
from app.services.games import _game_score_for_player, _infer_primary_player
from app.services.profiles import resolve_profile_id


STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


def repertoire_tree(profile_id: int | None = None, max_depth: int = 18) -> dict[str, object]:
    selected_profile_id = resolve_profile_id(profile_id)
    depth_limit = max(1, min(max_depth, 40))
    with get_connection() as conn:
        games = conn.execute(
            "SELECT * FROM games WHERE profile_id = ? ORDER BY played_at DESC, id DESC",
            (selected_profile_id,),
        ).fetchall()
        moves = conn.execute(
            """
            SELECT m.game_id, m.ply, m.san, m.uci, m.fen_after
            FROM moves m
            JOIN games g ON g.id = m.game_id
            WHERE g.profile_id = ? AND m.ply <= ?
            ORDER BY m.game_id, m.ply
            """,
            (selected_profile_id, depth_limit),
        ).fetchall()
        analysis_rows = conn.execute(
            """
            SELECT ma.game_id, AVG(ma.centipawn_loss) AS acpl
            FROM move_analyses ma
            JOIN games g ON g.id = ma.game_id
            WHERE g.profile_id = ? AND ma.centipawn_loss IS NOT NULL
            GROUP BY ma.game_id
            """,
            (selected_profile_id,),
        ).fetchall()

    player = _infer_primary_player(games)
    moves_by_game: dict[int, list[dict[str, object]]] = defaultdict(list)
    for move in moves:
        moves_by_game[int(move["game_id"])].append(move)
    accuracy_by_game = {
        int(row["game_id"]): accuracy_from_acpl(float(row["acpl"]))
        for row in analysis_rows
        if row["acpl"] is not None
    }

    root = _new_node("root", "Start", "", STARTING_FEN, 0, [])
    for game in games:
        game_id = int(game["id"])
        score = _game_score_for_player(game, player)
        accuracy = accuracy_by_game.get(game_id)
        _record_game(root, game_id, score, accuracy)
        node = root
        sans: list[str] = []
        path: list[str] = []
        for move in moves_by_game.get(game_id, []):
            san = str(move["san"])
            uci = str(move["uci"])
            sans.append(san)
            path.append(uci)
            child = node["_children"].get(uci)
            if child is None:
                child = _new_node(
                    "/".join(path),
                    san,
                    uci,
                    str(move["fen_after"]),
                    int(move["ply"]),
                    sans,
                )
                node["_children"][uci] = child
            _record_game(child, game_id, score, accuracy)
            node = child

    return {
        "profile_id": selected_profile_id,
        "player": player,
        "max_depth": depth_limit,
        "root": _serialize(root),
    }


def _new_node(
    node_id: str,
    san: str,
    uci: str,
    fen: str,
    ply: int,
    sans: list[str],
) -> dict[str, Any]:
    return {
        "id": node_id,
        "san": san,
        "uci": uci,
        "fen": fen,
        "ply": ply,
        "line": list(sans),
        "opening": detect_opening_from_san(sans) if sans else "Starting position",
        "_children": {},
        "_game_ids": set(),
        "_scores": [],
        "_accuracies": [],
    }


def _record_game(node: dict[str, Any], game_id: int, score: float | None, accuracy: float | None) -> None:
    if game_id in node["_game_ids"]:
        return
    node["_game_ids"].add(game_id)
    if score is not None:
        node["_scores"].append(float(score))
    if accuracy is not None:
        node["_accuracies"].append(float(accuracy))


def _serialize(node: dict[str, Any]) -> dict[str, object]:
    scores = node["_scores"]
    wins = sum(1 for score in scores if score == 1.0)
    draws = sum(1 for score in scores if score == 0.5)
    losses = sum(1 for score in scores if score == 0.0)
    children = sorted(
        (_serialize(child) for child in node["_children"].values()),
        key=lambda child: (-int(child["games"]), str(child["san"])),
    )
    return {
        "id": node["id"],
        "san": node["san"],
        "uci": node["uci"],
        "fen": node["fen"],
        "ply": node["ply"],
        "line": node["line"],
        "opening": node["opening"] or "Opening not identified",
        "games": len(node["_game_ids"]),
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "score_pct": round(mean(scores) * 100, 1) if scores else None,
        "average_accuracy": round(mean(node["_accuracies"]), 1) if node["_accuracies"] else None,
        "children": children,
    }
