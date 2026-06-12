import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from starscream.api.auth import require_reviewer
from starscream.api.peer_review import flag_recording, rate_recording
from starscream.api.peer_review_limits import PeerReviewAbuseError
from starscream.api.schemas import FlagIn, FlagOut, RateIn, RateOut
from starscream.db.models import RecordingReview
from starscream.db.session import get_db

router = APIRouter(tags=["peer-review"])


@router.post("/recordings/{recording_id}/rate", response_model=RateOut)
def rate(
    recording_id: uuid.UUID,
    body: RateIn,
    request: Request,
    db: Session = Depends(get_db),
    _reviewer=Depends(require_reviewer),
):
    try:
        recording, review, created = rate_recording(
            db, request, recording_id, body.score
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    db.commit()

    review_count = db.execute(
        select(func.count()).select_from(RecordingReview).where(
            RecordingReview.recording_id == recording_id
        )
    ).scalar_one()

    return RateOut(
        recording_id=recording_id,
        score=review.score,
        quality=recording.quality,
        review_count=review_count,
        updated=not created,
    )


@router.post("/recordings/{recording_id}/flag", response_model=FlagOut, status_code=201)
def flag(
    recording_id: uuid.UUID,
    body: FlagIn,
    request: Request,
    db: Session = Depends(get_db),
    _reviewer=Depends(require_reviewer),
):
    try:
        recording, flag = flag_recording(
            db, request, recording_id, body.reason, body.details
        )
    except PeerReviewAbuseError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    db.commit()

    return FlagOut(
        id=flag.id,
        recording_id=recording_id,
        reason=flag.reason,
        details=flag.details,
        status=flag.status,
        review_status=recording.review_status,
        created_at=flag.created_at,
    )
