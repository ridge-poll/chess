from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable

import chess

from app.analysis.stockfish import StockfishClient
from app.db import get_connection
from app.models import EngineCandidate, EngineEvaluation, PositionEngineAnalysis


DEFAULT_MULTIPV = 3
MAX_MULTIPV = 5
PROGRESSIVE_DEPTHS = (6, 10)


def analyze_position(
    fen: str,
    depth: int,
    multipv: int = DEFAULT_MULTIPV,
    engine: StockfishClient | None = None,
) -> dict[str, object]:
    analysis = get_or_create_position_analysis(fen, depth, multipv, engine)
    return serialize_position_analysis(analysis, multipv)


async def progressive_position_results(
    fen: str,
    target_depth: int,
    multipv: int = DEFAULT_MULTIPV,
    *,
    is_cancelled: Callable[[], Awaitable[bool]] | None = None,
    analyzer: Callable[[str, int, int], dict[str, object]] = analyze_position,
) -> AsyncIterator[dict[str, object]]:
    """Yield cached and increasingly deep snapshots for one position."""
    requested_lines = _normalize_multipv_for_fen(fen, multipv)
    target = max(1, int(target_depth))
    cached = _strongest_cached_position_analysis(fen, target, requested_lines)
    completed_depth = 0
    if cached:
        completed_depth = cached.evaluation.depth
        yield _progressive_snapshot(
            serialize_position_analysis(cached, requested_lines),
            target,
            cached=True,
        )
        if completed_depth >= target:
            return

    stages = sorted({depth for depth in (*PROGRESSIVE_DEPTHS, target) if completed_depth < depth <= target})
    for depth in stages:
        if is_cancelled and await is_cancelled():
            return
        result = await asyncio.to_thread(analyzer, fen, depth, requested_lines)
        if is_cancelled and await is_cancelled():
            return
        yield _progressive_snapshot(result, target, cached=False)


def _progressive_snapshot(
    result: dict[str, object],
    target_depth: int,
    *,
    cached: bool,
) -> dict[str, object]:
    depth = int(result.get("depth") or 0)
    return {
        **result,
        "target_depth": target_depth,
        "complete": depth >= target_depth,
        "cached": cached,
    }


def get_or_create_position_analysis(
    fen: str,
    depth: int,
    multipv: int = DEFAULT_MULTIPV,
    engine: StockfishClient | None = None,
) -> PositionEngineAnalysis:
    requested_lines = _normalize_multipv_for_fen(fen, multipv)
    cached = _cached_position_analysis(fen, depth, requested_lines)
    if cached:
        return cached

    if engine is None:
        with StockfishClient() as managed_engine:
            analysis = managed_engine.analyze_position(fen, depth, requested_lines)
    else:
        analysis = engine.analyze_position(fen, depth, requested_lines)
    _store_position_analysis(analysis)
    return analysis


def serialize_position_analysis(analysis: PositionEngineAnalysis, multipv: int | None = None) -> dict[str, object]:
    candidates = analysis.candidates
    if multipv is not None:
        candidates = candidates[: _normalize_multipv(multipv)]
    return {
        "status": "ok",
        "fen": analysis.evaluation.fen,
        "depth": analysis.evaluation.depth,
        "best_move": analysis.evaluation.best_move,
        "score_cp": analysis.evaluation.score_cp,
        "mate": analysis.evaluation.mate,
        "evaluation_perspective": "white",
        "threat_captures": opponent_capture_threats(analysis.evaluation.fen),
        "candidates": [
            {
                "rank": candidate.rank,
                "uci": candidate.uci,
                "san": candidate.san,
                "score_cp": candidate.score_cp,
                "mate": candidate.mate,
                "pv_uci": candidate.pv_uci,
                "pv_san": candidate.pv_san,
            }
            for candidate in candidates
        ],
    }


def opponent_capture_threats(fen: str, limit: int = 3) -> list[str]:
    board = chess.Board(fen)
    board.turn = not board.turn
    values = {
        chess.PAWN: 1,
        chess.KNIGHT: 3,
        chess.BISHOP: 3,
        chess.ROOK: 5,
        chess.QUEEN: 9,
        chess.KING: 100,
    }
    captures: list[tuple[int, str]] = []
    for move in board.generate_legal_captures():
        captured = board.piece_at(move.to_square)
        attacker = board.piece_at(move.from_square)
        if captured is None or attacker is None or captured.color == attacker.color:
            continue
        priority = values[captured.piece_type] * 10 - values[attacker.piece_type]
        captures.append((priority, move.uci()))
    captures.sort(key=lambda item: (-item[0], item[1]))
    return [uci for _, uci in captures[: max(0, limit)]]


def _cached_position_analysis(fen: str, depth: int, multipv: int) -> PositionEngineAnalysis | None:
    with get_connection() as conn:
        evaluation_row = conn.execute(
            "SELECT * FROM position_evaluations WHERE fen = ? AND depth = ?",
            (fen, depth),
        ).fetchone()
        if not evaluation_row:
            return None
        candidate_rows = conn.execute(
            """
            SELECT * FROM position_evaluation_candidates
            WHERE evaluation_id = ?
            ORDER BY rank
            """,
            (evaluation_row["id"],),
        ).fetchall()
        if len(candidate_rows) < multipv:
            return None

    evaluation = EngineEvaluation(
        fen=fen,
        depth=depth,
        best_move=evaluation_row["best_move"],
        score_cp=evaluation_row["score_cp"],
        mate=evaluation_row["mate"],
    )
    candidates = [
        EngineCandidate(
            rank=int(row["rank"]),
            uci=str(row["move_uci"]),
            san=str(row["move_san"]),
            score_cp=row["score_cp"],
            mate=row["mate"],
            pv_uci=json.loads(str(row["pv_uci"] or "[]")),
            pv_san=json.loads(str(row["pv_san"] or "[]")),
        )
        for row in candidate_rows
    ]
    return PositionEngineAnalysis(evaluation=evaluation, candidates=candidates)


def _strongest_cached_position_analysis(
    fen: str,
    maximum_depth: int,
    multipv: int,
) -> PositionEngineAnalysis | None:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT depth FROM position_evaluations
            WHERE fen = ? AND depth <= ?
            ORDER BY depth DESC
            """,
            (fen, maximum_depth),
        ).fetchall()
    for row in rows:
        cached = _cached_position_analysis(fen, int(row["depth"]), multipv)
        if cached:
            return cached
    return None


def _store_position_analysis(analysis: PositionEngineAnalysis) -> None:
    evaluation = analysis.evaluation
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO position_evaluations
            (fen, depth, best_move, score_cp, mate)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(fen, depth) DO UPDATE SET
                best_move = excluded.best_move,
                score_cp = excluded.score_cp,
                mate = excluded.mate
            """,
            (evaluation.fen, evaluation.depth, evaluation.best_move, evaluation.score_cp, evaluation.mate),
        )
        row = conn.execute(
            "SELECT id FROM position_evaluations WHERE fen = ? AND depth = ?",
            (evaluation.fen, evaluation.depth),
        ).fetchone()
        evaluation_id = int(row["id"])
        conn.execute("DELETE FROM position_evaluation_candidates WHERE evaluation_id = ?", (evaluation_id,))
        for candidate in analysis.candidates:
            conn.execute(
                """
                INSERT INTO position_evaluation_candidates (
                    evaluation_id, rank, move_uci, move_san, score_cp, mate, pv_uci, pv_san
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    evaluation_id,
                    candidate.rank,
                    candidate.uci,
                    candidate.san,
                    candidate.score_cp,
                    candidate.mate,
                    json.dumps(candidate.pv_uci),
                    json.dumps(candidate.pv_san),
                ),
            )


def _normalize_multipv_for_fen(fen: str, multipv: int) -> int:
    legal_count = chess.Board(fen).legal_moves.count()
    if legal_count == 0:
        return 0
    return min(_normalize_multipv(multipv), legal_count)


def _normalize_multipv(multipv: int) -> int:
    return max(1, min(MAX_MULTIPV, int(multipv)))
