"""Peer-review flag abuse limits."""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi import Request

from starscream.api.peer_review import flag_recording
from starscream.api.peer_review_limits import PeerReviewAbuseError, assert_flag_allowed
from starscream.config import Settings
from starscream.db.models import FlagReason, Recording


def _settings(**overrides) -> Settings:
    return Settings(
        peer_review_max_flags_per_recording_per_day=2,
        peer_review_max_flags_per_reviewer_per_day=3,
        **overrides,
    )


def test_assert_flag_blocks_duplicate_reporter():
    db = MagicMock()
    recording_id = uuid.uuid4()
    key = "contrib:abc"

    db.execute.return_value.first.return_value = (uuid.uuid4(),)
    db.scalar.return_value = 0

    with pytest.raises(PeerReviewAbuseError) as exc:
        assert_flag_allowed(
            db,
            recording_id=recording_id,
            reporter_key=key,
            settings=_settings(),
        )

    assert exc.value.status_code == 409
    assert "already flagged" in exc.value.message


def test_assert_flag_blocks_recording_daily_quota():
    db = MagicMock()
    recording_id = uuid.uuid4()

    db.execute.return_value.first.return_value = None
    db.scalar.side_effect = [2, 0]

    with pytest.raises(PeerReviewAbuseError) as exc:
        assert_flag_allowed(
            db,
            recording_id=recording_id,
            reporter_key="contrib:x",
            settings=_settings(),
        )

    assert exc.value.status_code == 429
    assert "recording" in exc.value.message.lower()


def test_assert_flag_blocks_reviewer_daily_quota():
    db = MagicMock()
    recording_id = uuid.uuid4()

    db.execute.return_value.first.return_value = None
    db.scalar.side_effect = [0, 3]

    with pytest.raises(PeerReviewAbuseError) as exc:
        assert_flag_allowed(
            db,
            recording_id=recording_id,
            reporter_key="contrib:y",
            settings=_settings(),
        )

    assert exc.value.status_code == 429
    assert "your daily" in exc.value.message.lower()


def test_flag_recording_raises_abuse_error():
    db = MagicMock()
    recording_id = uuid.uuid4()
    recording = MagicMock(spec=Recording)
    recording.id = recording_id
    db.get.return_value = recording

    request = MagicMock(spec=Request)
    request.state = MagicMock()
    request.state.contributor = None
    request.client = MagicMock(host="10.0.0.1")

    with patch("starscream.api.peer_review.assert_flag_allowed") as mock_limit:
        mock_limit.side_effect = PeerReviewAbuseError("quota", status_code=429)
        with pytest.raises(PeerReviewAbuseError):
            flag_recording(db, request, recording_id, FlagReason.OTHER)


def test_flag_route_returns_409_for_duplicate():
    from starscream.api.auth import require_reviewer
    from starscream.api.main import app
    from fastapi.testclient import TestClient

    recording_id = uuid.uuid4()

    app.dependency_overrides[require_reviewer] = lambda: MagicMock()
    try:
        with patch("starscream.api.routes.reviews.flag_recording") as mock_flag:
            mock_flag.side_effect = PeerReviewAbuseError(
                "You have already flagged this recording",
                status_code=409,
            )
            with TestClient(app) as client:
                response = client.post(
                    f"/v1/recordings/{recording_id}/flag",
                    json={"reason": "other"},
                    headers={"X-API-Key": "ss_test"},
                )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
