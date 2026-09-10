from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from app.config import settings


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS games (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    fingerprint TEXT NOT NULL,
    event TEXT,
    site TEXT,
    played_at TEXT,
    white TEXT,
    black TEXT,
    player_color TEXT,
    result TEXT,
    eco TEXT,
    opening TEXT,
    time_control TEXT,
    time_class TEXT,
    white_elo INTEGER,
    black_elo INTEGER,
    ply_count INTEGER NOT NULL DEFAULT 0,
    raw_pgn TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(profile_id, fingerprint)
);

CREATE TABLE IF NOT EXISTS profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    chesscom_username TEXT,
    chesscom_sync_days INTEGER NOT NULL DEFAULT 7,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS moves (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    ply INTEGER NOT NULL,
    move_number INTEGER NOT NULL,
    color TEXT NOT NULL,
    san TEXT NOT NULL,
    uci TEXT NOT NULL,
    fen_before TEXT NOT NULL,
    fen_after TEXT NOT NULL,
    phase TEXT NOT NULL,
    clock_seconds REAL,
    UNIQUE(game_id, ply)
);

CREATE TABLE IF NOT EXISTS position_evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fen TEXT NOT NULL,
    depth INTEGER NOT NULL,
    best_move TEXT,
    score_cp INTEGER,
    mate INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(fen, depth)
);

CREATE TABLE IF NOT EXISTS move_analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    ply INTEGER NOT NULL,
    depth INTEGER NOT NULL,
    played_uci TEXT NOT NULL,
    best_uci TEXT,
    eval_before_cp INTEGER,
    eval_after_cp INTEGER,
    mate_before INTEGER,
    mate_after INTEGER,
    centipawn_loss INTEGER,
    classification TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(game_id, ply, depth)
);

CREATE TABLE IF NOT EXISTS analysis_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    depth INTEGER NOT NULL,
    status TEXT NOT NULL,
    analyzed_plies INTEGER NOT NULL DEFAULT 0,
    total_plies INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(game_id, depth)
);

CREATE TABLE IF NOT EXISTS chesscom_syncs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    username TEXT NOT NULL,
    archive_url TEXT NOT NULL,
    status TEXT NOT NULL,
    imported INTEGER NOT NULL DEFAULT 0,
    duplicates INTEGER NOT NULL DEFAULT 0,
    errors TEXT,
    synced_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(profile_id, username, archive_url)
);
"""


def _dict_factory(cursor: sqlite3.Cursor, row: tuple[object, ...]) -> dict[str, object]:
    return {column[0]: row[index] for index, column in enumerate(cursor.description)}


def init_db(database_path: Path | None = None) -> None:
    path = database_path or settings.database_path
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        _ensure_profile_tables(conn)
        _migrate(conn)
        conn.executescript(SCHEMA)


def _migrate(conn: sqlite3.Connection) -> None:
    default_profile_id = _ensure_default_profile(conn)
    columns = {
        row[1]
        for row in conn.execute("PRAGMA table_info(games)").fetchall()
    }
    if columns and "profile_id" not in columns:
        _rebuild_games_with_profiles(conn, default_profile_id)
        columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(games)").fetchall()
        }
    if columns and "time_class" not in columns:
        conn.execute("ALTER TABLE games ADD COLUMN time_class TEXT")

    move_columns = {
        row[1]
        for row in conn.execute("PRAGMA table_info(moves)").fetchall()
    }
    if move_columns and "clock_seconds" not in move_columns:
        conn.execute("ALTER TABLE moves ADD COLUMN clock_seconds REAL")

    sync_columns = {
        row[1]
        for row in conn.execute("PRAGMA table_info(chesscom_syncs)").fetchall()
    }
    if sync_columns and "profile_id" not in sync_columns:
        _rebuild_syncs_with_profiles(conn, default_profile_id)

    profile_columns = {
        row[1]
        for row in conn.execute("PRAGMA table_info(profiles)").fetchall()
    }
    if profile_columns and "chesscom_username" not in profile_columns:
        conn.execute("ALTER TABLE profiles ADD COLUMN chesscom_username TEXT")
    if profile_columns and "chesscom_sync_days" not in profile_columns:
        conn.execute("ALTER TABLE profiles ADD COLUMN chesscom_sync_days INTEGER NOT NULL DEFAULT 7")

    active = conn.execute("SELECT value FROM app_settings WHERE key = 'active_profile_id'").fetchone()
    if not active:
        conn.execute(
            "INSERT INTO app_settings (key, value) VALUES ('active_profile_id', ?)",
            (str(default_profile_id),),
        )


def _ensure_profile_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            chesscom_username TEXT,
            chesscom_sync_days INTEGER NOT NULL DEFAULT 7,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """
    )


def _ensure_default_profile(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT id FROM profiles ORDER BY id LIMIT 1").fetchone()
    if row:
        return int(row[0])
    cursor = conn.execute("INSERT INTO profiles (name) VALUES (?)", ("Ridge",))
    return int(cursor.lastrowid)


def _rebuild_games_with_profiles(conn: sqlite3.Connection, default_profile_id: int) -> None:
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.executescript(
        """
        CREATE TABLE games_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
            fingerprint TEXT NOT NULL,
            event TEXT,
            site TEXT,
            played_at TEXT,
            white TEXT,
            black TEXT,
            player_color TEXT,
            result TEXT,
            eco TEXT,
            opening TEXT,
            time_control TEXT,
            time_class TEXT,
            white_elo INTEGER,
            black_elo INTEGER,
            ply_count INTEGER NOT NULL DEFAULT 0,
            raw_pgn TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(profile_id, fingerprint)
        );
        """
    )
    existing_columns = {
        row[1]
        for row in conn.execute("PRAGMA table_info(games)").fetchall()
    }
    time_class_expr = "time_class" if "time_class" in existing_columns else "NULL"
    conn.execute(
        f"""
        INSERT INTO games_new (
            id, profile_id, fingerprint, event, site, played_at, white, black,
            player_color, result, eco, opening, time_control, time_class,
            white_elo, black_elo, ply_count, raw_pgn, created_at
        )
        SELECT
            id, ?, fingerprint, event, site, played_at, white, black,
            player_color, result, eco, opening, time_control, {time_class_expr},
            white_elo, black_elo, ply_count, raw_pgn, created_at
        FROM games
        """,
        (default_profile_id,),
    )
    conn.execute("DROP TABLE games")
    conn.execute("ALTER TABLE games_new RENAME TO games")
    conn.execute("PRAGMA foreign_keys = ON")


def _rebuild_syncs_with_profiles(conn: sqlite3.Connection, default_profile_id: int) -> None:
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.executescript(
        """
        CREATE TABLE chesscom_syncs_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
            username TEXT NOT NULL,
            archive_url TEXT NOT NULL,
            status TEXT NOT NULL,
            imported INTEGER NOT NULL DEFAULT 0,
            duplicates INTEGER NOT NULL DEFAULT 0,
            errors TEXT,
            synced_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(profile_id, username, archive_url)
        );
        """
    )
    conn.execute(
        """
        INSERT INTO chesscom_syncs_new (
            id, profile_id, username, archive_url, status, imported,
            duplicates, errors, synced_at
        )
        SELECT id, ?, username, archive_url, status, imported, duplicates, errors, synced_at
        FROM chesscom_syncs
        """,
        (default_profile_id,),
    )
    conn.execute("DROP TABLE chesscom_syncs")
    conn.execute("ALTER TABLE chesscom_syncs_new RENAME TO chesscom_syncs")
    conn.execute("PRAGMA foreign_keys = ON")


@contextmanager
def get_connection(database_path: Path | None = None) -> Iterator[sqlite3.Connection]:
    path = database_path or settings.database_path
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = _dict_factory
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
