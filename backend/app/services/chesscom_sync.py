from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
import io
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import chess.pgn

from app.db import get_connection
from app.services.imports import import_pgn_text

logger = logging.getLogger(__name__)

BASE_URL = "https://api.chess.com/pub/player"
USER_AGENT = "ChessAnalyticsLocal/1.0 (+https://api.chess.com/pub)"


@dataclass(frozen=True)
class SyncOptions:
    username: str
    limit: int | None = None
    days: int | None = None
    force: bool = False
    profile_id: int | None = None


def sync_chesscom_archives(options: SyncOptions) -> dict[str, object]:
    username = options.username.strip().lower()
    if not username:
        raise ValueError("Chess.com username is required.")
    from app.services.profiles import resolve_profile_id

    profile_id = resolve_profile_id(options.profile_id)
    sync_days = max(1, min(365, int(options.days or 7)))
    _save_profile_sync_preferences(profile_id, username, sync_days)

    archives = _fetch_archive_urls(username)
    use_day_filter = options.limit is None
    if options.limit:
        archives = archives[-options.limit :]
    else:
        archive_count = max(1, (sync_days + 30) // 31)
        archives = archives[-archive_count:]
    since = datetime.now(timezone.utc) - timedelta(days=sync_days) if use_day_filter else None

    results = []
    total_imported = 0
    total_duplicates = 0
    total_errors = 0

    for archive_url in archives:
        if not options.force and _archive_complete(profile_id, username, archive_url):
            results.append(
                {
                    "archive_url": archive_url,
                    "status": "skipped",
                    "imported": 0,
                    "duplicates": 0,
                    "errors": [],
                }
            )
            continue

        try:
            pgn = _fetch_pgn_archive(archive_url)
            if since is not None:
                pgn = _filter_pgn_since(pgn, since)
            result = import_pgn_text(pgn, profile_id)
            status = "complete"
            errors = result["errors"]
        except Exception as exc:
            logger.exception("Chess.com sync failed for %s", archive_url)
            result = {"imported": 0, "duplicates": 0, "errors": [str(exc)]}
            status = "failed"
            errors = result["errors"]

        imported = int(result["imported"])
        duplicates = int(result["duplicates"])
        total_imported += imported
        total_duplicates += duplicates
        total_errors += len(errors)
        _record_archive_sync(profile_id, username, archive_url, status, imported, duplicates, errors)
        results.append(
            {
                "archive_url": archive_url,
                "status": status,
                "imported": imported,
                "duplicates": duplicates,
                "errors": errors,
            }
        )

    return {
        "username": username,
        "profile_id": profile_id,
        "days": sync_days,
        "archives": len(archives),
        "imported": total_imported,
        "duplicates": total_duplicates,
        "errors": total_errors,
        "results": results,
    }


def get_chesscom_syncs(username: str | None = None, profile_id: int | None = None) -> list[dict[str, object]]:
    from app.services.profiles import resolve_profile_id

    selected_profile_id = resolve_profile_id(profile_id)
    with get_connection() as conn:
        if username:
            return conn.execute(
                """
                SELECT * FROM chesscom_syncs
                WHERE username = ? AND profile_id = ?
                ORDER BY synced_at DESC
                """,
                (username.strip().lower(), selected_profile_id),
            ).fetchall()
        return conn.execute(
            """
            SELECT * FROM chesscom_syncs
            WHERE profile_id = ?
            ORDER BY synced_at DESC LIMIT 50
            """,
            (selected_profile_id,),
        ).fetchall()


def _fetch_archive_urls(username: str) -> list[str]:
    url = f"{BASE_URL}/{username}/games/archives"
    data = _get_json(url)
    archives = data.get("archives")
    if not isinstance(archives, list):
        raise ValueError("Chess.com archive response did not include archives.")
    return [str(archive) for archive in archives]


def _fetch_pgn_archive(archive_url: str) -> str:
    return _get_text(f"{archive_url}/pgn")


def _filter_pgn_since(pgn_text: str, since: datetime) -> str:
    stream = io.StringIO(pgn_text)
    exported: list[str] = []
    while True:
        game = chess.pgn.read_game(stream)
        if game is None:
            break
        played_at = _game_datetime(game)
        if played_at is None or played_at >= since:
            exporter = chess.pgn.StringExporter(headers=True, variations=False, comments=True)
            exported.append(game.accept(exporter))
    return "\n\n".join(exported)


def _game_datetime(game: chess.pgn.Game) -> datetime | None:
    date_text = game.headers.get("UTCDate") or game.headers.get("Date")
    if not date_text or "?" in date_text:
        return None
    time_text = game.headers.get("UTCTime") or "00:00:00"
    try:
        return datetime.strptime(f"{date_text} {time_text}", "%Y.%m.%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        try:
            return datetime.strptime(date_text, "%Y.%m.%d").replace(tzinfo=timezone.utc)
        except ValueError:
            return None


def _get_json(url: str) -> dict[str, object]:
    text = _get_text(url)
    return json.loads(text)


def _get_text(url: str) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json,text/plain"})
    try:
        with urlopen(request, timeout=30) as response:
            body = response.read()
    except HTTPError as exc:
        raise ValueError(f"Chess.com returned HTTP {exc.code} for {url}") from exc
    except URLError as exc:
        raise ValueError(f"Could not reach Chess.com: {exc.reason}") from exc
    return body.decode("utf-8", errors="replace")


def _archive_complete(profile_id: int, username: str, archive_url: str) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT status FROM chesscom_syncs
            WHERE profile_id = ? AND username = ? AND archive_url = ?
            ORDER BY synced_at DESC
            LIMIT 1
            """,
            (profile_id, username, archive_url),
        ).fetchone()
    return bool(row and row["status"] == "complete")


def _record_archive_sync(
    profile_id: int,
    username: str,
    archive_url: str,
    status: str,
    imported: int,
    duplicates: int,
    errors: list[str],
) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO chesscom_syncs (
                profile_id, username, archive_url, status, imported, duplicates, errors, synced_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(profile_id, username, archive_url) DO UPDATE SET
                status = excluded.status,
                imported = excluded.imported,
                duplicates = excluded.duplicates,
                errors = excluded.errors,
                synced_at = CURRENT_TIMESTAMP
            """,
            (profile_id, username, archive_url, status, imported, duplicates, json.dumps(errors)),
        )


def _save_profile_sync_preferences(profile_id: int, username: str, days: int) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE profiles
            SET chesscom_username = ?, chesscom_sync_days = ?
            WHERE id = ?
            """,
            (username, days, profile_id),
        )
