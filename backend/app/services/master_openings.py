from __future__ import annotations

import json
import logging
from threading import Lock
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import chess

from app.config import settings


logger = logging.getLogger(__name__)
_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_cache_lock = Lock()


class MasterExplorerUnavailable(RuntimeError):
    pass


def master_opening_position(fen: str, move_limit: int = 12) -> dict[str, Any]:
    normalized_fen = _normalize_fen(fen)
    normalized_limit = max(1, min(int(move_limit), 20))
    cache_key = f"{normalized_fen}|{normalized_limit}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return {**cached, "cached": True}

    query = urlencode({"fen": normalized_fen, "moves": normalized_limit, "topGames": 0})
    request = Request(
        f"{settings.lichess_explorer_url}?{query}",
        headers=_request_headers(),
    )
    try:
        with urlopen(request, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 401:
            raise MasterExplorerUnavailable(
                "Master data needs Lichess access."
            ) from exc
        logger.warning("Lichess master explorer returned HTTP %s", exc.code)
        raise MasterExplorerUnavailable("Master opening data is temporarily unavailable.") from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        logger.warning("Lichess master explorer request failed: %s", exc)
        raise MasterExplorerUnavailable("Master opening data is temporarily unavailable.") from exc

    result = _normalize_response(payload, normalized_fen)
    with _cache_lock:
        _cache[cache_key] = (time.monotonic(), result)
    return {**result, "cached": False}


def clear_master_opening_cache() -> None:
    with _cache_lock:
        _cache.clear()


def _normalize_fen(fen: str) -> str:
    try:
        return chess.Board(fen).fen()
    except ValueError as exc:
        raise ValueError("Invalid FEN.") from exc


def _request_headers() -> dict[str, str]:
    headers = {
        "Accept": "application/json",
        "User-Agent": "ChessAnalytics/1.0",
    }
    if settings.lichess_api_token:
        headers["Authorization"] = f"Bearer {settings.lichess_api_token}"
    return headers


def _get_cached(cache_key: str) -> dict[str, Any] | None:
    with _cache_lock:
        cached = _cache.get(cache_key)
        if cached is None:
            return None
        created_at, payload = cached
        if time.monotonic() - created_at <= settings.opening_explorer_cache_seconds:
            return payload
        _cache.pop(cache_key, None)
    return None


def _normalize_response(payload: dict[str, Any], fen: str) -> dict[str, Any]:
    moves = []
    for move in payload.get("moves") or []:
        white = max(0, int(move.get("white") or 0))
        draws = max(0, int(move.get("draws") or 0))
        black = max(0, int(move.get("black") or 0))
        moves.append(
            {
                "uci": str(move.get("uci") or ""),
                "san": str(move.get("san") or move.get("uci") or ""),
                "white": white,
                "draws": draws,
                "black": black,
                "games": white + draws + black,
                "average_rating": move.get("averageRating"),
            }
        )
    moves.sort(key=lambda item: int(item["games"]), reverse=True)
    opening = payload.get("opening") if isinstance(payload.get("opening"), dict) else None
    return {
        "status": "ready",
        "source": "masters",
        "fen": fen,
        "white": max(0, int(payload.get("white") or 0)),
        "draws": max(0, int(payload.get("draws") or 0)),
        "black": max(0, int(payload.get("black") or 0)),
        "opening": opening,
        "moves": moves,
    }
