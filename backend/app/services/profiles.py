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
