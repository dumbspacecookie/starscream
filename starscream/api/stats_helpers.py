"""Shared stats computation for REST and GraphQL."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from starscream.api.schemas import StatsOut
from starscream.db.models import Recording, Source, Tag, TaxonomyNode
from starscream.storage.stats import flac_storage_bytes


def compute_stats(db: Session) -> StatsOut:
    total_recordings = db.scalar(select(func.count()).select_from(Recording)) or 0
    total_sources = db.scalar(select(func.count()).select_from(Source)) or 0
    countries_covered = (
        db.scalar(
            select(func.count(func.distinct(Recording.country_code))).where(
                Recording.country_code.isnot(None)
            )
        )
        or 0
    )
    taxonomy_branches = (
        db.scalar(
            select(func.count()).select_from(TaxonomyNode).where(TaxonomyNode.parent_code.is_(None))
        )
        or 0
    )
    total_contributions = (
        db.scalar(
            select(func.count()).select_from(Recording).where(Recording.is_contribution.is_(True))
        )
        or 0
    )
    total_tags = db.scalar(select(func.count()).select_from(Tag)) or 0
    storage_bytes = flac_storage_bytes()

    return StatsOut(
        total_recordings=total_recordings,
        total_sources=total_sources,
        countries_covered=countries_covered,
        taxonomy_branches=taxonomy_branches,
        storage_flac_gb=round(storage_bytes / (1024**3), 4),
        total_contributions=total_contributions,
        total_tags=total_tags,
    )
