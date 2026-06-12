from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from starscream.api.schemas import StatsOut
from starscream.api.stats_helpers import compute_stats
from starscream.db.session import get_db

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("", response_model=StatsOut)
def get_stats(db: Session = Depends(get_db)):
    return compute_stats(db)
