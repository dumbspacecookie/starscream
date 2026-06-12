"""Abuse controls for peer-review flag endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from starscream.config import Settings, get_settings


class PeerReviewAbuseError(Exception):
    """Flag/rate abuse — maps to HTTP 409 (duplicate) or 429 (quota)."""

    def __init__(self, message: str, *, status_code: int = 429) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def assert_flag_allowed(
    db: Session,
    *,
    recording_id: uuid.UUID,
    reporter_key: str,
    settings: Settings | None = None,
) -> None:
    """Raise PeerReviewAbuseError when flag quotas would be exceeded."""
    cfg = settings or get_settings()
    since = datetime.now(timezone.utc) - timedelta(days=1)

    from starscream.db.models import RecordingFlag

    duplicate = db.execute(
        select(RecordingFlag.id).where(
            RecordingFlag.recording_id == recording_id,
            RecordingFlag.reporter_key == reporter_key,
        )
    ).first()
    if duplicate:
        raise PeerReviewAbuseError(
            "You have already flagged this recording",
            status_code=409,
        )

    recording_flags_today = db.scalar(
        select(func.count())
        .select_from(RecordingFlag)
        .where(
            RecordingFlag.recording_id == recording_id,
            RecordingFlag.created_at >= since,
        )
    ) or 0
    if recording_flags_today >= cfg.peer_review_max_flags_per_recording_per_day:
        raise PeerReviewAbuseError(
            f"This recording has reached the daily flag limit "
            f"({cfg.peer_review_max_flags_per_recording_per_day})",
        )

    reviewer_flags_today = db.scalar(
        select(func.count())
        .select_from(RecordingFlag)
        .where(
            RecordingFlag.reporter_key == reporter_key,
            RecordingFlag.created_at >= since,
        )
    ) or 0
    if reviewer_flags_today >= cfg.peer_review_max_flags_per_reviewer_per_day:
        raise PeerReviewAbuseError(
            f"You have reached your daily flag limit "
            f"({cfg.peer_review_max_flags_per_reviewer_per_day})",
        )
