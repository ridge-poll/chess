from __future__ import annotations

from collections import Counter, defaultdict
from statistics import mean

from app.analysis.metrics import accuracy_from_acpl, score_to_cp
from app.db import get_connection
from app.services.position_analysis import get_game_positions
from app.services.profiles import resolve_profile_id


def list_games(profile_id: int | None = None) -> list[dict[str, object]]:
    selected_profile_id = resolve_profile_id(profile_id)
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT
                g.*,
                COALESCE(MAX(j.status), 'not_analyzed') AS analysis_status,
                COALESCE(MAX(j.analyzed_plies), 0) AS analyzed_plies,
                COALESCE(MAX(j.total_plies), g.ply_count) AS total_plies,
                ROUND(AVG(ma.centipawn_loss), 1) AS acpl
            FROM games g
            LEFT JOIN analysis_jobs j ON j.game_id = g.id
            LEFT JOIN move_analyses ma ON ma.game_id = g.id
            WHERE g.profile_id = ?
            GROUP BY g.id
            ORDER BY g.played_at DESC, g.id DESC
            """,
            (selected_profile_id,),
        ).fetchall()


def get_game_detail(game_id: int, profile_id: int | None = None) -> dict[str, object] | None:
    positions = get_game_positions(game_id, profile_id)
    if not positions:
        return None
    return {
        "game": positions["game"],
        "moves": positions["positions"],
        "depth": positions["depth"],
        "evaluation_history": positions["evaluation_history"],
        "evaluation_summary": positions["evaluation_summary"],
        "quality_counts": positions["quality_counts"],
        "starting_fen": positions["starting_fen"],
    }


def delete_game(game_id: int, profile_id: int | None = None) -> bool:
    selected_profile_id = resolve_profile_id(profile_id)
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM games WHERE id = ? AND profile_id = ?",
            (game_id, selected_profile_id),
        )
        return cursor.rowcount > 0


def dashboard(profile_id: int | None = None) -> dict[str, object]:
    selected_profile_id = resolve_profile_id(profile_id)
    games = list_games(selected_profile_id)
    primary_player = _infer_primary_player(games)
    with get_connection() as conn:
        analyses = conn.execute(
            """
            SELECT g.id, g.played_at, g.result, g.white_elo, g.black_elo,
                   g.white, g.black, g.player_color, g.opening, g.eco,
                   m.phase, m.color, ma.centipawn_loss, ma.classification,
                   ma.eval_before_cp, ma.eval_after_cp, ma.mate_before, ma.mate_after
            FROM games g
            LEFT JOIN moves m ON m.game_id = g.id
            LEFT JOIN move_analyses ma ON ma.game_id = m.game_id AND ma.ply = m.ply
            WHERE g.profile_id = ?
            ORDER BY g.played_at, g.id, m.ply
            """,
            (selected_profile_id,),
        ).fetchall()
        openings = conn.execute(
            """
            SELECT
                opening,
                COUNT(*) AS games,
                ROUND(AVG(CASE
                    WHEN result = '1-0' THEN 1.0
                    WHEN result = '1/2-1/2' THEN 0.5
                    ELSE 0.0
                END), 3) AS score_rate,
                ROUND(AVG(game_acpl), 1) AS acpl
            FROM (
                SELECT
                    g.id,
                    COALESCE(g.opening, 'Unknown') AS opening,
                    g.result,
                    AVG(ma.centipawn_loss) AS game_acpl
                FROM games g
                LEFT JOIN move_analyses ma ON ma.game_id = g.id
                WHERE g.profile_id = ?
                GROUP BY g.id
            )
            GROUP BY opening
            ORDER BY games DESC, opening ASC
            LIMIT 20
            """,
            (selected_profile_id,),
        ).fetchall()

    result_counts = {"wins": 0, "losses": 0, "draws": 0}
    for game in games:
        score = _game_score_for_player(game, primary_player)
        if score == 0.5:
            result_counts["draws"] += 1
        elif score == 1.0:
            result_counts["wins"] += 1
        elif score == 0.0:
            result_counts["losses"] += 1

    losses = [row["centipawn_loss"] for row in analyses if row["centipawn_loss"] is not None]
    acpl = round(mean(losses), 1) if losses else None
    mistakes = _count_by_classification(analyses)
    phases = _phase_stats(analyses)
    trend = _trend_rows(analyses)
    rating_trend = _rating_trend(games, primary_player)
    opening_summary = _opening_summary(games, analyses, primary_player)
    mistake_breakdown = _mistake_breakdown(analyses, primary_player)
    time_control_stats = _time_control_stats(games, primary_player)
    insights = _insight_cards(acpl, trend, phases, opening_summary, mistake_breakdown)

    return {
        "totals": {
            "games": len(games),
            "analyzed_games": sum(1 for game in games if game["analysis_status"] == "complete"),
            "acpl": acpl,
            "accuracy": accuracy_from_acpl(acpl),
            **result_counts,
            **mistakes,
        },
        "profile_id": selected_profile_id,
        "player": primary_player,
        "trend": trend,
        "rating_trend": rating_trend,
        "openings": openings,
        "opening_summary": opening_summary,
        "phases": phases,
        "mistake_breakdown": mistake_breakdown,
        "time_control_stats": time_control_stats,
        "insights": insights,
        "recent_games": games[:10],
    }


def _count_by_classification(rows: list[dict[str, object]]) -> dict[str, int]:
    counts = {"inaccuracies": 0, "mistakes": 0, "blunders": 0}
    for row in rows:
        if row["classification"] == "inaccuracy":
            counts["inaccuracies"] += 1
        elif row["classification"] == "mistake":
            counts["mistakes"] += 1
        elif row["classification"] == "blunder":
            counts["blunders"] += 1
    return counts


def _phase_stats(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, list[int]] = defaultdict(list)
    for row in rows:
        if row["phase"] and row["centipawn_loss"] is not None:
            grouped[str(row["phase"])].append(int(row["centipawn_loss"]))
    stats = [
        {
            "phase": phase,
            "moves": len(values),
            "acpl": round(mean(values), 1),
            "accuracy": accuracy_from_acpl(mean(values)),
        }
        for phase, values in grouped.items()
    ]
    stats.sort(key=lambda row: {"opening": 0, "middlegame": 1, "endgame": 2}.get(str(row["phase"]), 9))
    if stats:
        best = min(stats, key=lambda row: float(row["acpl"]))
        weakest = max(stats, key=lambda row: float(row["acpl"]))
        for row in stats:
            row["label"] = "steady"
            if row["phase"] == best["phase"]:
                row["label"] = "strength"
            if row["phase"] == weakest["phase"]:
                row["label"] = "focus"
    return stats


def _trend_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[int, list[int]] = defaultdict(list)
    dates: dict[int, object] = {}
    for row in rows:
        if row["centipawn_loss"] is None:
            continue
        game_id = int(row["id"])
        grouped[game_id].append(int(row["centipawn_loss"]))
        dates[game_id] = row["played_at"]
    return [
        {
            "game_id": game_id,
            "played_at": dates[game_id],
            "acpl": round(mean(values), 1),
            "accuracy": accuracy_from_acpl(mean(values)),
        }
        for game_id, values in grouped.items()
    ][-25:]


def _infer_primary_player(games: list[dict[str, object]]) -> str | None:
    names: Counter[str] = Counter()
    display_names: dict[str, str] = {}
    for game in games:
        for key in ("white", "black"):
            name = game.get(key)
            if not name:
                continue
            normalized = str(name).lower()
            names[normalized] += 1
            display_names[normalized] = str(name)
    if not names:
        return None
    player, count = names.most_common(1)[0]
    if count <= 1 and len(names) > 1:
        return None
    return display_names[player]


def _player_color(game: dict[str, object], primary_player: str | None) -> str | None:
    if game.get("player_color"):
        return str(game["player_color"])
    if not primary_player:
        return None
    if game.get("white") and str(game["white"]).lower() == primary_player.lower():
        return "white"
    if game.get("black") and str(game["black"]).lower() == primary_player.lower():
        return "black"
    return None


def _game_score_for_player(game: dict[str, object], primary_player: str | None) -> float | None:
    result = game.get("result")
    if result == "1/2-1/2":
        return 0.5
    color = _player_color(game, primary_player)
    if result == "1-0":
        return 1.0 if color in {None, "white"} else 0.0
    if result == "0-1":
        return 1.0 if color == "black" else 0.0
    return None


def _rating_for_player(game: dict[str, object], primary_player: str | None) -> int | None:
    color = _player_color(game, primary_player)
    if color == "white":
        return game.get("white_elo")  # type: ignore[return-value]
    if color == "black":
        return game.get("black_elo")  # type: ignore[return-value]
    return game.get("white_elo") or game.get("black_elo")  # type: ignore[return-value]


def _rating_trend(games: list[dict[str, object]], primary_player: str | None) -> list[dict[str, object]]:
    rows = []
    for game in sorted(games, key=lambda row: (str(row.get("played_at") or ""), int(row["id"]))):
        rating = _rating_for_player(game, primary_player)
        if rating is None:
            continue
        rows.append(
            {
                "game_id": game["id"],
                "played_at": game["played_at"],
                "rating": rating,
            }
        )
    return rows[-40:]


def _time_control_stats(
    games: list[dict[str, object]],
    primary_player: str | None,
) -> list[dict[str, object]]:
    buckets = ["Overall", "Bullet", "Blitz", "Rapid", "Classical", "Daily / Correspondence"]
    grouped: dict[str, list[dict[str, object]]] = {bucket: [] for bucket in buckets}
    for game in games:
        grouped["Overall"].append(game)
        time_class = str(game.get("time_class") or "Unknown")
        grouped.setdefault(time_class, []).append(game)

    rows = []
    for label in buckets:
        items = grouped.get(label, [])
        wins = losses = draws = 0
        acpls = []
        lengths = []
        for game in items:
            score = _game_score_for_player(game, primary_player)
            if score == 1.0:
                wins += 1
            elif score == 0.5:
                draws += 1
            elif score == 0.0:
                losses += 1
            if game.get("acpl") is not None:
                acpls.append(float(game["acpl"]))
            if game.get("ply_count") is not None:
                lengths.append(float(game["ply_count"]) / 2)

        acpl = round(mean(acpls), 1) if acpls else None
        rows.append(
            {
                "time_class": label,
                "games": len(items),
                "wins": wins,
                "losses": losses,
                "draws": draws,
                "accuracy": accuracy_from_acpl(acpl),
                "acpl": acpl,
                "average_game_length": round(mean(lengths), 1) if lengths else None,
            }
        )
    return rows


def _opening_summary(
    games: list[dict[str, object]],
    analyses: list[dict[str, object]],
    primary_player: str | None,
) -> dict[str, object]:
    losses_by_game: dict[int, list[int]] = defaultdict(list)
    for row in analyses:
        if row["centipawn_loss"] is not None:
            losses_by_game[int(row["id"])].append(int(row["centipawn_loss"]))

    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for game in games:
        opening = str(game.get("opening") or game.get("eco") or "Unknown")
        values = losses_by_game.get(int(game["id"]), [])
        grouped[opening].append(
            {
                "score": _game_score_for_player(game, primary_player),
                "acpl": mean(values) if values else None,
            }
        )

    rows = []
    for opening, items in grouped.items():
        scores = [item["score"] for item in items if item["score"] is not None]
        acpls = [item["acpl"] for item in items if item["acpl"] is not None]
        rows.append(
            {
                "opening": opening,
                "games": len(items),
                "score_rate": round(mean(scores), 3) if scores else None,
                "acpl": round(mean(acpls), 1) if acpls else None,
            }
        )

    scored = [row for row in rows if row["acpl"] is not None]
    best = sorted(scored, key=lambda row: (float(row["acpl"]), -int(row["games"])))[:3]
    weakest = sorted(scored, key=lambda row: (-float(row["acpl"]), -int(row["games"])))[:3]
    frequent = sorted(rows, key=lambda row: (-int(row["games"]), str(row["opening"])))[:5]
    return {"best": best, "weakest": weakest, "frequent": frequent}


def _mistake_breakdown(
    rows: list[dict[str, object]],
    primary_player: str | None,
) -> dict[str, object]:
    breakdown = {
        "inaccuracies": 0,
        "mistakes": 0,
        "blunders": 0,
        "large_eval_swings": 0,
        "conversion_failures": 0,
        "defensive_saves": 0,
    }
    worst_moves = []
    for row in rows:
        loss = row.get("centipawn_loss")
        if loss is None:
            continue
        loss = int(loss)
        classification = row.get("classification")
        if classification in {"inaccuracy", "mistake", "blunder"}:
            key = "inaccuracies" if classification == "inaccuracy" else f"{classification}s"
            breakdown[key] += 1
        if loss >= 300:
            breakdown["large_eval_swings"] += 1

        player_color = _player_color(row, primary_player)
        mover_color = row.get("color")
        before = _player_eval(row, "before", player_color)
        if player_color and mover_color == player_color and before is not None:
            if before >= 300 and loss >= 150:
                breakdown["conversion_failures"] += 1
            if before <= -200 and loss <= 20:
                breakdown["defensive_saves"] += 1

        if loss >= 75:
            worst_moves.append(
                {
                    "game_id": row["id"],
                    "played_at": row["played_at"],
                    "phase": row["phase"],
                    "opening": row.get("opening") or row.get("eco") or "Unknown",
                    "loss": loss,
                    "classification": classification,
                }
            )

    worst_moves.sort(key=lambda row: int(row["loss"]), reverse=True)
    return {**breakdown, "worst_moves": worst_moves[:8]}


def _player_eval(row: dict[str, object], side: str, player_color: str | None) -> int | None:
    cp = row.get(f"eval_{side}_cp")
    mate = row.get(f"mate_{side}")
    value = score_to_cp(cp, mate)  # type: ignore[arg-type]
    if value is None:
        return None
    return value if player_color != "black" else -value


def _insight_cards(
    acpl: float | None,
    trend: list[dict[str, object]],
    phases: list[dict[str, object]],
    opening_summary: dict[str, object],
    mistake_breakdown: dict[str, object],
) -> list[dict[str, str]]:
    cards: list[dict[str, str]] = []
    if acpl is not None:
        cards.append(
            {
                "title": "Current Baseline",
                "body": f"Your analyzed average is {acpl} ACPL, roughly {accuracy_from_acpl(acpl)}% accuracy.",
            }
        )
    if len(trend) >= 2:
        recent = mean(float(row["acpl"]) for row in trend[-3:])
        previous = mean(float(row["acpl"]) for row in trend[: max(1, len(trend) - 3)])
        direction = "improving" if recent < previous else "slipping"
        cards.append(
            {
                "title": "Recent Form",
                "body": f"Recent games are {direction}: last games average {round(recent, 1)} ACPL versus {round(previous, 1)} before.",
            }
        )
    focus_phase = next((phase for phase in phases if phase.get("label") == "focus"), None)
    if focus_phase:
        cards.append(
            {
                "title": "Phase Focus",
                "body": f"{str(focus_phase['phase']).title()} is the highest-ACPL phase at {focus_phase['acpl']}.",
            }
        )
    weakest = opening_summary.get("weakest") or []
    if weakest:
        opening = weakest[0]
        cards.append(
            {
                "title": "Opening Watch",
                "body": f"{opening['opening']} is currently your roughest opening sample at {opening['acpl']} ACPL.",
            }
        )
    if mistake_breakdown["conversion_failures"]:
        cards.append(
            {
                "title": "Conversion",
                "body": f"{mistake_breakdown['conversion_failures']} mistakes came from promising positions. Those are high-value review targets.",
            }
        )
    return cards[:5]
