import uuid
from datetime import datetime
from typing import Any

import strawberry
from geoalchemy2.functions import ST_DWithin, ST_MakePoint, ST_SetSRID
from graphql import GraphQLError
from sqlalchemy import select
from sqlalchemy.orm import Session
from strawberry.types import Info

from starscream.api.geo import location_lat, location_lng
from starscream.api.routes.search import INDEX_NAME, _client, _hit_from_doc
from starscream.api.stats_helpers import compute_stats
from starscream.db.models import (
    LicenseType,
    RecorderType,
    Recording,
    ReviewStatus,
    Season,
)

LicenseEnum = strawberry.enum(LicenseType)
RecorderEnum = strawberry.enum(RecorderType)
ReviewEnum = strawberry.enum(ReviewStatus)
SeasonEnum = strawberry.enum(Season)


@strawberry.type
class Location:
    lat: float
    lng: float


@strawberry.type
class RecordingType:
    id: strawberry.ID
    spectral_hash: str
    taxonomy_code: str
    location: Location
    recorded_at: datetime
    source_id: strawberry.ID
    license: LicenseEnum
    title: str | None
    description: str | None
    source_object: str | None
    source_action: str | None
    tags: list[str]
    material: str | None
    environment: str | None
    world_model_labels: strawberry.scalars.JSON | None
    contributor_id: str | None
    contributor_name: str | None
    recorder_model: str | None
    sample_rate_hz: int | None
    channels: int | None
    bit_depth: int | None
    is_contribution: bool
    location_name: str | None
    country_code: str | None
    altitude_m: float | None
    season: SeasonEnum | None
    habitat: str | None
    weather: str | None
    temperature_c: float | None
    cross_modal_links: strawberry.scalars.JSON | None
    recorder_type: RecorderEnum
    quality: int | None
    review_status: ReviewEnum
    external_id: str | None
    external_url: str | None
    duration_s: float | None
    has_audio: bool
    canonical_id: strawberry.ID | None
    is_duplicate: bool


@strawberry.type
class SearchHit:
    id: strawberry.ID
    title: str | None
    source_object: str | None
    source_action: str | None
    description: str | None
    tags: list[str]
    material: str | None
    environment: str | None
    taxonomy_code: str
    location_name: str | None
    country_code: str | None
    habitat: str | None
    season: str | None
    quality: int | None
    is_contribution: bool
    recorded_at: datetime | None
    lat: float | None
    lng: float | None


@strawberry.type
class SearchResult:
    query: str
    hits: list[SearchHit]
    limit: int
    total: int | None
    processing_time_ms: int | None


@strawberry.type
class Stats:
    total_recordings: int
    total_sources: int
    countries_covered: int
    taxonomy_branches: int
    storage_flac_gb: float
    total_contributions: int
    total_tags: int


def _db(info: Info) -> Session:
    return info.context["db"]


def _to_recording(recording: Recording, lat: float | None, lng: float | None) -> RecordingType:
    return RecordingType(
        id=strawberry.ID(str(recording.id)),
        spectral_hash=recording.spectral_hash,
        taxonomy_code=recording.taxonomy_code,
        location=Location(lat=lat or 0.0, lng=lng or 0.0),
        recorded_at=recording.recorded_at,
        source_id=strawberry.ID(str(recording.source_id)),
        license=recording.license,
        title=recording.title,
        description=recording.description,
        source_object=recording.source_object,
        source_action=recording.source_action,
        tags=recording.tags or [],
        material=recording.material,
        environment=recording.environment,
        world_model_labels=recording.world_model_labels,
        contributor_id=recording.contributor_id,
        contributor_name=recording.contributor_name,
        recorder_model=recording.recorder_model,
        sample_rate_hz=recording.sample_rate_hz,
        channels=recording.channels,
        bit_depth=recording.bit_depth,
        is_contribution=recording.is_contribution,
        location_name=recording.location_name,
        country_code=recording.country_code,
        altitude_m=recording.altitude_m,
        season=recording.season,
        habitat=recording.habitat,
        weather=recording.weather,
        temperature_c=recording.temperature_c,
        cross_modal_links=recording.cross_modal_links,
        recorder_type=recording.recorder_type,
        quality=recording.quality,
        review_status=recording.review_status,
        external_id=recording.external_id,
        external_url=recording.external_url,
        duration_s=recording.duration_s,
        has_audio=recording.flac_key is not None,
        canonical_id=strawberry.ID(str(recording.canonical_id))
        if recording.canonical_id
        else None,
        is_duplicate=recording.is_duplicate,
    )


def _to_search_hit(hit: Any) -> SearchHit:
    return SearchHit(
        id=strawberry.ID(str(hit.id)),
        title=hit.title,
        source_object=hit.source_object,
        source_action=hit.source_action,
        description=hit.description,
        tags=hit.tags,
        material=hit.material,
        environment=hit.environment,
        taxonomy_code=hit.taxonomy_code,
        location_name=hit.location_name,
        country_code=hit.country_code,
        habitat=hit.habitat,
        season=hit.season.value if isinstance(hit.season, Season) else hit.season,
        quality=hit.quality,
        is_contribution=hit.is_contribution,
        recorded_at=hit.recorded_at,
        lat=hit.lat,
        lng=hit.lng,
    )


def _recordings_query(
    db: Session,
    *,
    near: str | None,
    taxonomy: str | None,
    season: str | None,
    quality_min: int | None,
    limit: int,
) -> list[RecordingType]:
    lat_col = location_lat(Recording.location).label("lat")
    lng_col = location_lng(Recording.location).label("lng")
    stmt = select(Recording, lat_col, lng_col)

    if near:
        try:
            lat_s, lng_s = near.split(",", 1)
            lat, lng = float(lat_s.strip()), float(lng_s.strip())
        except ValueError as exc:
            raise GraphQLError("near must be lat,lng") from exc
        radius_m = 50 * 1000
        point = ST_SetSRID(ST_MakePoint(lng, lat), 4326)
        stmt = stmt.where(ST_DWithin(Recording.location, point, radius_m, use_spheroid=True))

    if taxonomy:
        stmt = stmt.where(Recording.taxonomy_code.startswith(taxonomy))
    if season:
        stmt = stmt.where(Recording.season == season)
    if quality_min:
        stmt = stmt.where(Recording.quality >= quality_min)

    stmt = stmt.order_by(Recording.recorded_at.desc(), Recording.id.desc()).limit(limit)
    rows = db.execute(stmt).all()
    return [_to_recording(rec, lat, lng) for rec, lat, lng in rows]


def _stats_query(db: Session) -> Stats:
    out = compute_stats(db)
    return Stats(
        total_recordings=out.total_recordings,
        total_sources=out.total_sources,
        countries_covered=out.countries_covered,
        taxonomy_branches=out.taxonomy_branches,
        storage_flac_gb=out.storage_flac_gb,
        total_contributions=out.total_contributions,
        total_tags=out.total_tags,
    )


@strawberry.type
class Query:
    @strawberry.field
    def recordings(
        self,
        info: Info,
        near: str | None = None,
        taxonomy: str | None = None,
        season: str | None = None,
        qualityMin: int | None = None,
        limit: int = 100,
    ) -> list[RecordingType]:
        if limit < 1 or limit > 500:
            raise GraphQLError("limit must be between 1 and 500")
        if qualityMin is not None and (qualityMin < 1 or qualityMin > 5):
            raise GraphQLError("qualityMin must be between 1 and 5")
        return _recordings_query(
            _db(info),
            near=near,
            taxonomy=taxonomy,
            season=season,
            quality_min=qualityMin,
            limit=limit,
        )

    @strawberry.field
    def recording(self, info: Info, id: strawberry.ID) -> RecordingType | None:
        try:
            recording_id = uuid.UUID(str(id))
        except ValueError as exc:
            raise GraphQLError("Invalid recording id") from exc

        lat_col = location_lat(Recording.location).label("lat")
        lng_col = location_lng(Recording.location).label("lng")
        row = (
            _db(info)
            .execute(select(Recording, lat_col, lng_col).where(Recording.id == recording_id))
            .one_or_none()
        )
        if not row:
            return None
        rec, lat, lng = row
        return _to_recording(rec, lat, lng)

    @strawberry.field
    def search(self, info: Info, q: str = "", limit: int = 20) -> SearchResult:
        if limit < 1 or limit > 100:
            raise GraphQLError("limit must be between 1 and 100")

        client = _client()
        if not client:
            raise GraphQLError("Search service unavailable")

        try:
            result = client.index(INDEX_NAME).search(q, {"limit": limit})
        except Exception as exc:
            raise GraphQLError("Search query failed") from exc

        hits = [_to_search_hit(_hit_from_doc(doc)) for doc in result.get("hits", [])]
        return SearchResult(
            query=result.get("query", q),
            hits=hits,
            limit=limit,
            total=result.get("estimatedTotalHits"),
            processing_time_ms=result.get("processingTimeMs"),
        )

    @strawberry.field
    def stats(self, info: Info) -> Stats:
        return _stats_query(_db(info))


schema = strawberry.Schema(query=Query)
