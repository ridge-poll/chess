from __future__ import annotations

import sqlite3
from dataclasses import asdict

from app.db import get_connection
from app.models import ParsedGame
from app.pgn.parser import parse_pgn_text
from app.services.profiles import resolve_profile_id


def import_pgn_text(pgn_text: str, profile_id: int | None = None) -> dict[str, object]:
    selected_profile_id = resolve_profile_id(profile_id)
    parsed_games, errors = parse_pgn_text(pgn_text)
    imported: list[int] = []
    duplicates: list[str] = []

    with get_connection() as conn:
        for game in parsed_games:
            try:
                game_id = _insert_game(conn, game, selected_profile_id)
            except sqlite3.IntegrityError:
                duplicates.append(game.fingerprint)
                continue
            imported.append(game_id)

    return {
        "imported": len(imported),
        "imported_game_ids": imported,
        "duplicates": len(duplicates),
        "profile_id": selected_profile_id,
        "errors": errors,
    }


def _insert_game(conn: sqlite3.Connection, game: ParsedGame, profile_id: int) -> int:
    cursor = conn.execute(
        """
        INSERT INTO games (
            profile_id, fingerprint, event, site, played_at, white, black, player_color, result,
            eco, opening, time_control, time_class, white_elo, black_elo, ply_count, raw_pgn
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            profile_id,
            game.fingerprint,
            game.event,
            game.site,
            game.played_at,
            game.white,
            game.black,
            game.player_color,
            game.result,
            game.eco,
            game.opening,
            game.time_control,
            game.time_class,
            game.white_elo,
            game.black_elo,
            len(game.moves),
            game.raw_pgn,
        ),
    )
    game_id = int(cursor.lastrowid)
    conn.executemany(
        """
        INSERT INTO moves (
            game_id, ply, move_number, color, san, uci, fen_before, fen_after, phase, clock_seconds
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                game_id,
                move.ply,
                move.move_number,
                move.color,
                move.san,
                move.uci,
                move.fen_before,
                move.fen_after,
                move.phase,
                move.clock_seconds,
            )
            for move in game.moves
        ],
    )
    return game_id


def preview_pgn_text(pgn_text: str) -> dict[str, object]:
    parsed_games, errors = parse_pgn_text(pgn_text)
    return {
        "games": [
            {
                **asdict(game),
                "moves": len(game.moves),
                "raw_pgn": "",
            }
            for game in parsed_games
        ],
        "errors": errors,
    }
