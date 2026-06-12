"""Persist federation harvest run results to harvest_runs."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from starscream.db.models import HarvestRun, HarvestRunStatus
from starscream.federation.ingest import IngestResult


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _harvest_detail(*, errors: list[str] | None = None, message: str | None = None) -> dict | None:
    detail: dict = {}
    if errors:
        detail["errors"] = errors
    if message:
        detail["message"] = message
    return detail or None


def record_harvest_run(
    db: Session,
    source_slug: str,
    *,
    started_at: datetime,
    finished_at: datetime,
    created: int = 0,
    skipped: int = 0,
    failed: int = 0,
    status: HarvestRunStatus,
    detail: dict | None = None,
) -> HarvestRun:
    run = HarvestRun(
        source_slug=source_slug,
        started_at=started_at,
        finished_at=finished_at,
        created=created,
        skipped=skipped,
        failed=failed,
        status=status,
        detail=detail,
    )
    db.add(run)
    db.commit()
    return run


def record_success(
    db: Session,
    source_slug: str,
    started_at: datetime,
    result: IngestResult,
) -> HarvestRun:
    return record_harvest_run(
        db,
        source_slug,
        started_at=started_at,
        finished_at=utcnow(),
        created=result.created,
        skipped=result.skipped,
        failed=result.failed,
        status=HarvestRunStatus.COMPLETED,
        detail=_harvest_detail(errors=result.errors or None),
    )


def record_skipped(
    db: Session,
    source_slug: str,
    started_at: datetime,
    *,
    message: str | None = None,
) -> HarvestRun:
    return record_harvest_run(
        db,
        source_slug,
        started_at=started_at,
        finished_at=utcnow(),
        status=HarvestRunStatus.SKIPPED,
        detail=_harvest_detail(message=message),
    )


def record_failed(
    db: Session,
    source_slug: str,
    started_at: datetime,
    *,
    message: str | None = None,
) -> HarvestRun:
    return record_harvest_run(
        db,
        source_slug,
        started_at=started_at,
        finished_at=utcnow(),
        status=HarvestRunStatus.FAILED,
        detail=_harvest_detail(message=message),
    )
