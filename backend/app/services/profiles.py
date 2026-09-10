from __future__ import annotations

from app.db import get_connection


DEFAULT_PROFILE_NAME = "Ridge"


def list_profiles() -> list[dict[str, object]]:
    with get_connection() as conn:
        return conn.execute("SELECT * FROM profiles ORDER BY name").fetchall()


def create_profile(name: str) -> dict[str, object]:
    cleaned = name.strip()
    if not cleaned:
        raise ValueError("Profile name is required.")
    with get_connection() as conn:
        cursor = conn.execute("INSERT INTO profiles (name) VALUES (?)", (cleaned,))
        profile = conn.execute("SELECT * FROM profiles WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return profile


def update_sync_preferences(
    profile_id: int,
    chesscom_username: str | None = None,
    chesscom_sync_days: int | None = None,
) -> dict[str, object]:
    cleaned_username = chesscom_username.strip().lower() if chesscom_username is not None else None
    days = None
    if chesscom_sync_days is not None:
        days = max(1, min(365, int(chesscom_sync_days)))
    with get_connection() as conn:
        profile = conn.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()
        if not profile:
            raise ValueError(f"Profile {profile_id} was not found.")
        conn.execute(
            """
            UPDATE profiles
            SET
                chesscom_username = COALESCE(?, chesscom_username),
                chesscom_sync_days = COALESCE(?, chesscom_sync_days)
            WHERE id = ?
            """,
            (cleaned_username, days, profile_id),
        )
        return conn.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()


def get_active_profile() -> dict[str, object]:
    with get_connection() as conn:
        row = conn.execute("SELECT value FROM app_settings WHERE key = 'active_profile_id'").fetchone()
        if row:
            profile = conn.execute("SELECT * FROM profiles WHERE id = ?", (row["value"],)).fetchone()
            if profile:
                return profile

        profile = conn.execute("SELECT * FROM profiles ORDER BY id LIMIT 1").fetchone()
        if profile:
            conn.execute(
                """
                INSERT INTO app_settings (key, value)
                VALUES ('active_profile_id', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (str(profile["id"]),),
            )
            return profile

        cursor = conn.execute("INSERT INTO profiles (name) VALUES (?)", (DEFAULT_PROFILE_NAME,))
        conn.execute(
            "INSERT INTO app_settings (key, value) VALUES ('active_profile_id', ?)",
            (str(cursor.lastrowid),),
        )
        return conn.execute("SELECT * FROM profiles WHERE id = ?", (cursor.lastrowid,)).fetchone()


def set_active_profile(profile_id: int) -> dict[str, object]:
    with get_connection() as conn:
        profile = conn.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()
        if not profile:
            raise ValueError(f"Profile {profile_id} was not found.")
        conn.execute(
            """
            INSERT INTO app_settings (key, value)
            VALUES ('active_profile_id', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (str(profile_id),),
        )
    return profile


def resolve_profile_id(profile_id: int | None = None) -> int:
    if profile_id is not None:
        with get_connection() as conn:
            row = conn.execute("SELECT id FROM profiles WHERE id = ?", (profile_id,)).fetchone()
            if not row:
                raise ValueError(f"Profile {profile_id} was not found.")
        return profile_id
    return int(get_active_profile()["id"])
