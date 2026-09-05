from __future__ import annotations

import hashlib
import io
import logging
import re
from typing import Any

import chess
import chess.pgn

from app.models import ParsedGame, ParsedMove
from app.pgn.openings import detect_opening
from app.pgn.time_control import classify_time_control

logger = logging.getLogger(__name__)

CLOCK_RE = re.compile(r"\[%clk\s+([0-9:.]+)\]")


def parse_pgn_text(pgn_text: str) -> tuple[list[ParsedGame], list[str]]:
    games: list[ParsedGame] = []
    errors: list[str] = []
    stream = io.StringIO(pgn_text)
    index = 0

    while True:
        index += 1
        try:
            game = chess.pgn.read_game(stream)
        except Exception as exc:
            message = f"Game {index}: malformed PGN ({exc})"
            logger.warning(message)
            errors.append(message)
            continue

        if game is None:
            break

        if game.errors:
            errors.extend(f"Game {index}: {error}" for error in game.errors)

        try:
            games.append(_parse_game(game))
        except Exception as exc:
            message = f"Game {index}: could not import ({exc})"
            logger.exception(message)
            errors.append(message)

    return games, errors


def _parse_game(game: chess.pgn.Game) -> ParsedGame:
    headers = game.headers
    board = game.board()
    parsed_moves: list[ParsedMove] = []
    node = game

    ply = 0
    while node.variations:
        ply += 1
        next_node = node.variation(0)
        move = next_node.move
        fen_before = board.fen()
        san = board.san(move)
        color = "white" if board.turn == chess.WHITE else "black"
        board.push(move)
        parsed_moves.append(
            ParsedMove(
                ply=ply,
                move_number=(ply + 1) // 2,
                color=color,
                san=san,
                uci=move.uci(),
                fen_before=fen_before,
                fen_after=board.fen(),
                phase=_phase_for_board(board, ply),
                clock_seconds=_parse_clock_seconds(next_node.comment),
            )
        )
        node = next_node

    raw_pgn = _game_to_text(game)
    fingerprint = _fingerprint(headers, parsed_moves)
    white = _none_if_unknown(headers.get("White"))
    black = _none_if_unknown(headers.get("Black"))

    time_control = _none_if_unknown(headers.get("TimeControl"))
    opening = detect_opening(
        parsed_moves,
        _none_if_unknown(headers.get("Opening")),
        _none_if_unknown(headers.get("ECOUrl")),
    )

    return ParsedGame(
        fingerprint=fingerprint,
        event=_none_if_unknown(headers.get("Event")),
        site=_none_if_unknown(headers.get("Site")),
        played_at=_parse_date(headers),
        white=white,
        black=black,
        player_color=_infer_player_color(headers, white, black),
        result=_none_if_unknown(headers.get("Result")),
        eco=_none_if_unknown(headers.get("ECO")),
        opening=opening,
        time_control=time_control,
        time_class=classify_time_control(time_control),
        white_elo=_parse_int(headers.get("WhiteElo")),
        black_elo=_parse_int(headers.get("BlackElo")),
        raw_pgn=raw_pgn,
        moves=parsed_moves,
    )


def _game_to_text(game: chess.pgn.Game) -> str:
    exporter = chess.pgn.StringExporter(headers=True, variations=False, comments=False)
    return game.accept(exporter)


def _fingerprint(headers: Any, moves: list[ParsedMove]) -> str:
    key = "|".join(
        [
            headers.get("UTCDate", headers.get("Date", "")),
            headers.get("White", ""),
            headers.get("Black", ""),
            headers.get("Result", ""),
            " ".join(move.uci for move in moves),
        ]
    )
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _parse_date(headers: Any) -> str | None:
    date = headers.get("UTCDate") or headers.get("Date")
    if not date or date == "????.??.??":
        return None
    time = headers.get("UTCTime")
    if time and time != "??:??:??":
        return f"{date.replace('.', '-') }T{time}Z"
    return date.replace(".", "-")


def _infer_player_color(headers: Any, white: str | None, black: str | None) -> str | None:
    username = headers.get("CurrentPositionUser") or headers.get("User")
    if not username:
        return None
    if white and username.lower() == white.lower():
        return "white"
    if black and username.lower() == black.lower():
        return "black"
    return None


def _phase_for_board(board: chess.Board, ply: int) -> str:
    if ply <= 20:
        return "opening"
    material = sum(
        len(board.pieces(piece_type, chess.WHITE)) + len(board.pieces(piece_type, chess.BLACK))
        for piece_type in [chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT]
    )
    if material <= 6 or board.fullmove_number >= 40:
        return "endgame"
    return "middlegame"


def _parse_int(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _parse_clock_seconds(comment: str | None) -> float | None:
    if not comment:
        return None
    match = CLOCK_RE.search(comment)
    if not match:
        return None
    parts = match.group(1).split(":")
    try:
        if len(parts) == 3:
            hours, minutes, seconds = parts
            return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
        if len(parts) == 2:
            minutes, seconds = parts
            return int(minutes) * 60 + float(seconds)
        if len(parts) == 1:
            return float(parts[0])
    except ValueError:
        return None
    return None


def _none_if_unknown(value: str | None) -> str | None:
    if not value or value == "?":
        return None
    return value
