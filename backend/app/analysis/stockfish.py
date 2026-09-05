from __future__ import annotations

import logging
from contextlib import AbstractContextManager
from types import TracebackType

import chess
import chess.engine

from app.config import settings
from app.models import EngineEvaluation

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
        if self._engine is None:
            raise RuntimeError("StockfishClient must be used as a context manager.")

        board = chess.Board(fen)
        result = self._engine.analyse(board, chess.engine.Limit(depth=depth))
        pov_score = result["score"].pov(chess.WHITE)
        best_move = result.get("pv", [None])[0]

        return EngineEvaluation(
            fen=fen,
            depth=depth,
            best_move=best_move.uci() if best_move else None,
            score_cp=pov_score.score(mate_score=None),
            mate=pov_score.mate(),
        )
