from __future__ import annotations

import logging
from contextlib import AbstractContextManager
from types import TracebackType

import chess
import chess.engine

from app.config import settings
from app.models import EngineCandidate, EngineEvaluation, PositionEngineAnalysis

logger = logging.getLogger(__name__)


class StockfishUnavailable(RuntimeError):
    pass


class StockfishClient(AbstractContextManager["StockfishClient"]):
    def __init__(self, path: str | None = None) -> None:
        self.path = path or settings.stockfish_path
        self._engine: chess.engine.SimpleEngine | None = None

    def __enter__(self) -> "StockfishClient":
        try:
            self._engine = chess.engine.SimpleEngine.popen_uci(self.path)
        except FileNotFoundError as exc:
            raise StockfishUnavailable(
                f"Stockfish was not found at '{self.path}'. Set STOCKFISH_PATH."
            ) from exc
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._engine:
            self._engine.quit()

    def evaluate(self, fen: str, depth: int) -> EngineEvaluation:
        analysis = self.analyze_position(fen, depth, multipv=1)
        return analysis.evaluation

    def analyze_position(self, fen: str, depth: int, multipv: int = 3) -> PositionEngineAnalysis:
        if self._engine is None:
            raise RuntimeError("StockfishClient must be used as a context manager.")

        board = chess.Board(fen)
        legal_count = board.legal_moves.count()
        if legal_count:
            requested_lines = max(1, min(multipv, legal_count))
            result = self._engine.analyse(
                board,
                chess.engine.Limit(depth=depth),
                multipv=requested_lines,
            )
            infos = result if isinstance(result, list) else [result]
            candidates = [_candidate_from_info(board, info, rank) for rank, info in enumerate(infos, start=1)]
            score_info = infos[0]
        else:
            score_info = self._engine.analyse(board, chess.engine.Limit(depth=depth))
            candidates = []
        score = score_info["score"].pov(chess.WHITE)
        best = candidates[0] if candidates else None

        evaluation = EngineEvaluation(
            fen=fen,
            depth=depth,
            best_move=best.uci if best else None,
            score_cp=score.score(mate_score=None),
            mate=score.mate(),
        )
        return PositionEngineAnalysis(evaluation=evaluation, candidates=candidates)


def _candidate_from_info(board: chess.Board, info: dict[str, object], rank: int) -> EngineCandidate:
    score = info["score"].pov(chess.WHITE)  # type: ignore[index, union-attr]
    pv = list(info.get("pv", []))  # type: ignore[union-attr]
    move = pv[0] if pv else None
    return EngineCandidate(
        rank=rank,
        uci=move.uci() if move else "",
        san=board.san(move) if move else "",
        score_cp=score.score(mate_score=None),
        mate=score.mate(),
        pv_uci=[pv_move.uci() for pv_move in pv],
        pv_san=_pv_to_san(board, pv),
    )


def _pv_to_san(board: chess.Board, pv: list[chess.Move]) -> list[str]:
    replay = board.copy(stack=False)
    sans: list[str] = []
    for move in pv:
        if move not in replay.legal_moves:
            break
        sans.append(replay.san(move))
        replay.push(move)
    return sans
