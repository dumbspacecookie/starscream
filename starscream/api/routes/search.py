import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from starscream.api.schemas import SearchHitOut, SearchOut
from starscream.pipeline.index import INDEX_NAME, _client

router = APIRouter(prefix="/search", tags=["search"])


def _escape_filter_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _build_filter(
    taxonomy: str | None,
    country: str | None,
    material: str | None,
    is_contribution: bool | None,
) -> str | None:
    parts: list[str] = []
    if taxonomy:
        parts.append(f'taxonomy_code STARTS WITH "{_escape_filter_value(taxonomy)}"')
    if country:
        parts.append(f'country_code = "{_escape_filter_value(country)}"')
    if material:
        parts.append(f'material = "{_escape_filter_value(material)}"')
    if is_contribution is not None:
        parts.append(f"is_contribution = {str(is_contribution).lower()}")
    if not parts:
        return None
    return " AND ".join(parts)


def _hit_from_doc(doc: dict) -> SearchHitOut:
    recorded_at = doc.get("recorded_at")
    if isinstance(recorded_at, str):
        recorded_at = datetime.fromisoformat(recorded_at)
    return SearchHitOut(
        id=uuid.UUID(doc["id"]),
        title=doc.get("title"),
        source_object=doc.get("source_object"),
        source_action=doc.get("source_action"),
        description=doc.get("description"),
        tags=doc.get("tags") or [],
        material=doc.get("material"),
        environment=doc.get("environment"),
        taxonomy_code=doc["taxonomy_code"],
        location_name=doc.get("location_name"),
        country_code=doc.get("country_code"),
        habitat=doc.get("habitat"),
        season=doc.get("season"),
        quality=doc.get("quality"),
        is_contribution=doc.get("is_contribution", False),
        recorded_at=recorded_at,
        lat=doc.get("lat"),
        lng=doc.get("lng"),
    )


@router.get("", response_model=SearchOut)
def search_recordings(
    q: str = Query("", max_length=500, description="Full-text search query"),
    limit: int = Query(20, ge=1, le=100),
    taxonomy: str | None = Query(None, max_length=64, description="Filter by taxonomy code prefix"),
    country: str | None = Query(None, max_length=8, description="Filter by ISO country code"),
    material: str | None = Query(None, max_length=64, description="Filter by material"),
    is_contribution: bool | None = Query(None, description="Filter by contribution status"),
):
    client = _client()
    if not client:
        raise HTTPException(status_code=503, detail="Search service unavailable")

    options: dict = {"limit": limit}
    filter_expr = _build_filter(taxonomy, country, material, is_contribution)
    if filter_expr:
        options["filter"] = filter_expr

    try:
        result = client.index(INDEX_NAME).search(q, options)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Search query failed") from exc

    hits = [_hit_from_doc(doc) for doc in result.get("hits", [])]
    return SearchOut(
        query=result.get("query", q),
        hits=hits,
        limit=limit,
        total=result.get("estimatedTotalHits"),
        processing_time_ms=result.get("processingTimeMs"),
    )
