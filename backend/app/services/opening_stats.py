from __future__ import annotations

from collections import defaultdict
from statistics import mean

from app.analysis.metrics import accuracy_from_acpl
from app.db import get_connection
from app.services.games import _game_score_for_player, _infer_primary_player
from app.services.profiles import resolve_profile_id


VALID_SORTS = {"most_played", "highest_win_rate", "highest_accuracy", "lowest_accuracy"}


def opening_stats(sort_by: str = "most_played", profile_id: int | None = None) -> list[dict[str, object]]:
    selected_sort = sort_by if sort_by in VALID_SORTS else "most_played"
    selected_profile_id = resolve_profile_id(profile_id)
    with get_connection() as conn:
        games = conn.execute("SELECT * FROM games WHERE profile_id = ?", (selected_profile_id,)).fetchall()
        rows = conn.execute(
            """
            SELECT g.id AS game_id, ma.centipawn_loss
            FROM games g
            LEFT JOIN move_analyses ma ON ma.game_id = g.id
            WHERE g.profile_id = ?
            """,
            (selected_profile_id,),
        ).fetchall()

    player = _infer_primary_player(games)
    losses_by_game: dict[int, list[int]] = defaultdict(list)
    for row in rows:
        if row["centipawn_loss"] is not None:
            losses_by_game[int(row["game_id"])].append(int(row["centipawn_loss"]))

    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for game in games:
        opening = str(game.get("opening") or game.get("eco") or "Unknown")
        grouped[opening].append(game)

    stats = []
    for opening, items in grouped.items():
        wins = draws = losses = 0
        accuracies = []
        lengths = []
        for game in items:
            score = _game_score_for_player(game, player)
            if score == 1.0:
                wins += 1
            elif score == 0.5:
                draws += 1
            elif score == 0.0:
                losses += 1

            game_losses = losses_by_game.get(int(game["id"]), [])
            if game_losses:
                accuracies.append(accuracy_from_acpl(mean(game_losses)))
            if game.get("ply_count") is not None:
                lengths.append(float(game["ply_count"]) / 2)

        total = len(items)
        average_accuracy = round(mean([value for value in accuracies if value is not None]), 1) if accuracies else None
        stats.append(
            {
                "opening": opening,
                "games": total,
                "wins": wins,
                "draws": draws,
                "losses": losses,
                "win_pct": _pct(wins, total),
                "draw_pct": _pct(draws, total),
                "loss_pct": _pct(losses, total),
                "average_accuracy": average_accuracy,
                "average_game_length": round(mean(lengths), 1) if lengths else None,
            }
        )

    if selected_sort == "highest_win_rate":
        stats.sort(key=lambda row: (-float(row["win_pct"]), -int(row["games"]), str(row["opening"])))
    elif selected_sort == "highest_accuracy":
        stats.sort(key=lambda row: (-(row["average_accuracy"] or -1), -int(row["games"]), str(row["opening"])))
    elif selected_sort == "lowest_accuracy":
        stats.sort(key=lambda row: ((row["average_accuracy"] if row["average_accuracy"] is not None else 101), -int(row["games"]), str(row["opening"])))
    else:
        stats.sort(key=lambda row: (-int(row["games"]), str(row["opening"])))
    return stats


def _pct(value: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round((value / total) * 100, 1)
