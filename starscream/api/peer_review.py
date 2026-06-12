import logging
import uuid
from datetime import datetime, timezone

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from starscream.api.geo import location_lat, location_lng
from starscream.api.auth import get_request_contributor, reviewer_key
from starscream.api.peer_review_limits import assert_flag_allowed
from starscream.db.models import (
    FlagReason,
    FlagStatus,
    Recording,
    RecordingFlag,
    RecordingReview,
    ReviewStatus,
)
from starscream.pipeline.index import index_recording

logger = logging.getLogger(__name__)


def _recording_coords(db: Session, recording_id: uuid.UUID) -> tuple[float, float]:
    lat_col = location_lat(Recording.location).label("lat")
    lng_col = location_lng(Recording.location).label("lng")
    row = db.execute(
        select(lat_col, lng_col).where(Recording.id == recording_id)
    ).one_or_none()
    if not row:
        return 0.0, 0.0
    return float(row.lat or 0.0), float(row.lng or 0.0)


def _reindex_recording(db: Session, recording: Recording) -> None:
    lat, lng = _recording_coords(db, recording.id)
    try:
        index_recording(recording, lat, lng)
    except Exception as exc:
        logger.warning("Failed to reindex recording %s after review: %s", recording.id, exc)


def _update_quality_average(db: Session, recording: Recording) -> None:
    avg = db.execute(
        select(func.avg(RecordingReview.score)).where(
            RecordingReview.recording_id == recording.id
        )
    ).scalar()
    if avg is not None:
        recording.quality = max(1, min(5, round(float(avg))))


def rate_recording(
    db: Session,
    request: Request,
    recording_id: uuid.UUID,
    score: int,
) -> tuple[Recording, RecordingReview, bool]:
    """Rate a recording 1–5. Returns (recording, review, created)."""
    recording = db.get(Recording, recording_id)
    if not recording:
        raise ValueError("Recording not found")

    key = reviewer_key(request)
    contributor = get_request_contributor(request)

    existing = db.execute(
        select(RecordingReview).where(
            RecordingReview.recording_id == recording_id,
            RecordingReview.reviewer_key == key,
        )
    ).scalar_one_or_none()

    created = existing is None
    if existing:
        existing.score = score
        review = existing
    else:
        review = RecordingReview(
            recording_id=recording_id,
            score=score,
            reviewer_key=key,
            contributor_id=contributor.id if contributor else None,
        )
        db.add(review)

    _update_quality_average(db, recording)
    db.flush()
    _reindex_recording(db, recording)
    return recording, review, created


def flag_recording(
    db: Session,
    request: Request,
    recording_id: uuid.UUID,
    reason: FlagReason,
    details: str | None = None,
) -> tuple[Recording, RecordingFlag]:
    recording = db.get(Recording, recording_id)
    if not recording:
        raise ValueError("Recording not found")

    key = reviewer_key(request)
    assert_flag_allowed(db, recording_id=recording_id, reporter_key=key)

    contributor = get_request_contributor(request)
    flag = RecordingFlag(
        recording_id=recording_id,
        reason=reason,
        details=details,
        status=FlagStatus.PENDING,
        reporter_key=key,
        contributor_id=contributor.id if contributor else None,
    )
    db.add(flag)

    recording.review_status = ReviewStatus.FLAGGED
    db.flush()
    _reindex_recording(db, recording)
    return recording, flag


def resolve_flag(
    db: Session,
    flag_id: uuid.UUID,
    status: FlagStatus,
) -> RecordingFlag:
    flag = db.get(RecordingFlag, flag_id)
    if not flag:
        raise ValueError("Flag not found")
    if status == FlagStatus.PENDING:
        raise ValueError("Cannot set status back to pending")

    flag.status = status
    flag.resolved_at = datetime.now(timezone.utc)
    db.flush()
    return flag
