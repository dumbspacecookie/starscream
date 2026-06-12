import uuid
from datetime import timezone

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from starscream.api.geo import point_wkt
from starscream.db.models import LicenseType, RecorderType, Recording, SensorNode, Source, TaxonomyNode
from starscream.pipeline.audio_convert import normalize_upload
from starscream.pipeline.classify import classify_audio, persist_classifications
from starscream.pipeline.dedup import find_duplicate, link_duplicate
from starscream.pipeline.enrich import enrich_metadata
from starscream.pipeline.fingerprint import compute_spectral_hash
from starscream.pipeline.index import index_recording
from starscream.pipeline.spectrogram import generate_spectrogram
from starscream.sensor.mqtt_handler import DEFAULT_TAXONOMY, MqttSensorPayload, decode_audio_base64
from starscream.storage import put_audio, put_spectrogram

IOT_SOURCE_SLUG = "iot-sensor"


class SensorEventIn(MqttSensorPayload):
    """HTTP ingest accepts the same shape as MQTT payloads."""


def _get_or_create_iot_source(db: Session) -> Source:
    source = db.execute(select(Source).where(Source.slug == IOT_SOURCE_SLUG)).scalar_one_or_none()
    if source:
        return source

    source = Source(
        id=uuid.uuid4(),
        name="IoT Sensor Network",
        slug=IOT_SOURCE_SLUG,
        url=None,
        license_default=LicenseType.CC0,
    )
    db.add(source)
    db.flush()
    return source


def resolve_audio_bytes(
    event: SensorEventIn,
    uploaded_audio: bytes | None,
) -> bytes:
    if uploaded_audio:
        return uploaded_audio
    if event.audio_base64:
        return decode_audio_base64(event.audio_base64)
    if event.audio_url:
        try:
            response = httpx.get(event.audio_url, timeout=30.0, follow_redirects=True)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=400, detail=f"Failed to fetch audio_url: {exc}") from exc
        return response.content

    raise HTTPException(
        status_code=400,
        detail="Provide audio file upload, audio_url, or audio_base64",
    )


def submit_sensor_event(
    *,
    db: Session,
    event: SensorEventIn,
    audio_bytes: bytes,
    node: SensorNode | None = None,
) -> Recording:
    if node and event.node_id != node.node_id:
        raise HTTPException(status_code=403, detail="node_id does not match authenticated node token")

    registered = db.get(SensorNode, event.node_id)
    if not registered:
        raise HTTPException(status_code=404, detail=f"Unknown sensor node: {event.node_id}")
    if not registered.is_active:
        raise HTTPException(status_code=403, detail=f"Sensor node inactive: {event.node_id}")

    taxonomy_code = event.taxonomy_code or DEFAULT_TAXONOMY
    taxonomy = db.get(TaxonomyNode, taxonomy_code)
    if not taxonomy:
        raise HTTPException(status_code=400, detail=f"Unknown taxonomy: {taxonomy_code}")

    source = _get_or_create_iot_source(db)
    lat = registered.lat
    lng = registered.lng
    recorded_at = event.recorded_at
    if recorded_at.tzinfo is None:
        recorded_at = recorded_at.replace(tzinfo=timezone.utc)

    spectral_hash = compute_spectral_hash(audio_bytes)
    existing_canonical = find_duplicate(db, spectral_hash)
    classification = classify_audio(audio_bytes, taxonomy_code)
    enrichment = enrich_metadata(
        lat=lat,
        lng=lng,
        recorded_at=recorded_at,
        location_name=None,
        country_code=None,
    )

    recording_id = uuid.uuid4()
    flac_bytes, mp3_bytes, audio_meta = normalize_upload(audio_bytes, f"{event.node_id}.wav")
    flac_key = put_audio(f"flac/{recording_id}.flac", flac_bytes)
    mp3_key = None
    if mp3_bytes:
        mp3_key = put_audio(f"mp3/{recording_id}.mp3", mp3_bytes, content_type="audio/mpeg")

    spectrogram_key = None
    try:
        png_bytes = generate_spectrogram(audio_bytes)
        spectrogram_key = put_spectrogram(str(recording_id), png_bytes)
    except Exception:
        pass

    title = event.title or f"IoT event from {event.node_id}"
    recording = Recording(
        id=recording_id,
        spectral_hash=spectral_hash,
        taxonomy_code=taxonomy_code,
        location=point_wkt(lat, lng),
        recorded_at=recorded_at,
        source_id=source.id,
        license=LicenseType.CC0,
        title=title,
        description=event.description,
        source_object=f"sensor node {event.node_id}",
        source_action="acoustic event detection",
        tags=["iot", "sensor"],
        recorder_type=RecorderType.IOT,
        recorder_model=event.node_id,
        sample_rate_hz=event.sample_rate_hz or audio_meta.sample_rate,
        channels=audio_meta.channels,
        bit_depth=audio_meta.bit_depth,
        contributor_id=event.node_id,
        contributor_name=f"node:{event.node_id}",
        external_id=f"{event.node_id}:{int(recorded_at.timestamp())}",
        flac_key=flac_key,
        mp3_key=mp3_key,
        spectrogram_key=spectrogram_key,
        duration_s=event.duration_s or audio_meta.duration,
        location_name=enrichment.location_name,
        country_code=enrichment.country_code,
        season=enrichment.season,
        habitat=enrichment.habitat,
        cross_modal_links=enrichment.cross_modal_links,
        world_model_labels=event.metadata or None,
        is_contribution=False,
    )
    db.add(recording)
    persist_classifications(db, recording_id, classification)
    if existing_canonical:
        link_duplicate(db, recording, existing_canonical)

    taxonomy.recording_count += 1
    source.record_count += 1
    registered.last_seen_at = recorded_at
    registered.event_count += 1
    db.commit()
    db.refresh(recording)

    index_recording(recording, lat, lng)
    return recording
