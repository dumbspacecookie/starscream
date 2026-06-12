import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import String, cast, func, select
from sqlalchemy.orm import Session

from starscream.api.schemas import ContributorProfileOut, LeaderboardEntryOut, LeaderboardOut
from starscream.db.models import Contributor, Recording
from starscream.db.session import get_db

router = APIRouter(prefix="/contributors", tags=["contributors"])


@router.get("/leaderboard", response_model=LeaderboardOut)
def get_contributor_leaderboard(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    sound_count = func.count(Recording.id).label("sound_count")
    stmt = (
        select(
            Contributor.id,
            Contributor.display_name,
            Contributor.citations_count,
            sound_count,
        )
        .join(
            Recording,
            Recording.contributor_id == cast(Contributor.id, String),
        )
        .where(Contributor.is_active.is_(True))
        .where(Recording.is_duplicate.is_(False))
        .group_by(Contributor.id)
        .order_by(sound_count.desc(), Contributor.citations_count.desc(), Contributor.id)
        .limit(limit)
    )
    rows = db.execute(stmt).all()

    items = [
        LeaderboardEntryOut(
            rank=index,
            id=row.id,
            display_name=row.display_name,
            sound_count=row.sound_count,
            citations_count=row.citations_count,
        )
        for index, row in enumerate(rows, start=1)
    ]
    return LeaderboardOut(items=items, limit=limit)


@router.get("/{contributor_id}", response_model=ContributorProfileOut)
def get_contributor_profile(
    contributor_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    contributor = db.get(Contributor, contributor_id)
    if not contributor or not contributor.is_active:
        raise HTTPException(status_code=404, detail="Contributor not found")

    sound_count = db.execute(
        select(func.count())
        .select_from(Recording)
        .where(Recording.contributor_id == str(contributor_id))
    ).scalar_one()

    return ContributorProfileOut(
        id=contributor.id,
        display_name=contributor.display_name,
        github_username=contributor.github_username,
        sound_count=sound_count,
        citations_count=contributor.citations_count,
        created_at=contributor.created_at,
    )
