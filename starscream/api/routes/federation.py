from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from starscream.config import get_settings
from starscream.db.session import get_db, get_session_factory
from starscream.federation.harvest import harvest_source_sync
from starscream.jobs.worker import JobStatus, get_worker

router = APIRouter(prefix="/federation", tags=["federation"])


class HarvestOut(BaseModel):
    source: str
    created: int
    skipped: int
    failed: int
    errors: list[str]


class HarvestJobOut(BaseModel):
    job_id: str
    source: str
    status: str


class JobStatusOut(BaseModel):
    job_id: str
    name: str
    status: str
    result: HarvestOut | None = None
    error: str | None = None


def _run_harvest(
    db: Session,
    source_slug: str,
    *,
    pages: int,
    page_size: int,
    download_previews: bool | None,
) -> HarvestOut:
    result = harvest_source_sync(
        db,
        source_slug,
        pages=pages,
        page_size=page_size,
        download_previews=download_previews,
    )
    return HarvestOut(
        source=source_slug,
        created=result.created,
        skipped=result.skipped,
        failed=result.failed,
        errors=result.errors,
    )


@router.post("/harvest/{source_slug}", response_model=HarvestOut | HarvestJobOut)
def trigger_harvest(
    source_slug: str,
    pages: int = Query(1, ge=1, le=20),
    page_size: int = Query(50, ge=1, le=150),
    download_previews: bool = Query(
        default=None,
        description="Download preview audio when permitted; default follows CATALOG_ONLY setting",
    ),
    background: bool = Query(False, description="Run harvest in background worker"),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    if source_slug == "freesound" and not settings.freesound_api_key:
        raise HTTPException(
            status_code=400,
            detail="FREESOUND_API_KEY not configured",
        )

    if background:

        def _background_harvest() -> HarvestOut:
            session = get_session_factory()()
            try:
                return _run_harvest(
                    session,
                    source_slug,
                    pages=pages,
                    page_size=page_size,
                    download_previews=download_previews,
                )
            finally:
                session.close()

        job_id = get_worker().submit(f"harvest:{source_slug}", _background_harvest)
        return HarvestJobOut(job_id=job_id, source=source_slug, status="pending")

    try:
        return _run_harvest(
            db,
            source_slug,
            pages=pages,
            page_size=page_size,
            download_previews=download_previews,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/jobs/{job_id}", response_model=JobStatusOut)
def get_harvest_job(job_id: str):
    job = get_worker().get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    result = job.result if job.status == JobStatus.COMPLETED else None
    return JobStatusOut(
        job_id=job.id,
        name=job.name,
        status=job.status.value,
        result=result,
        error=job.error,
    )
