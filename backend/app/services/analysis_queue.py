from __future__ import annotations

import logging
import queue
import threading
from dataclasses import dataclass

from app.config import settings
from app.db import get_connection
from app.services.analysis_jobs import analyze_game, get_analysis_jobs, prepare_queued_job
from app.services.profiles import resolve_profile_id

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AnalysisTask:
    game_id: int
    depth: int


class AnalysisQueue:
    def __init__(self) -> None:
        self._queue: queue.Queue[AnalysisTask] = queue.Queue()
        self._queued_keys: set[tuple[int, int]] = set()
        self._lock = threading.Lock()
        self._worker: threading.Thread | None = None

    def enqueue_game(self, game_id: int, depth: int | None = None, profile_id: int | None = None) -> dict[str, object]:
        selected_depth = depth or settings.default_depth
        selected_profile_id = resolve_profile_id(profile_id)
        job = prepare_queued_job(game_id, selected_depth, selected_profile_id)
        if job["status"] != "queued":
            return {**job, "enqueued": False}

        key = (game_id, selected_depth)
        with self._lock:
            if key not in self._queued_keys:
                self._queue.put(AnalysisTask(game_id=game_id, depth=selected_depth))
                self._queued_keys.add(key)
            self._ensure_worker()
        return {**job, "enqueued": True}

    def enqueue_all(self, depth: int | None = None, profile_id: int | None = None) -> dict[str, object]:
        selected_depth = depth or settings.default_depth
        selected_profile_id = resolve_profile_id(profile_id)
        with get_connection() as conn:
            games = conn.execute(
                "SELECT id FROM games WHERE profile_id = ? ORDER BY played_at DESC, id DESC",
                (selected_profile_id,),
            ).fetchall()

        jobs = [self.enqueue_game(int(game["id"]), selected_depth, selected_profile_id) for game in games]
        return {
            "depth": selected_depth,
            "profile_id": selected_profile_id,
            "requested": len(jobs),
            "enqueued": sum(1 for job in jobs if job["enqueued"]),
            "jobs": jobs,
        }

    def status(self, profile_id: int | None = None) -> dict[str, object]:
        selected_profile_id = resolve_profile_id(profile_id)
        with self._lock:
            worker_alive = bool(self._worker and self._worker.is_alive())
            queued = self._queue.qsize()
        return {
            "worker_alive": worker_alive,
            "queued": queued,
            "profile_id": selected_profile_id,
            "jobs": get_analysis_jobs(selected_profile_id),
        }

    def _ensure_worker(self) -> None:
        if self._worker and self._worker.is_alive():
            return
        self._worker = threading.Thread(target=self._run, name="analysis-worker", daemon=True)
        self._worker.start()

    def _run(self) -> None:
        while True:
            try:
                task = self._queue.get(timeout=1.0)
            except queue.Empty:
                with self._lock:
                    if self._queue.empty():
                        self._worker = None
                        return
                continue

            try:
                analyze_game(task.game_id, task.depth)
            except Exception:
                logger.exception("Queued analysis failed for game %s", task.game_id)
            finally:
                with self._lock:
                    self._queued_keys.discard((task.game_id, task.depth))
                self._queue.task_done()


analysis_queue = AnalysisQueue()
