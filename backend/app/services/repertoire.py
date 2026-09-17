from __future__ import annotations

from collections import defaultdict
import hashlib
from statistics import mean
from typing import Any

from app.analysis.metrics import accuracy_from_acpl
from app.db import get_connection
from app.pgn.openings import detect_opening_from_san
from app.services.games import _game_score_for_player, _infer_primary_player, _player_color
from app.services.profiles import resolve_profile_id


STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
REPERTOIRE_COLORS = {"white", "black"}


def repertoire_graph(
    color: str,
    profile_id: int | None = None,
    max_depth: int = 24,
) -> dict[str, object]:
    selected_color = color.lower().strip()
    if selected_color not in REPERTOIRE_COLORS:
        raise ValueError("Repertoire color must be 'white' or 'black'.")

    selected_profile_id = resolve_profile_id(profile_id)
    depth_limit = max(1, min(max_depth, 60))
    with get_connection() as conn:
        profile = conn.execute(
            "SELECT chesscom_username FROM profiles WHERE id = ?",
            (selected_profile_id,),
        ).fetchone()
        games = conn.execute(
            "SELECT * FROM games WHERE profile_id = ? ORDER BY played_at, id",
            (selected_profile_id,),
        ).fetchall()
        moves = conn.execute(
            """
            SELECT m.game_id, m.ply, m.color, m.san, m.uci, m.fen_before, m.fen_after
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

    configured_player = str(profile["chesscom_username"]) if profile and profile.get("chesscom_username") else None
    player = configured_player or _infer_primary_player(games)
    selected_games = [game for game in games if _player_color(game, player) == selected_color]
    selected_game_ids = {int(game["id"]) for game in selected_games}
    excluded_games = len(games) - len(selected_games)
    moves_by_game: dict[int, list[dict[str, object]]] = defaultdict(list)
    for move in moves:
        game_id = int(move["game_id"])
        if game_id in selected_game_ids:
            moves_by_game[game_id].append(move)
    accuracy_by_game = {
        int(row["game_id"]): accuracy_from_acpl(float(row["acpl"]))
        for row in analysis_rows
        if row["acpl"] is not None and int(row["game_id"]) in selected_game_ids
    }

    positions: dict[str, dict[str, Any]] = {}
    edges: dict[str, dict[str, Any]] = {}
    root_id = _position_id(STARTING_FEN)
    _ensure_position(positions, STARTING_FEN, 0)

    for game in selected_games:
        game_id = int(game["id"])
        score = _game_score_for_player(game, player)
        accuracy = accuracy_by_game.get(game_id)
        sans: list[str] = []
        current_position_id = root_id
        _record_graph_position(positions[current_position_id], game_id, score, accuracy, "Starting position")

        for move in moves_by_game.get(game_id, []):
            san = str(move["san"])
            uci = str(move["uci"])
            sans.append(san)
            child_position_id = _ensure_position(positions, str(move["fen_after"]), int(move["ply"]))
            opening = detect_opening_from_san(sans) or "Opening not identified"
            _record_graph_position(positions[child_position_id], game_id, score, accuracy, opening)

            edge_id = _edge_id(current_position_id, uci, child_position_id)
            if edge_id not in edges:
                edges[edge_id] = {
                    "id": edge_id,
                    "parent_position_id": current_position_id,
                    "child_position_id": child_position_id,
                    "san": san,
                    "uci": uci,
                    "mover_color": str(move["color"]),
                    "is_user_move": str(move["color"]) == selected_color,
                    "observed": True,
                    "book_status": "unknown",
                    "_game_ids": set(),
                    "_scores": {},
                }
            _record_graph_edge(edges[edge_id], game_id, score)
            positions[current_position_id]["_outgoing_edge_ids"].add(edge_id)
            positions[child_position_id]["_incoming_edge_ids"].add(edge_id)
            current_position_id = child_position_id

    serialized_positions = {
        position_id: _serialize_graph_position(position)
        for position_id, position in positions.items()
    }
    serialized_edges = {
        edge_id: _serialize_graph_edge(edge, positions[edge["parent_position_id"]])
        for edge_id, edge in edges.items()
    }
    return {
        "profile_id": selected_profile_id,
        "player": player,
        "color": selected_color,
        "max_depth": depth_limit,
        "root_position_id": root_id,
        "games": len(selected_games),
        "excluded_games": excluded_games,
        "positions": serialized_positions,
        "edges": serialized_edges,
    }


def normalize_position_fen(fen: str) -> str:
    fields = fen.split()
    if len(fields) < 4:
        raise ValueError("A complete FEN is required for position identity.")
    return " ".join(fields[:4])


def _position_id(fen: str) -> str:
    normalized = normalize_position_fen(fen)
    return f"pos_{hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:20]}"


def _edge_id(parent_position_id: str, uci: str, child_position_id: str) -> str:
    identity = f"{parent_position_id}|{uci}|{child_position_id}"
    return f"edge_{hashlib.sha256(identity.encode('utf-8')).hexdigest()[:20]}"


def _ensure_position(positions: dict[str, dict[str, Any]], fen: str, ply: int) -> str:
    position_id = _position_id(fen)
    if position_id not in positions:
        positions[position_id] = {
            "id": position_id,
            "fen": fen,
            "normalized_fen": normalize_position_fen(fen),
            "turn": "white" if fen.split()[1] == "w" else "black",
            "min_ply": ply,
            "max_ply": ply,
            "_game_ids": set(),
            "_scores": {},
            "_accuracies": {},
            "_opening_counts": defaultdict(int),
            "_incoming_edge_ids": set(),
            "_outgoing_edge_ids": set(),
        }
    else:
        positions[position_id]["min_ply"] = min(int(positions[position_id]["min_ply"]), ply)
        positions[position_id]["max_ply"] = max(int(positions[position_id]["max_ply"]), ply)
    return position_id


def _record_graph_position(
    position: dict[str, Any],
    game_id: int,
    score: float | None,
    accuracy: float | None,
    opening: str,
) -> None:
    position["_game_ids"].add(game_id)
    if score is not None:
        position["_scores"][game_id] = float(score)
    if accuracy is not None:
        position["_accuracies"][game_id] = float(accuracy)
    position["_opening_counts"][opening] += 1


def _record_graph_edge(edge: dict[str, Any], game_id: int, score: float | None) -> None:
    edge["_game_ids"].add(game_id)
    if score is not None:
        edge["_scores"][game_id] = float(score)


def _result_counts(scores: list[float]) -> tuple[int, int, int]:
    return (
        sum(1 for score in scores if score == 1.0),
        sum(1 for score in scores if score == 0.5),
        sum(1 for score in scores if score == 0.0),
    )


def _serialize_graph_position(position: dict[str, Any]) -> dict[str, object]:
    scores = list(position["_scores"].values())
    wins, draws, losses = _result_counts(scores)
    opening_counts = position["_opening_counts"]
    opening = max(opening_counts, key=lambda name: (opening_counts[name], len(name))) if opening_counts else "Opening not identified"
    incoming = sorted(position["_incoming_edge_ids"])
    return {
        "id": position["id"],
        "fen": position["fen"],
        "normalized_fen": position["normalized_fen"],
        "turn": position["turn"],
        "min_ply": position["min_ply"],
        "max_ply": position["max_ply"],
        "opening": opening,
        "games": len(position["_game_ids"]),
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "score_pct": round(mean(scores) * 100, 1) if scores else None,
        "average_accuracy": round(mean(position["_accuracies"].values()), 1) if position["_accuracies"] else None,
        "incoming_edge_ids": incoming,
        "outgoing_edge_ids": sorted(position["_outgoing_edge_ids"]),
        "is_transposition": len(incoming) > 1,
    }


def _serialize_graph_edge(edge: dict[str, Any], parent: dict[str, Any]) -> dict[str, object]:
    scores = list(edge["_scores"].values())
    wins, draws, losses = _result_counts(scores)
    games = len(edge["_game_ids"])
    parent_games = len(parent["_game_ids"])
    return {
        "id": edge["id"],
        "parent_position_id": edge["parent_position_id"],
        "child_position_id": edge["child_position_id"],
        "san": edge["san"],
        "uci": edge["uci"],
        "mover_color": edge["mover_color"],
        "is_user_move": edge["is_user_move"],
        "observed": edge["observed"],
        "book_status": edge["book_status"],
        "games": games,
        "parent_games": parent_games,
        "frequency": round(games / parent_games, 4) if parent_games else 0.0,
        "wins": wins,
        "draws": draws,
        "losses": losses,
    }


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
