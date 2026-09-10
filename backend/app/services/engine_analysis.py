from __future__ import annotations

import json

import chess

from app.analysis.stockfish import StockfishClient
from app.db import get_connection
from app.models import EngineCandidate, EngineEvaluation, PositionEngineAnalysis


DEFAULT_MULTIPV = 3
MAX_MULTIPV = 5


def analyze_position(
    fen: str,
    depth: int,
    multipv: int = DEFAULT_MULTIPV,
    engine: StockfishClient | None = None,
) -> dict[str, object]:
    analysis = get_or_create_position_analysis(fen, depth, multipv, engine)
    return serialize_position_analysis(analysis, multipv)


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
