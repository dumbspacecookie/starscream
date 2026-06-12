import uuid
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from starscream.api.geo import point_wkt
from starscream.db.models import LicenseType, Recording, RecorderType, Source, TaxonomyNode
from starscream.pipeline.classify import classify_audio, persist_classifications
from starscream.pipeline.enrich import enrich_metadata
from starscream.pipeline.fingerprint import compute_spectral_hash
from starscream.pipeline.index import index_recording
from starscream.pipeline.validate import validate_recording
from starscream.storage import put_audio


def run_pipeline(
    *,
    db: Session,
    taxonomy_code: str,
    lat: float,
    lng: float,
    recorded_at: datetime,
    license: LicenseType,
    source: Source,
    location_name: str | None = None,
    country_code: str | None = None,
    recorder_type: RecorderType = RecorderType.UNKNOWN,
    external_id: str | None = None,
    external_url: str | None = None,
    audio_bytes: bytes | None = None,
) -> Recording:
    taxonomy = db.get(TaxonomyNode, taxonomy_code)
    if not taxonomy:
        raise HTTPException(status_code=400, detail=f"Unknown taxonomy: {taxonomy_code}")

    validation = validate_recording(
        lat=lat,
        lng=lng,
        recorded_at=recorded_at,
        license=license,
        audio_bytes=audio_bytes,
        external_url=external_url,
    )
    if not validation.ok:
        raise HTTPException(status_code=422, detail=validation.errors)

    spectral_hash = compute_spectral_hash(audio_bytes)
    existing = db.execute(
        select(Recording).where(Recording.spectral_hash == spectral_hash).limit(1)
    ).scalar_one_or_none()
    if existing and audio_bytes:
        return existing

    classification = classify_audio(audio_bytes, taxonomy_code)

    enrichment = enrich_metadata(
        lat=lat,
        lng=lng,
        recorded_at=recorded_at,
        location_name=location_name,
        country_code=country_code,
    )

    recording_id = uuid.uuid4()
    flac_key = None
    if audio_bytes and license not in (LicenseType.POINTER_ONLY, LicenseType.CC_BY_NC):
        flac_key = put_audio(f"flac/{recording_id}.flac", audio_bytes)

    recording = Recording(
        id=recording_id,
        spectral_hash=spectral_hash,
        taxonomy_code=taxonomy_code,
        location=point_wkt(lat, lng),
        recorded_at=recorded_at,
        source_id=source.id,
        license=license,
        location_name=enrichment.location_name,
        country_code=enrichment.country_code,
        season=enrichment.season,
        habitat=enrichment.habitat,
        weather=enrichment.weather,
        temperature_c=enrichment.temperature_c,
        cross_modal_links=enrichment.cross_modal_links,
        recorder_type=recorder_type,
        external_id=external_id,
        external_url=external_url,
        flac_key=flac_key,
        duration_s=validation.duration_s,
    )
    db.add(recording)
    persist_classifications(db, recording_id, classification)

    taxonomy.recording_count += 1
    source.record_count += 1

    db.commit()
    db.refresh(recording)

    index_recording(recording, lat, lng)
    return recording
