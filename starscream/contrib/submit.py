import json
import uuid
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from starscream.api.geo import point_wkt
from starscream.contrib.schema import ContributionManifest
from starscream.contrib.validator import ValidationReport, validate_contribution
from starscream.db.models import Recording, Source, Tag, TaxonomyNode
from starscream.pipeline.audio_convert import normalize_upload
from starscream.pipeline.classify import classify_audio, persist_classifications
from starscream.pipeline.dedup import find_duplicate, link_duplicate
from starscream.pipeline.enrich import enrich_metadata
from starscream.pipeline.fingerprint import compute_spectral_hash
from starscream.pipeline.index import index_recording
from starscream.pipeline.spectrogram import generate_spectrogram
from starscream.events import get_broadcaster, recording_summary_from_recording
from starscream.storage import put_audio, put_spectrogram


def load_manifest(path: Path) -> ContributionManifest:
    data = json.loads(path.read_text(encoding="utf-8"))
    return ContributionManifest.model_validate(data)


def submit_contribution(
    *,
    db: Session,
    manifest: ContributionManifest,
    audio_bytes: bytes,
    strict: bool = True,
) -> tuple[Recording, ValidationReport]:
    """Validate and ingest a user contribution."""
    report = validate_contribution(manifest, audio_bytes, strict=strict)
    if not report.valid:
        raise HTTPException(status_code=422, detail={"errors": report.errors, "warnings": report.warnings})

    source = db.execute(
        select(Source).where(Source.slug == "contributor")
    ).scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=500, detail="contributor source not seeded")

    taxonomy = db.get(TaxonomyNode, manifest.taxonomy_code)
    if not taxonomy:
        raise HTTPException(status_code=400, detail=f"Unknown taxonomy: {manifest.taxonomy_code}")

    lat, lng = manifest.location.lat, manifest.location.lng
    spectral_hash = compute_spectral_hash(audio_bytes)
    existing_canonical = find_duplicate(db, spectral_hash)

    classification = classify_audio(audio_bytes, manifest.taxonomy_code)

    enrichment = enrich_metadata(
        lat=lat,
        lng=lng,
        recorded_at=manifest.recorded_at,
        location_name=manifest.location.name,
        country_code=manifest.location.country_code,
    )

    recording_id = uuid.uuid4()
    flac_bytes, mp3_bytes, audio_meta = normalize_upload(audio_bytes, manifest.audio_filename)
    flac_key = put_audio(f"flac/{recording_id}.flac", flac_bytes)
    mp3_key = None
    if mp3_bytes:
        mp3_key = put_audio(
            f"mp3/{recording_id}.mp3", mp3_bytes, content_type="audio/mpeg"
        )

    spectrogram_key = None
    try:
        png_bytes = generate_spectrogram(audio_bytes)
        spectrogram_key = put_spectrogram(str(recording_id), png_bytes)
    except Exception:
        pass

    world_model_labels = None
    if manifest.physical_properties:
        world_model_labels = manifest.physical_properties.model_dump(exclude_none=True)

    events_json = None
    if manifest.events:
        events_json = [e.model_dump(exclude_none=True) for e in manifest.events]

    scene_graph_json = None
    if manifest.scene_graph:
        scene_graph_json = manifest.scene_graph.model_dump(exclude_none=True)

    recording = Recording(
        id=recording_id,
        spectral_hash=spectral_hash,
        taxonomy_code=manifest.taxonomy_code,
        location=point_wkt(lat, lng),
        recorded_at=manifest.recorded_at,
        source_id=source.id,
        license=manifest.license,
        title=manifest.title,
        description=manifest.description,
        source_object=manifest.source_object,
        source_action=manifest.source_action,
        tags=manifest.tags,
        material=manifest.material,
        environment=manifest.environment.value,
        distance_m=manifest.distance_m,
        mic_orientation=manifest.mic_orientation,
        background_noise_level=(
            manifest.background_noise_level.value if manifest.background_noise_level else None
        ),
        other_sounds_present=manifest.other_sounds_present or None,
        recorder_type=manifest.recorder_type,
        recorder_model=manifest.recorder_model,
        sample_rate_hz=audio_meta.sample_rate or report.detected_sample_rate_hz or manifest.sample_rate_hz,
        channels=audio_meta.channels or report.detected_channels or manifest.channels,
        bit_depth=audio_meta.bit_depth or report.detected_bit_depth or manifest.bit_depth,
        contributor_id=manifest.contributor_id,
        contributor_name=manifest.contributor_name,
        world_model_labels=world_model_labels,
        events=events_json,
        scene_graph=scene_graph_json,
        location_name=enrichment.location_name,
        country_code=enrichment.country_code,
        altitude_m=manifest.location.altitude_m,
        season=enrichment.season,
        habitat=enrichment.habitat,
        cross_modal_links=enrichment.cross_modal_links,
        flac_key=flac_key,
        mp3_key=mp3_key,
        spectrogram_key=spectrogram_key,
        duration_s=audio_meta.duration or report.duration_s,
        is_contribution=True,
    )
    db.add(recording)
    persist_classifications(db, recording_id, classification)
    if existing_canonical:
        link_duplicate(db, recording, existing_canonical)
    _upsert_tags(db, manifest.tags)

    taxonomy.recording_count += 1
    source.record_count += 1
    db.commit()
    db.refresh(recording)

    index_recording(recording, lat, lng)
    get_broadcaster().publish(recording_summary_from_recording(recording, lat, lng))
    return recording, report


def _upsert_tags(db: Session, tags: list[str]) -> None:
    for tag_name in tags:
        tag = db.get(Tag, tag_name)
        if tag:
            tag.usage_count += 1
        else:
            db.add(Tag(name=tag_name, usage_count=1))
