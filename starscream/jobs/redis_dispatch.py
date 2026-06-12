"""Redis-backed pipeline job dispatch for multi-worker API deployments."""

from __future__ import annotations

import logging
import threading
import uuid

from starscream.config import get_settings

logger = logging.getLogger(__name__)

JOB_QUEUE_KEY = "starscream:pipeline_jobs"
JOB_LOCK_PREFIX = "starscream:job:lock:"
LOCK_TTL_S = 3600


def redis_enabled() -> bool:
    url = get_settings().redis_url.strip()
    return bool(url)


def _redis_client():
    import redis

    return redis.from_url(get_settings().redis_url, decode_responses=True)


def enqueue_pipeline_job(job_id: uuid.UUID) -> None:
    """Push a persisted job id onto the shared Redis queue."""
    client = _redis_client()
    client.lpush(JOB_QUEUE_KEY, str(job_id))
    logger.debug("Enqueued pipeline job %s on Redis", job_id)


def _acquire_lock(client, job_id: uuid.UUID, worker_id: str) -> bool:
    return bool(
        client.set(
            f"{JOB_LOCK_PREFIX}{job_id}",
            worker_id,
            nx=True,
            ex=LOCK_TTL_S,
        )
    )


def _release_lock(client, job_id: uuid.UUID) -> None:
    client.delete(f"{JOB_LOCK_PREFIX}{job_id}")


class RedisJobConsumer:
    """Background thread: BRPOP job ids and run them with a distributed lock."""

    def __init__(self) -> None:
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._worker_id = uuid.uuid4().hex[:12]

    def start(self) -> None:
        if not redis_enabled():
            return
        try:
            import redis  # noqa: F401

            _redis_client().ping()
        except ImportError:
            logger.warning(
                "redis_url is set but redis package is not installed; "
                "pipeline jobs will not be consumed from Redis"
            )
            return
        except Exception as exc:
            logger.warning("Redis unavailable for pipeline jobs: %s", exc)
            return
        self._thread = threading.Thread(
            target=self._loop,
            name="redis-pipeline-consumer",
            daemon=True,
        )
        self._thread.start()
        logger.info("Redis pipeline job consumer started (worker %s)", self._worker_id)

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=10)

    def _loop(self) -> None:
        from starscream.jobs.pipeline_jobs import run_contribution_job

        client = _redis_client()
        while not self._stop.is_set():
            item = client.brpop(JOB_QUEUE_KEY, timeout=5)
            if not item:
                continue
            try:
                job_id = uuid.UUID(item[1])
            except ValueError:
                logger.warning("Invalid job id on Redis queue: %r", item[1])
                continue

            if not _acquire_lock(client, job_id, self._worker_id):
                logger.debug("Job %s already claimed by another worker", job_id)
                continue

            try:
                run_contribution_job(job_id)
            except Exception:
                logger.exception("Redis pipeline job %s failed", job_id)
            finally:
                _release_lock(client, job_id)


_consumer: RedisJobConsumer | None = None
_consumer_lock = threading.Lock()


def get_redis_consumer() -> RedisJobConsumer:
    global _consumer
    with _consumer_lock:
        if _consumer is None:
            _consumer = RedisJobConsumer()
        return _consumer
