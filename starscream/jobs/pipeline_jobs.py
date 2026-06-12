"""Persistent pipeline job queue backed by in-process BackgroundWorker."""

from __future__ import annotations

import base64
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from starscream.api.geo import location_lat, location_lng
from starscream.contrib.schema import ContributionManifest
from starscream.contrib.submit import submit_contribution
from starscream.db.models import PipelineJob, PipelineJobStatus, Recording
from starscream.db.session import get_session_factory
from starscream.jobs.redis_dispatch import enqueue_pipeline_job, redis_enabled
from starscream.jobs.worker import get_worker


@dataclass
class JobStatusView:
    job_id: uuid.UUID
    status: str
    kind: str
    error: str | None
    warnings: list[str] | None
    recording: Recording | None
    lat: float | None
    lng: float | None


def _format_error(exc: Exception) -> str:
    if isinstance(exc, HTTPException):
        detail = exc.detail
        if isinstance(detail, str):
            return detail
        return json.dumps(detail)
    return str(exc)


def run_contribution_job(job_id: uuid.UUID) -> None:
    session = get_session_factory()()
    try:
        job = session.get(PipelineJob, job_id)
        if not job:
            return

        job.status = PipelineJobStatus.RUNNING
        session.commit()

        try:
            payload = job.payload_json
            manifest = ContributionManifest.model_validate(payload["manifest"])
            audio_bytes = base64.b64decode(payload["audio_b64"])
            recording, report = submit_contribution(
                db=session,
                manifest=manifest,
                audio_bytes=audio_bytes,
                strict=True,
            )
            job.status = PipelineJobStatus.COMPLETED
            job.result_json = {
                "recording_id": str(recording.id),
                "warnings": report.warnings,
            }
            job.error = None
        except Exception as exc:
            job.status = PipelineJobStatus.FAILED
            job.error = _format_error(exc)
            job.result_json = None
        finally:
            job.finished_at = datetime.now(timezone.utc)
            session.commit()
    finally:
        session.close()


def enqueue_contribution_job(
    db: Session,
    *,
    manifest: ContributionManifest,
    audio_bytes: bytes,
) -> uuid.UUID:
    job = PipelineJob(
        kind="contribution",
        status=PipelineJobStatus.PENDING,
        payload_json={
            "manifest": manifest.model_dump(mode="json"),
            "audio_b64": base64.b64encode(audio_bytes).decode("ascii"),
        },
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    job_id = job.id
    if redis_enabled():
        enqueue_pipeline_job(job_id)
    else:
        get_worker().submit(f"contribution:{job_id}", lambda: run_contribution_job(job_id))
    return job_id


def get_job_status(db: Session, job_id: uuid.UUID) -> JobStatusView | None:
    job = db.get(PipelineJob, job_id)
    if not job:
        return None

    recording = None
    lat = lng = None
    warnings = None

    if job.status == PipelineJobStatus.COMPLETED and job.result_json:
        warnings = job.result_json.get("warnings") or []
        recording_id = job.result_json.get("recording_id")
        if recording_id:
            lat_col = location_lat(Recording.location).label("lat")
            lng_col = location_lng(Recording.location).label("lng")
            row = db.execute(
                select(Recording, lat_col, lng_col).where(Recording.id == uuid.UUID(recording_id))
            ).one_or_none()
            if row:
                recording, lat, lng = row[0], row[1], row[2]

    return JobStatusView(
        job_id=job.id,
        status=job.status.value,
        kind=job.kind,
        error=job.error,
        warnings=warnings,
        recording=recording,
        lat=lat,
        lng=lng,
    )
