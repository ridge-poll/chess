from __future__ import annotations

import logging

import chess

from app.analysis.metrics import classify_loss, move_loss
from app.analysis.stockfish import StockfishClient
from app.db import get_connection
from app.models import EngineEvaluation
from app.services.engine_analysis import get_or_create_position_analysis
from app.services.profiles import resolve_profile_id

logger = logging.getLogger(__name__)


def analyze_game(game_id: int, depth: int) -> dict[str, object]:
    with get_connection() as conn:
        game = conn.execute("SELECT * FROM games WHERE id = ?", (game_id,)).fetchone()
        if not game:
            raise ValueError(f"Game {game_id} was not found.")

        total_plies = int(game["ply_count"])
        analyzed_plies = _count_analyzed_plies(conn, game_id, depth)
        if analyzed_plies >= total_plies:
            _upsert_job(conn, game_id, depth, "complete", total_plies, None, analyzed_plies)
            return {
                "game_id": game_id,
                "depth": depth,
                "status": "complete",
                "analyzed_plies": analyzed_plies,
                "skipped": True,
            }

        _upsert_job(conn, game_id, depth, "running", total_plies, None, analyzed_plies)
        moves = conn.execute(
            """
            SELECT * FROM moves
            WHERE game_id = ? AND ply NOT IN (
                SELECT ply FROM move_analyses WHERE game_id = ? AND depth = ?
            )
            ORDER BY ply
            """,
            (game_id, game_id, depth),
        ).fetchall()

    try:
        with StockfishClient() as engine:
            for move in moves:
                before = _get_or_create_evaluation(move["fen_before"], depth, engine)
                after = _get_or_create_evaluation(move["fen_after"], depth, engine)
                loss = move_loss(
                    before.score_cp,
                    after.score_cp,
                    before.mate,
                    after.mate,
                    str(move["color"]),
                    chess.Board(str(move["fen_after"])).is_checkmate(),
                )
                classification = classify_loss(loss)

                with get_connection() as conn:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO move_analyses (
                            game_id, ply, depth, played_uci, best_uci,
                            eval_before_cp, eval_after_cp, mate_before, mate_after,
                            centipawn_loss, classification
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            game_id,
                            move["ply"],
                            depth,
                            move["uci"],
                            before.best_move,
                            before.score_cp,
                            after.score_cp,
                            before.mate,
                            after.mate,
                            loss,
                            classification,
                        ),
                    )
                    analyzed_plies = _count_analyzed_plies(conn, game_id, depth)
                    _upsert_job(conn, game_id, depth, "running", total_plies, None, analyzed_plies)

        with get_connection() as conn:
            analyzed_plies = _count_analyzed_plies(conn, game_id, depth)
            status = "complete" if analyzed_plies >= total_plies else "partial"
            _upsert_job(conn, game_id, depth, status, total_plies, None, analyzed_plies)
        return {"game_id": game_id, "depth": depth, "status": status, "analyzed_plies": analyzed_plies}
    except Exception as exc:
        logger.exception("Analysis failed for game %s", game_id)
        with get_connection() as conn:
            analyzed_plies = _count_analyzed_plies(conn, game_id, depth)
            _upsert_job(conn, game_id, depth, "failed", total_plies, str(exc), analyzed_plies)
        raise


def analyze_all(depth: int, profile_id: int | None = None) -> dict[str, object]:
    selected_profile_id = resolve_profile_id(profile_id)
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id FROM games WHERE profile_id = ? ORDER BY played_at DESC, id DESC",
            (selected_profile_id,),
        ).fetchall()

    results = []
    for row in rows:
        results.append(analyze_game(int(row["id"]), depth))
    return {"analyzed": len(results), "profile_id": selected_profile_id, "results": results}


def get_analysis_jobs(profile_id: int | None = None) -> list[dict[str, object]]:
    selected_profile_id = resolve_profile_id(profile_id)
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT
                j.*,
                g.profile_id,
                g.white,
                g.black,
                g.played_at,
                g.opening,
                CASE
                    WHEN j.total_plies = 0 THEN 0
                    ELSE ROUND((j.analyzed_plies * 100.0) / j.total_plies, 1)
                END AS progress
            FROM analysis_jobs j
            JOIN games g ON g.id = j.game_id
            WHERE g.profile_id = ?
            ORDER BY j.updated_at DESC, j.id DESC
            """,
            (selected_profile_id,),
        ).fetchall()


def mark_interrupted_jobs_failed() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE analysis_jobs
            SET status = 'failed',
                error = 'Analysis was interrupted before completion.',
                updated_at = CURRENT_TIMESTAMP
            WHERE status IN ('running', 'queued')
            """
        )


def prepare_queued_job(game_id: int, depth: int, profile_id: int | None = None) -> dict[str, object]:
    selected_profile_id = resolve_profile_id(profile_id)
    with get_connection() as conn:
        game = conn.execute(
            "SELECT * FROM games WHERE id = ? AND profile_id = ?",
            (game_id, selected_profile_id),
        ).fetchone()
        if not game:
            raise ValueError(f"Game {game_id} was not found.")

        total_plies = int(game["ply_count"])
        analyzed_plies = _count_analyzed_plies(conn, game_id, depth)
        existing = conn.execute(
            "SELECT * FROM analysis_jobs WHERE game_id = ? AND depth = ?",
            (game_id, depth),
        ).fetchone()

        if analyzed_plies >= total_plies:
            _upsert_job(conn, game_id, depth, "complete", total_plies, None, analyzed_plies)
            status = "complete"
        elif existing and existing["status"] in {"queued", "running"}:
            status = str(existing["status"])
        else:
            _upsert_job(conn, game_id, depth, "queued", total_plies, None, analyzed_plies)
            status = "queued"

    return {
        "game_id": game_id,
        "profile_id": selected_profile_id,
        "depth": depth,
        "status": status,
        "analyzed_plies": analyzed_plies,
        "total_plies": total_plies,
    }


def _get_or_create_evaluation(fen: str, depth: int, engine: StockfishClient) -> EngineEvaluation:
    return get_or_create_position_analysis(fen, depth, engine=engine).evaluation


def _upsert_job(
    conn,
    game_id: int,
    depth: int,
    status: str,
    total_plies: int,
    error: str | None,
    analyzed_plies: int = 0,
) -> None:
    conn.execute(
        """
        INSERT INTO analysis_jobs (game_id, depth, status, analyzed_plies, total_plies, error)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(game_id, depth) DO UPDATE SET
            status = excluded.status,
            analyzed_plies = excluded.analyzed_plies,
            total_plies = excluded.total_plies,
            error = excluded.error,
            updated_at = CURRENT_TIMESTAMP
        """,
        (game_id, depth, status, analyzed_plies, total_plies, error),
    )


def _count_analyzed_plies(conn, game_id: int, depth: int) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS count FROM move_analyses WHERE game_id = ? AND depth = ?",
        (game_id, depth),
    ).fetchone()
    return int(row["count"])
