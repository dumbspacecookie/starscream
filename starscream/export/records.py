from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from starscream.api.geo import location_lat, location_lng
from starscream.db.models import Recording


def fetch_recordings(
    db: Session,
    *,
    contributions_only: bool = False,
    with_audio_only: bool = True,
    limit: int | None = None,
) -> list[tuple[Recording, float, float]]:
    lat_col = location_lat(Recording.location).label("lat")
    lng_col = location_lng(Recording.location).label("lng")
    stmt = (
        select(Recording, lat_col, lng_col)
        .options(joinedload(Recording.source))
        .order_by(Recording.recorded_at.desc())
    )

    if contributions_only:
        stmt = stmt.where(Recording.is_contribution.is_(True))
    if with_audio_only:
        stmt = stmt.where(Recording.flac_key.isnot(None))
    if limit:
        stmt = stmt.limit(limit)

    return list(db.execute(stmt).all())


def recording_to_row(recording: Recording, lat: float, lng: float, audio_path: str | None, split: str) -> dict:
    wm = recording.world_model_labels or {}
    cm = getattr(recording, "cross_modal_links", None) or {}
    source = getattr(recording, "source", None)
    source_slug = source.slug if source else None
    return {
        "id": str(recording.id),
        "audio": audio_path,
        "has_audio": bool(getattr(recording, "flac_key", None) or getattr(recording, "mp3_key", None)),
        "external_id": getattr(recording, "external_id", None),
        "external_url": getattr(recording, "external_url", None),
        "source_slug": source_slug,
        "title": recording.title,
        "description": recording.description,
        "source_object": recording.source_object,
        "source_action": recording.source_action,
        "taxonomy_code": recording.taxonomy_code,
        "tags": recording.tags or [],
        "material": recording.material,
        "environment": recording.environment,
        "lat": lat,
        "lng": lng,
        "location_name": recording.location_name,
        "country_code": recording.country_code,
        "altitude_m": recording.altitude_m,
        "recorded_at": recording.recorded_at.isoformat(),
        "season": recording.season.value if recording.season else None,
        "habitat": recording.habitat,
        "license": recording.license.value,
        "duration_s": recording.duration_s,
        "sample_rate_hz": recording.sample_rate_hz,
        "channels": recording.channels,
        "bit_depth": recording.bit_depth,
        "recorder_type": recording.recorder_type.value,
        "recorder_model": recording.recorder_model,
        "contributor_id": recording.contributor_id,
        "contributor_name": recording.contributor_name,
        "spectral_hash": recording.spectral_hash,
        "is_contribution": recording.is_contribution,
        "world_model_labels": wm,
        "events": getattr(recording, "events", None) or [],
        "scene_graph": getattr(recording, "scene_graph", None),
        "wm_object_category": wm.get("object_category"),
        "wm_interaction_type": wm.get("interaction_type"),
        "wm_estimated_size": wm.get("estimated_size"),
        "wm_force_level": wm.get("force_level"),
        "wm_repeatability": wm.get("repeatability"),
        "wm_material_state": wm.get("material_state"),
        "cross_modal_links": cm or None,
        "osm_primary_type": cm.get("osm_primary_type"),
        "osm_primary_name": cm.get("osm_primary_name"),
        "split": split,
    }
