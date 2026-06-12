from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from starscream.api.schemas import SourceOut
from starscream.db.models import Source
from starscream.db.session import get_db

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("", response_model=list[SourceOut])
def list_sources(db: Session = Depends(get_db)):
    sources = db.execute(select(Source).order_by(Source.name)).scalars().all()
    return sources
