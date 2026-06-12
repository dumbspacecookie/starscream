from dataclasses import asdict

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from starscream.api.auth import require_admin
from starscream.api.schemas import FlagQueueItemOut, FlagQueueOut, HarvestRunListOut, HarvestRunOut
from starscream.db.models import FlagStatus, HarvestRun, Recording, RecordingFlag
from starscream.db.session import get_db
from starscream.pipeline.metrics import get_metrics

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/metrics")
def admin_metrics(request: Request):
    require_admin(request)
    return asdict(get_metrics())


@router.get("/flags", response_model=FlagQueueOut)
def list_flags(
    request: Request,
    status: FlagStatus = Query(FlagStatus.PENDING),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    require_admin(request)

    total = db.execute(
        select(func.count())
        .select_from(RecordingFlag)
        .where(RecordingFlag.status == status)
    ).scalar_one()

    rows = db.execute(
        select(RecordingFlag, Recording.title)
        .join(Recording, Recording.id == RecordingFlag.recording_id)
        .where(RecordingFlag.status == status)
        .order_by(RecordingFlag.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()

    items = [
        FlagQueueItemOut(
            id=flag.id,
            recording_id=flag.recording_id,
            recording_title=title,
            reason=flag.reason,
            details=flag.details,
            status=flag.status,
            reporter_key=flag.reporter_key,
            created_at=flag.created_at,
        )
        for flag, title in rows
    ]

    return FlagQueueOut(items=items, total=total)


@router.get("/harvest-runs", response_model=HarvestRunListOut)
def list_harvest_runs(
    request: Request,
    db: Session = Depends(get_db),
):
    require_admin(request)

    total = db.execute(select(func.count()).select_from(HarvestRun)).scalar_one()

    rows = db.execute(
        select(HarvestRun)
        .order_by(HarvestRun.started_at.desc())
        .limit(20)
    ).scalars().all()

    return HarvestRunListOut(
        items=[HarvestRunOut.model_validate(row) for row in rows],
        total=total,
    )
