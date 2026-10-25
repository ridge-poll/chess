from pathlib import Path
import sqlite3

import app.config as config
import app.db as db
import app.services.chesscom_sync as chesscom_sync
from app.services.chesscom_sync import SyncOptions, sync_chesscom_archives
from app.services.games import dashboard, list_games
from app.services.imports import import_pgn_text
from app.services.opening_stats import opening_stats
from app.services.profiles import (
    create_profile,
    get_active_profile,
    list_profiles,
    set_active_profile,
    update_sync_preferences,
)


SICILIAN_PGN = """
[Event "Live Chess"]
[Site "Chess.com"]
[Date "2026.06.01"]
[White "ridgepoll1"]
[Black "opponent1"]
[Result "1-0"]
[TimeControl "600"]

1. e4 c5 2. Nf3 d6 1-0
"""

FRENCH_PGN = """
[Event "Live Chess"]
[Site "Chess.com"]
[Date "2026.06.02"]
[White "other"]
[Black "opponent2"]
[Result "0-1"]
[TimeControl "180"]

1. e4 e6 2. d4 d5 0-1
"""

SYNCED_PGN = """
[Event "Live Chess"]
[Site "Chess.com"]
[Date "2026.10.25"]
[White "returningplayer"]
[Black "newopponent"]
[Result "1-0"]
[TimeControl "300"]

1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 1-0
"""


def test_create_and_switch_profiles(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "test.sqlite3"
    monkeypatch.setattr(db, "settings", config.Settings(database_path=database_path))
    db.init_db(database_path)

    first = get_active_profile()
    second = create_profile("Study")
    active = set_active_profile(int(second["id"]))

    assert first["name"] == "Ridge"
    assert active["name"] == "Study"
    assert [profile["name"] for profile in list_profiles()] == ["Ridge", "Study"]


def test_imports_and_statistics_are_profile_specific(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "test.sqlite3"
    monkeypatch.setattr(db, "settings", config.Settings(database_path=database_path))
    db.init_db(database_path)
    profile_a = get_active_profile()
    profile_b = create_profile("Second")

    import_pgn_text(SICILIAN_PGN, int(profile_a["id"]))
    import_pgn_text(FRENCH_PGN, int(profile_b["id"]))

    games_a = list_games(int(profile_a["id"]))
    games_b = list_games(int(profile_b["id"]))
    dashboard_a = dashboard(int(profile_a["id"]))
    dashboard_b = dashboard(int(profile_b["id"]))
    openings_a = opening_stats(profile_id=int(profile_a["id"]))
    openings_b = opening_stats(profile_id=int(profile_b["id"]))

    assert len(games_a) == 1
    assert len(games_b) == 1
    assert games_a[0]["opening"] == "Sicilian Defense"
    assert games_b[0]["opening"] == "French Defense"
    assert dashboard_a["totals"]["games"] == 1
    assert dashboard_b["totals"]["games"] == 1
    assert dashboard_a["time_control_stats"][3]["time_class"] == "Rapid"
    assert dashboard_a["time_control_stats"][3]["games"] == 1
    assert dashboard_b["time_control_stats"][2]["time_class"] == "Blitz"
    assert dashboard_b["time_control_stats"][2]["games"] == 1
    assert openings_a[0]["opening"] == "Sicilian Defense"
    assert openings_b[0]["opening"] == "French Defense"


def test_existing_games_migrate_to_default_profile(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "legacy.sqlite3"
    monkeypatch.setattr(db, "settings", config.Settings(database_path=database_path))
    with sqlite3.connect(database_path) as conn:
        conn.executescript(
            """
            CREATE TABLE games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fingerprint TEXT NOT NULL UNIQUE,
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
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            INSERT INTO games (
                fingerprint, white, black, result, time_control, ply_count, raw_pgn
            )
            VALUES ('abc', 'ridgepoll1', 'opponent', '1-0', '600', 0, 'legacy');
            """
        )

    db.init_db(database_path)

    profiles = list_profiles()
    games = list_games(int(profiles[0]["id"]))

    assert profiles[0]["name"] == "Ridge"
    assert len(games) == 1
    assert games[0]["profile_id"] == profiles[0]["id"]


def test_profile_sync_preferences_are_profile_specific(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "test.sqlite3"
    monkeypatch.setattr(db, "settings", config.Settings(database_path=database_path))
    db.init_db(database_path)
    profile_a = get_active_profile()
    profile_b = create_profile("Second")

    update_sync_preferences(int(profile_a["id"]), "RidgePoll1", 14)
    update_sync_preferences(int(profile_b["id"]), "OtherPlayer", 30)
    profiles = {profile["name"]: profile for profile in list_profiles()}

    assert profiles["Ridge"]["chesscom_username"] == "ridgepoll1"
    assert profiles["Ridge"]["chesscom_sync_days"] == 14
    assert profiles["Second"]["chesscom_username"] == "otherplayer"
    assert profiles["Second"]["chesscom_sync_days"] == 30


def test_existing_installation_restores_active_profile_and_syncs_into_it(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "existing.sqlite3"
    monkeypatch.setattr(db, "settings", config.Settings(database_path=database_path))
    db.init_db(database_path)
    returning = create_profile("Returning")
    returning_id = int(returning["id"])
    update_sync_preferences(returning_id, "returningplayer", 7)
    set_active_profile(returning_id)
    existing_game_id = import_pgn_text(FRENCH_PGN, returning_id)["imported_game_ids"][0]

    # Simulate application startup after an upgrade against the existing file.
    db.init_db(database_path)

    assert int(get_active_profile()["id"]) == returning_id
    assert any(int(profile["id"]) == returning_id for profile in list_profiles())
    assert [game["id"] for game in list_games(returning_id)] == [existing_game_id]

    monkeypatch.setattr(chesscom_sync, "_fetch_archive_urls", lambda _username: ["archive"])
    monkeypatch.setattr(chesscom_sync, "_fetch_pgn_archive", lambda _url: SYNCED_PGN)
    result = sync_chesscom_archives(
        SyncOptions(username="returningplayer", limit=1, force=True, profile_id=returning_id)
    )

    assert result["imported"] == 1
    games = list_games(returning_id)
    assert len(games) == 2
    assert all(int(game["profile_id"]) == returning_id for game in games)
