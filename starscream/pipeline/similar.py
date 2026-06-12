"""Find recordings similar to a given recording by metadata and location."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from geoalchemy2.functions import ST_DWithin
from sqlalchemy import select

from starscream.api.geo import location_lat, location_lng
from starscream.db.models import Recording

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

_WORD_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)


def _parent_taxonomy_prefix(code: str) -> str:
    if "." not in code:
        return code
    return code.rsplit(".", 1)[0]


def _same_taxonomy_prefix(a: str, b: str) -> bool:
    return _parent_taxonomy_prefix(a) == _parent_taxonomy_prefix(b)


def _normalize_tags(tags: list | None) -> set[str]:
    if not tags:
        return set()
    return {str(t).lower() for t in tags}


def _source_object_words(text: str | None) -> set[str]:
    if not text:
        return set()
    return {m.group(0).lower() for m in _WORD_RE.finditer(text)}


def score_similarity(source: Recording, candidate: Recording, within_50km: bool) -> int:
    """Score how similar *candidate* is to *source* (higher is better)."""
    score = 0

    if _same_taxonomy_prefix(source.taxonomy_code, candidate.taxonomy_code):
        score += 3

    shared_tags = _normalize_tags(source.tags) & _normalize_tags(candidate.tags)
    score += len(shared_tags) * 2

    if source.material and candidate.material and source.material == candidate.material:
        score += 2

    if _source_object_words(source.source_object) & _source_object_words(candidate.source_object):
        score += 1

    if within_50km:
        score += 2

    return score


def find_similar_recordings(
    db: Session,
    recording: Recording,
    limit: int = 10,
) -> list[tuple[Recording, float, float, int]]:
    """Return up to *limit* similar recordings as (recording, lat, lng, score)."""
    lat_col = location_lat(Recording.location).label("lat")
    lng_col = location_lng(Recording.location).label("lng")

    stmt = (
        select(Recording, lat_col, lng_col)
        .where(Recording.id != recording.id)
        .where(Recording.is_duplicate.is_(False))
    )

    rows = db.execute(stmt).all()

    within_ids: set = set()
    if recording.location is not None:
        near_rows = db.execute(
            select(Recording.id).where(
                Recording.id != recording.id,
                Recording.is_duplicate.is_(False),
                ST_DWithin(
                    Recording.location,
                    recording.location,
                    50_000,
                    use_spheroid=True,
                ),
            )
        ).all()
        within_ids = {row[0] for row in near_rows}

    scored: list[tuple[Recording, float, float, int]] = []
    for candidate, lat, lng in rows:
        if candidate.id == recording.id or candidate.is_duplicate:
            continue
        within_50km = candidate.id in within_ids
        points = score_similarity(recording, candidate, within_50km=within_50km)
        if points > 0:
            scored.append((candidate, lat, lng, points))

    scored.sort(key=lambda row: (-row[3], row[0].recorded_at, str(row[0].id)))
    return scored[:limit]
