from pathlib import Path
import asyncio

import app.config as config
import app.db as db
from app.api.analysis import PositionAnalysisRequest, position_analysis
from app.models import EngineCandidate, EngineEvaluation, PositionEngineAnalysis
from app.services.engine_analysis import analyze_position, get_or_create_position_analysis


class FakeStockfish:
    def __init__(self) -> None:
        self.calls = 0

    def analyze_position(self, fen: str, depth: int, multipv: int = 3) -> PositionEngineAnalysis:
        self.calls += 1
        candidates = [
            EngineCandidate(
                rank=1,
                uci="e2e4",
                san="e4",
                score_cp=34,
                mate=None,
                pv_uci=["e2e4", "e7e5"],
                pv_san=["e4", "e5"],
            ),
            EngineCandidate(
                rank=2,
                uci="d2d4",
                san="d4",
                score_cp=21,
                mate=None,
                pv_uci=["d2d4", "d7d5"],
                pv_san=["d4", "d5"],
            ),
            EngineCandidate(
                rank=3,
                uci="g1f3",
                san="Nf3",
                score_cp=18,
                mate=None,
                pv_uci=["g1f3", "d7d5"],
                pv_san=["Nf3", "d5"],
            ),
        ][:multipv]
        return PositionEngineAnalysis(
            evaluation=EngineEvaluation(
                fen=fen,
                depth=depth,
                best_move=candidates[0].uci,
                score_cp=candidates[0].score_cp,
                mate=None,
            ),
            candidates=candidates,
        )


def _setup_db(tmp_path: Path, monkeypatch) -> Path:
    database_path = tmp_path / "test.sqlite3"
    monkeypatch.setattr(db, "settings", config.Settings(database_path=database_path))
    db.init_db(database_path)
    return database_path


def test_position_analysis_stores_multipv_candidates(tmp_path: Path, monkeypatch) -> None:
    database_path = _setup_db(tmp_path, monkeypatch)
    engine = FakeStockfish()

    result = get_or_create_position_analysis(
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        depth=8,
        multipv=3,
        engine=engine,
    )

    assert result.evaluation.best_move == "e2e4"
    assert [candidate.san for candidate in result.candidates] == ["e4", "d4", "Nf3"]
    with db.get_connection(database_path) as conn:
        evaluation_count = conn.execute("SELECT COUNT(*) AS count FROM position_evaluations").fetchone()
        candidate_count = conn.execute("SELECT COUNT(*) AS count FROM position_evaluation_candidates").fetchone()
    assert evaluation_count["count"] == 1
    assert candidate_count["count"] == 3


def test_position_analysis_reuses_candidate_cache(tmp_path: Path, monkeypatch) -> None:
    _setup_db(tmp_path, monkeypatch)
    engine = FakeStockfish()
    fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

    get_or_create_position_analysis(fen, depth=8, multipv=3, engine=engine)
    cached = get_or_create_position_analysis(fen, depth=8, multipv=2, engine=engine)

    assert engine.calls == 1
    assert [candidate.uci for candidate in cached.candidates[:2]] == ["e2e4", "d2d4"]


def test_position_analysis_response_documents_white_perspective(tmp_path: Path, monkeypatch) -> None:
    _setup_db(tmp_path, monkeypatch)

    response = analyze_position(
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        depth=8,
        multipv=2,
        engine=FakeStockfish(),
    )

    assert response["status"] == "ok"
    assert response["evaluation_perspective"] == "white"
    assert response["best_move"] == "e2e4"
    assert len(response["candidates"]) == 2
    assert response["candidates"][0]["pv_san"] == ["e4", "e5"]


def test_position_analysis_api_returns_cached_payload(tmp_path: Path, monkeypatch) -> None:
    database_path = _setup_db(tmp_path, monkeypatch)
    fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    engine = FakeStockfish()
    get_or_create_position_analysis(fen, depth=8, multipv=3, engine=engine)

    monkeypatch.setattr(db, "settings", config.Settings(database_path=database_path))
    payload = asyncio.run(position_analysis(PositionAnalysisRequest(fen=fen, depth=8, multipv=2)))

    assert payload["best_move"] == "e2e4"
    assert [candidate["san"] for candidate in payload["candidates"]] == ["e4", "d4"]
