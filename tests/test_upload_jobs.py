"""Async upload job queue tests — mocked DB/S3, no Docker."""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from starscream.api.main import app
from starscream.contrib.schema import ContributionManifest
from starscream.contrib.validator import ValidationReport
from starscream.db.models import LicenseType, PipelineJob, PipelineJobStatus, RecorderType
from starscream.db.session import get_db
from starscream.jobs.pipeline_jobs import (
    enqueue_contribution_job,
    get_job_status,
    run_contribution_job,
)

TEMPLATE = Path(__file__).parent.parent / "starscream" / "contrib" / "templates" / "manifest.example.json"

client = TestClient(app)


def _manifest_json() -> str:
    return TEMPLATE.read_text(encoding="utf-8")


def _upload_payload():
    from tests.test_contrib import _make_wav_bytes

    return {
        "data": {"manifest_json": _manifest_json()},
        "files": {"audio": ("door_close_raw.wav", _make_wav_bytes(), "audio/wav")},
    }


@pytest.fixture
def mock_db():
    mock = MagicMock()
    app.dependency_overrides[get_db] = lambda: mock
    yield mock
    app.dependency_overrides.clear()


@pytest.fixture
def mock_contributor():
    contributor = MagicMock()
    contributor.id = uuid.uuid4()
    contributor.display_name = "Test Contributor"
    with patch("starscream.api.middleware.lookup_contributor", return_value=contributor):
        yield contributor


def _recording_row():
    recording = MagicMock()
    recording.id = uuid.uuid4()
    recording.spectral_hash = "hash123"
    recording.taxonomy_code = "URBAN"
    recording.recorded_at = datetime(2026, 3, 15, 14, 32, tzinfo=timezone.utc)
    recording.source_id = uuid.uuid4()
    recording.license = LicenseType.CC0
    recording.title = "Test"
    recording.description = None
    recording.source_object = "door"
    recording.source_action = "closing"
    recording.tags = []
    recording.material = None
    recording.environment = None
    recording.world_model_labels = None
    recording.contributor_id = None
    recording.contributor_name = None
    recording.recorder_type = RecorderType.SMARTPHONE
    recording.recorder_model = None
    recording.sample_rate_hz = 48000
    recording.channels = 1
    recording.bit_depth = 16
    recording.quality = None
    recording.review_status = "unreviewed"
    recording.external_id = None
    recording.external_url = None
    recording.duration_s = 1.0
    recording.is_contribution = True
    recording.flac_key = "flac/test.flac"
    recording.canonical_id = None
    recording.is_duplicate = False
    recording.location_name = None
    recording.country_code = None
    recording.altitude_m = None
    recording.season = None
    recording.habitat = None
    recording.weather = None
    recording.temperature_c = None
    return recording, 40.758, -73.9855


@patch("starscream.api.routes.contrib.enqueue_contribution_job")
def test_async_upload_returns_202(mock_enqueue, mock_db, mock_contributor):
    job_id = uuid.uuid4()
    mock_enqueue.return_value = job_id

    payload = _upload_payload()
    response = client.post(
        "/v1/contrib/upload?async=true",
        data=payload["data"],
        files=payload["files"],
        headers={"X-API-Key": "ss_test_key"},
    )

    assert response.status_code == 202
    body = response.json()
    assert body["job_id"] == str(job_id)
    assert body["status"] == "pending"
    mock_enqueue.assert_called_once()


@patch("starscream.api.routes.contrib.submit_contribution")
@patch("starscream.api.routes.contrib.enqueue_contribution_job")
def test_sync_upload_does_not_enqueue(mock_enqueue, mock_submit, mock_db, mock_contributor):
    recording, lat, lng = _recording_row()
    report = ValidationReport(valid=True, errors=[], warnings=["note"])
    mock_submit.return_value = (recording, report)
    mock_db.execute.return_value.one.return_value = (recording, lat, lng)

    payload = _upload_payload()
    response = client.post(
        "/v1/contrib/upload",
        data=payload["data"],
        files=payload["files"],
        headers={"X-API-Key": "ss_test_key"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["warnings"] == ["note"]
    assert "recording" in body
    mock_enqueue.assert_not_called()
    mock_submit.assert_called_once()


@patch("starscream.api.routes.contrib.get_job_status")
def test_get_job_endpoint_returns_status(mock_get_status, mock_db):
    job_id = uuid.uuid4()
    recording, lat, lng = _recording_row()
    mock_get_status.return_value = MagicMock(
        job_id=job_id,
        status="completed",
        kind="contribution",
        error=None,
        warnings=[],
        recording=recording,
        lat=lat,
        lng=lng,
    )

    response = client.get(f"/v1/contrib/jobs/{job_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["kind"] == "contribution"
    assert body["recording"]["id"] == str(recording.id)


def test_get_job_endpoint_404(mock_db):
    with patch("starscream.api.routes.contrib.get_job_status", return_value=None):
        response = client.get(f"/v1/contrib/jobs/{uuid.uuid4()}")
    assert response.status_code == 404


@patch("starscream.jobs.pipeline_jobs.get_worker")
def test_enqueue_contribution_job_persists_and_submits(mock_get_worker):
    worker = MagicMock()
    mock_get_worker.return_value = worker
    db = MagicMock()
    job = PipelineJob(id=uuid.uuid4(), kind="contribution", status=PipelineJobStatus.PENDING, payload_json={})
    db.refresh.side_effect = lambda obj: setattr(obj, "id", job.id)

    manifest = ContributionManifest.model_validate(json.loads(_manifest_json()))
    audio_bytes = b"wav-bytes"

    result_id = enqueue_contribution_job(db=db, manifest=manifest, audio_bytes=audio_bytes)

    assert result_id == job.id
    db.add.assert_called_once()
    db.commit.assert_called_once()
    worker.submit.assert_called_once()
    assert worker.submit.call_args[0][0] == f"contribution:{job.id}"


@patch("starscream.jobs.pipeline_jobs.submit_contribution")
def test_run_contribution_job_success(mock_submit):
    job_id = uuid.uuid4()
    recording = MagicMock()
    recording.id = uuid.uuid4()
    mock_submit.return_value = (recording, ValidationReport(valid=True, errors=[], warnings=["ok"]))

    session = MagicMock()
    job = PipelineJob(
        id=job_id,
        kind="contribution",
        status=PipelineJobStatus.PENDING,
        payload_json={
            "manifest": json.loads(_manifest_json()),
            "audio_b64": "d2F2",
        },
    )
    session.get.return_value = job

    with patch("starscream.jobs.pipeline_jobs.get_session_factory") as mock_factory:
        mock_factory.return_value = MagicMock(return_value=session)
        run_contribution_job(job_id)

    assert job.status == PipelineJobStatus.COMPLETED
    assert job.result_json["recording_id"] == str(recording.id)
    assert job.result_json["warnings"] == ["ok"]
    assert job.finished_at is not None
    session.close.assert_called_once()


@patch("starscream.jobs.pipeline_jobs.submit_contribution", side_effect=RuntimeError("s3 down"))
def test_run_contribution_job_failure(mock_submit):
    job_id = uuid.uuid4()
    session = MagicMock()
    job = PipelineJob(
        id=job_id,
        kind="contribution",
        status=PipelineJobStatus.PENDING,
        payload_json={
            "manifest": json.loads(_manifest_json()),
            "audio_b64": "d2F2",
        },
    )
    session.get.return_value = job

    with patch("starscream.jobs.pipeline_jobs.get_session_factory") as mock_factory:
        mock_factory.return_value = MagicMock(return_value=session)
        run_contribution_job(job_id)

    assert job.status == PipelineJobStatus.FAILED
    assert job.error == "s3 down"
    assert job.finished_at is not None


def test_get_job_status_completed_with_recording():
    job_id = uuid.uuid4()
    recording_id = uuid.uuid4()
    recording, lat, lng = _recording_row()
    recording.id = recording_id

    job = PipelineJob(
        id=job_id,
        kind="contribution",
        status=PipelineJobStatus.COMPLETED,
        payload_json={},
        result_json={"recording_id": str(recording_id), "warnings": ["w1"]},
    )

    db = MagicMock()
    db.get.return_value = job
    db.execute.return_value.one_or_none.return_value = (recording, lat, lng)

    view = get_job_status(db, job_id)

    assert view is not None
    assert view.status == "completed"
    assert view.warnings == ["w1"]
    assert view.recording is recording
    assert view.lat == lat
    assert view.lng == lng
