import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from starscream.api.geo import point_wkt
from starscream.config import get_settings
from starscream.db.models import LicenseType, Recording, Source
from starscream.federation.base import FederatedRecord
from starscream.federation.grounding import infer_minimal_world_model_labels, maybe_ground_record
from starscream.pipeline.audio_convert import is_mp3, normalize_upload, reencode_mp3_proxy
from starscream.pipeline.classify import classify_audio, persist_classifications
from starscream.pipeline.dedup import find_duplicate, link_cross_source_duplicates, link_duplicate
from starscream.pipeline.enrich import enrich_metadata
from starscream.pipeline.fingerprint import compute_spectral_hash
from starscream.pipeline.index import index_recording
from starscream.pipeline.spectrogram import generate_spectrogram
from starscream.events import get_broadcaster, recording_summary_from_recording
from starscream.storage import put_audio, put_spectrogram

logger = logging.getLogger(__name__)


def _map_license(license_str: str) -> LicenseType:
    mapping = {
        "CC0": LicenseType.CC0,
        "CC-BY": LicenseType.CC_BY,
        "CC-BY-NC": LicenseType.CC_BY_NC,
        "PUBLIC_DOMAIN": LicenseType.PUBLIC_DOMAIN,
    }
    return mapping.get(license_str, LicenseType.POINTER_ONLY)


@dataclass
class IngestResult:
    created: int
    skipped: int
    failed: int
    errors: list[str]


def ingest_federated_records(
    db: Session,
    source: Source,
    records: list[FederatedRecord],
    *,
    download_audio: bool | None = None,
) -> IngestResult:
    if download_audio is None:
        download_audio = not get_settings().catalog_only
    created = skipped = failed = 0
    errors: list[str] = []

    for record in records:
        existing = db.execute(
            select(Recording).where(
                Recording.source_id == source.id,
                Recording.external_id == record.external_id,
            )
        ).scalar_one_or_none()
        if existing:
            skipped += 1
            continue

        license = _map_license(record.license)
        if record.license == "CC-BY-NC" or license == LicenseType.CC_BY_NC:
            logger.warning(
                "CC-BY-NC record %s from %s: pointer-only storage (no local audio)",
                record.external_id,
                source.slug,
            )
            license = LicenseType.POINTER_ONLY

        try:
            with db.begin_nested():
                recording_id = uuid.uuid4()
                flac_key = None
                mp3_key = None
                spectrogram_key = None
                audio_bytes: bytes | None = None
                if license not in (LicenseType.POINTER_ONLY, LicenseType.CC_BY_NC):
                    audio_bytes = getattr(record, "_preview_bytes", None)

                if download_audio and audio_bytes:
                    if is_mp3(audio_bytes):
                        mp3_data = reencode_mp3_proxy(audio_bytes) or audio_bytes
                        mp3_key = put_audio(
                            f"mp3/{recording_id}.mp3", mp3_data, content_type="audio/mpeg"
                        )
                    else:
                        flac_bytes, mp3_bytes, _meta = normalize_upload(
                            audio_bytes, f"{record.external_id}.wav"
                        )
                        flac_key = put_audio(f"flac/{recording_id}.flac", flac_bytes)
                        if mp3_bytes:
                            mp3_key = put_audio(
                                f"mp3/{recording_id}.mp3", mp3_bytes, content_type="audio/mpeg"
                            )

                    try:
                        png_bytes = generate_spectrogram(audio_bytes)
                        spectrogram_key = put_spectrogram(str(recording_id), png_bytes)
                    except Exception:
                        pass

                spectral_hash = compute_spectral_hash(audio_bytes)
                existing_canonical = find_duplicate(db, spectral_hash)

                enrichment = enrich_metadata(
                    lat=record.lat,
                    lng=record.lng,
                    recorded_at=record.recorded_at,
                    location_name=None,
                    country_code=None,
                )
                classification = classify_audio(audio_bytes, record.taxonomy_code)

                source_object, source_action = maybe_ground_record(
                    record.source_object,
                    record.source_action,
                    title=record.title,
                    tags=record.tags or [],
                )
                wm_labels = infer_minimal_world_model_labels(
                    record.taxonomy_code, source_object, source_action
                )

                rec = Recording(
                    id=recording_id,
                    spectral_hash=spectral_hash,
                    taxonomy_code=record.taxonomy_code,
                    location=point_wkt(record.lat, record.lng),
                    recorded_at=record.recorded_at,
                    source_id=source.id,
                    license=license,
                    title=record.title,
                    description=record.description,
                    source_object=source_object,
                    source_action=source_action,
                    world_model_labels=wm_labels,
                    tags=record.tags or None,
                    location_name=enrichment.location_name,
                    country_code=enrichment.country_code,
                    season=enrichment.season,
                    habitat=enrichment.habitat,
                    weather=enrichment.weather,
                    temperature_c=enrichment.temperature_c,
                    cross_modal_links=enrichment.cross_modal_links,
                    external_id=record.external_id,
                    external_url=record.external_url,
                    flac_key=flac_key,
                    mp3_key=mp3_key,
                    spectrogram_key=spectrogram_key,
                    duration_s=record.duration_s,
                    is_contribution=False,
                )
                db.add(rec)
                persist_classifications(db, recording_id, classification)
                db.flush()
                if existing_canonical:
                    link_duplicate(db, rec, existing_canonical)
                link_cross_source_duplicates(db, rec)
                index_recording(rec, record.lat, record.lng)
                get_broadcaster().publish(
                    recording_summary_from_recording(rec, record.lat, record.lng)
                )
            created += 1
        except Exception as exc:
            failed += 1
            errors.append(f"{record.external_id}: {exc}")

    if created:
        source.record_count += created
    db.commit()
    return IngestResult(created=created, skipped=skipped, failed=failed, errors=errors)
