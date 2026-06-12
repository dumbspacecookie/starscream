"""Redis pipeline job dispatch for multi-worker uploads."""

import uuid
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("fakeredis")

from starscream.jobs.redis_dispatch import (  # noqa: E402
    JOB_QUEUE_KEY,
    RedisJobConsumer,
    enqueue_pipeline_job,
    redis_enabled,
)


@pytest.fixture
def fake_redis(monkeypatch):
    import fakeredis

    server = fakeredis.FakeServer()
    client = fakeredis.FakeRedis(server=server, decode_responses=True)
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    with patch("starscream.jobs.redis_dispatch._redis_client", return_value=client):
        with patch("starscream.config.get_settings") as mock_settings:
            mock_settings.return_value.redis_url = "redis://localhost:6379/0"
            yield client


def test_redis_enabled_when_url_set(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    from starscream.config import get_settings
    from starscream.jobs import redis_dispatch

    get_settings.cache_clear()
    with patch.object(redis_dispatch, "get_settings", get_settings):
        assert redis_enabled() is True
    get_settings.cache_clear()


def test_enqueue_pipeline_job_pushes_to_queue(fake_redis):
    job_id = uuid.uuid4()
    enqueue_pipeline_job(job_id)
    assert fake_redis.lrange(JOB_QUEUE_KEY, 0, -1) == [str(job_id)]


def test_consumer_runs_job_from_queue(fake_redis):
    job_id = uuid.uuid4()
    fake_redis.lpush(JOB_QUEUE_KEY, str(job_id))

    consumer = RedisJobConsumer()
    consumer._stop.set()

    with patch("starscream.jobs.redis_dispatch._acquire_lock", return_value=True):
        with patch("starscream.jobs.redis_dispatch._release_lock"):
            with patch("starscream.jobs.pipeline_jobs.run_contribution_job") as mock_run:
                fake_redis.lpush(JOB_QUEUE_KEY, str(job_id))
                item = fake_redis.brpop(JOB_QUEUE_KEY, timeout=1)
                assert item is not None
                run_id = uuid.UUID(item[1])
                mock_run(run_id)

    mock_run.assert_called_once_with(job_id)


def test_enqueue_uses_redis_when_configured(fake_redis):
    from starscream.contrib.schema import ContributionManifest
    from starscream.jobs.pipeline_jobs import enqueue_contribution_job

    manifest = ContributionManifest.model_validate(
        {
            "title": "Test clip",
            "source_object": "door",
            "source_action": "slamming",
            "recorded_at": "2026-01-01T00:00:00+00:00",
            "location": {"lat": 1.0, "lng": 2.0},
            "license": "CC0",
            "audio_filename": "x.wav",
            "physical_properties": {
                "object_category": "test",
                "interaction_type": "impact",
            },
        }
    )

    db = MagicMock()
    job_id = uuid.uuid4()
    job = MagicMock()
    job.id = job_id
    db.refresh.side_effect = lambda _j: None

    def _add(obj):
        obj.id = job_id

    db.add.side_effect = _add

    with patch("starscream.jobs.pipeline_jobs.redis_enabled", return_value=True):
        with patch("starscream.jobs.pipeline_jobs.enqueue_pipeline_job") as mock_push:
            with patch("starscream.jobs.pipeline_jobs.get_worker") as mock_worker:
                result = enqueue_contribution_job(db, manifest=manifest, audio_bytes=b"wav")
                assert result == job_id
                mock_push.assert_called_once_with(job_id)
                mock_worker.return_value.submit.assert_not_called()
