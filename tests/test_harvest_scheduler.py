import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from starscream.api.main import app
from starscream.db.models import HarvestRunStatus
from starscream.federation.ingest import IngestResult
from starscream.jobs.harvest_state import record_failed, record_skipped, record_success
from starscream.jobs.scheduler import main as scheduler_main


def test_harvest_state_record_success_commits_run():
    db = MagicMock()
    started = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
    result = IngestResult(
        created=3,
        skipped=1,
        failed=0,
        errors=["page 2: timeout", "abc123 download: 404"],
    )

    with patch("starscream.jobs.harvest_state.utcnow") as mock_now:
        mock_now.return_value = datetime(2026, 6, 10, 12, 5, tzinfo=timezone.utc)
        run = record_success(db, "xeno-canto", started, result)

    db.add.assert_called_once()
    db.commit.assert_called_once()
    saved = db.add.call_args[0][0]
    assert saved.source_slug == "xeno-canto"
    assert saved.created == 3
    assert saved.skipped == 1
    assert saved.failed == 0
    assert saved.status == HarvestRunStatus.COMPLETED
    assert saved.detail == {"errors": ["page 2: timeout", "abc123 download: 404"]}
    assert run is saved


def test_harvest_state_record_skipped_and_failed():
    db = MagicMock()
    started = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)

    skipped = record_skipped(db, "bad-source", started, message="Unknown source: bad")
    assert skipped.status == HarvestRunStatus.SKIPPED
    assert skipped.created == 0
    assert skipped.detail == {"message": "Unknown source: bad"}

    failed = record_failed(db, "freesound", started, message="connection reset")
    assert failed.status == HarvestRunStatus.FAILED
    assert failed.failed == 0
    assert failed.detail == {"message": "connection reset"}
    assert db.commit.call_count == 2


def test_harvest_all_logs_completed_run():
    result = IngestResult(created=2, skipped=0, failed=0, errors=[])
    session = MagicMock()

    with (
        patch("starscream.jobs.harvest_all.get_session_factory", return_value=lambda: session),
        patch("starscream.jobs.harvest_all.harvest_source_sync", return_value=result),
        patch("starscream.jobs.harvest_all.record_success") as mock_success,
        patch("starscream.jobs.harvest_all.utcnow") as mock_now,
    ):
        mock_now.return_value = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
        from starscream.jobs.harvest_all import harvest_all

        code = harvest_all(["xeno-canto"], pages=1)

    assert code == 0
    mock_success.assert_called_once_with(session, "xeno-canto", mock_now.return_value, result)
    session.close.assert_called_once()


def test_harvest_all_logs_skipped_run_on_value_error():
    session = MagicMock()

    with (
        patch("starscream.jobs.harvest_all.get_session_factory", return_value=lambda: session),
        patch(
            "starscream.jobs.harvest_all.harvest_source_sync",
            side_effect=ValueError("Unknown source: bad"),
        ),
        patch("starscream.jobs.harvest_all.record_skipped") as mock_skipped,
        patch("starscream.jobs.harvest_all.utcnow") as mock_now,
    ):
        mock_now.return_value = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
        from starscream.jobs.harvest_all import harvest_all

        code = harvest_all(["bad"], pages=1)

    assert code == 1
    mock_skipped.assert_called_once_with(session, "bad", mock_now.return_value, message="Unknown source: bad")


def test_scheduler_run_once_delegates_to_harvest_all():
    with patch("starscream.jobs.scheduler.harvest_all", return_value=0) as mock_harvest:
        code = scheduler_main(["run-once", "--sources", "xeno-canto", "--pages", "2"])

    assert code == 0
    mock_harvest.assert_called_once_with(
        ["xeno-canto"],
        pages=2,
        page_size=50,
        download_previews=True,
    )


def test_scheduler_daemon_runs_initial_cycle():
    with (
        patch("starscream.jobs.scheduler.harvest_all", return_value=0) as mock_harvest,
        patch("starscream.jobs.scheduler.time.sleep"),
        patch("starscream.jobs.scheduler.schedule.run_pending"),
    ):
        from starscream.jobs.scheduler import run_daemon

        code = run_daemon(
            ["inaturalist"],
            interval_hours=12,
            download_previews=False,
            stop_after=1,
        )

    assert code == 0
    mock_harvest.assert_called_once_with(
        ["inaturalist"],
        pages=1,
        page_size=50,
        download_previews=False,
    )


def test_scheduler_rejects_unknown_source():
    code = scheduler_main(["run-once", "--sources", "not-a-real-source"])
    assert code == 1


def test_admin_harvest_runs_endpoint_in_openapi():
    client = TestClient(app)
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert "/v1/admin/harvest-runs" in response.json()["paths"]


def test_admin_harvest_runs_requires_admin_key():
    client = TestClient(app)
    response = client.get("/v1/admin/harvest-runs")
    assert response.status_code in (401, 503)


def test_admin_harvest_runs_returns_last_runs():
    run_id = uuid.uuid4()
    started = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
    finished = datetime(2026, 6, 10, 12, 5, tzinfo=timezone.utc)
    row = MagicMock(
        id=run_id,
        source_slug="xeno-canto",
        started_at=started,
        finished_at=finished,
        created=4,
        skipped=1,
        failed=0,
        status=HarvestRunStatus.COMPLETED,
        detail=None,
    )

    count_result = MagicMock()
    count_result.scalar_one.return_value = 1
    list_result = MagicMock()
    list_result.scalars.return_value.all.return_value = [row]

    mock_db = MagicMock()
    mock_db.execute.side_effect = [count_result, list_result]

    from starscream.db.session import get_db

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        with patch("starscream.api.auth.get_settings") as mock_settings:
            mock_settings.return_value.admin_api_key = "admin-secret"
            client = TestClient(app)
            response = client.get("/v1/admin/harvest-runs", headers={"X-API-Key": "admin-secret"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    item = data["items"][0]
    assert item["id"] == str(run_id)
    assert item["source_slug"] == "xeno-canto"
    assert item["created"] == 4
    assert item["status"] == "completed"
