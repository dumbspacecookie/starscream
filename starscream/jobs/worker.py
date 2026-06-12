"""In-process background worker for harvest and other long-running tasks."""

from __future__ import annotations

import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Job:
    id: str
    name: str
    status: JobStatus
    created_at: datetime
    finished_at: datetime | None = None
    result: Any = None
    error: str | None = None


class BackgroundWorker:
    def __init__(self, max_workers: int = 2) -> None:
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="starscream-job",
        )
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def submit(self, name: str, fn: Callable[[], Any]) -> str:
        job_id = uuid.uuid4().hex
        job = Job(
            id=job_id,
            name=name,
            status=JobStatus.PENDING,
            created_at=datetime.now(timezone.utc),
        )
        with self._lock:
            self._jobs[job_id] = job

        def _run() -> None:
            with self._lock:
                job.status = JobStatus.RUNNING
            try:
                result = fn()
                with self._lock:
                    job.status = JobStatus.COMPLETED
                    job.result = result
                    job.finished_at = datetime.now(timezone.utc)
            except Exception as exc:
                logger.exception("Background job %s (%s) failed", job_id, name)
                with self._lock:
                    job.status = JobStatus.FAILED
                    job.error = str(exc)
                    job.finished_at = datetime.now(timezone.utc)

        self._executor.submit(_run)
        return job_id

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)


_worker: BackgroundWorker | None = None
_worker_lock = threading.Lock()


def get_worker() -> BackgroundWorker:
    global _worker
    with _worker_lock:
        if _worker is None:
            _worker = BackgroundWorker()
        return _worker
