from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedMove:
    ply: int
    move_number: int
    color: str
    san: str
    uci: str
    fen_before: str
    fen_after: str
    phase: str
    clock_seconds: float | None = None


@dataclass(frozen=True)
class ParsedGame:
    fingerprint: str
    event: str | None
    site: str | None
    played_at: str | None
    white: str | None
    black: str | None
    player_color: str | None
    result: str | None
    eco: str | None
    opening: str | None
    time_control: str | None
    time_class: str | None
    white_elo: int | None
    black_elo: int | None
    raw_pgn: str
    moves: list[ParsedMove]


@dataclass(frozen=True)
class EngineEvaluation:
    fen: str
    depth: int
    best_move: str | None
    score_cp: int | None
    mate: int | None
