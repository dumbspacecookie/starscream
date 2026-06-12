import base64
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from geoalchemy2.functions import ST_DWithin, ST_MakePoint, ST_SetSRID
from sqlalchemy import select
from sqlalchemy.orm import Session

from starscream.api.schemas import (
    CanonicalOut,
    ClassificationListOut,
    ClassificationOut,
    RecordingListOut,
    RecordingOut,
    SimilarRecordingsOut,
)
from starscream.api.geo import location_lat, location_lng
from starscream.pipeline.similar import find_similar_recordings
from starscream.db.models import LicenseType, Recording, RecordingClassification, RecorderType, Source
from starscream.db.session import get_db
from starscream.pipeline.dedup import get_canonical_chain
from starscream.pipeline.runner import run_pipeline
from starscream.storage import get_audio_bytes, get_spectrogram_bytes, put_spectrogram

router = APIRouter(prefix="/recordings", tags=["recordings"])


def _recording_out(
    recording: Recording,
    lat: float | None = None,
    lng: float | None = None,
) -> RecordingOut:
    return RecordingOut(
        id=recording.id,
        spectral_hash=recording.spectral_hash,
        taxonomy_code=recording.taxonomy_code,
        location={"lat": lat or 0.0, "lng": lng or 0.0},
        recorded_at=recording.recorded_at,
        source_id=recording.source_id,
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
        canonical_id=recording.canonical_id,
        is_duplicate=recording.is_duplicate,
    )


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        recorded_at_str, id_str = raw.split("|", 1)
        return datetime.fromisoformat(recorded_at_str), uuid.UUID(id_str)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid cursor") from exc


def _encode_cursor(recorded_at: datetime, record_id: uuid.UUID) -> str:
    raw = f"{recorded_at.isoformat()}|{record_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


@router.get("", response_model=RecordingListOut)
def list_recordings(
    near: str | None = Query(None, max_length=64, description="lat,lng"),
    radius_km: float = Query(50, ge=0.1, le=500),
    taxonomy: str | None = Query(None, max_length=64),
    recorded_after: datetime | None = None,
    recorded_before: datetime | None = None,
    season: str | None = Query(None, max_length=32),
    habitat: str | None = Query(None, max_length=128),
    quality_min: int | None = Query(None, ge=1, le=5),
    tag: str | None = Query(None, max_length=64, description="Filter by tag (exact match)"),
    source_object: str | None = Query(
        None, max_length=200, description="Filter by source object (contains)"
    ),
    material: str | None = Query(None, max_length=64),
    environment: str | None = Query(None, max_length=64),
    contributions_only: bool = False,
    limit: int = Query(100, ge=1, le=500),
    cursor: str | None = None,
    db: Session = Depends(get_db),
):
    lat_col = location_lat(Recording.location).label("lat")
    lng_col = location_lng(Recording.location).label("lng")

    stmt = select(Recording, lat_col, lng_col)

    if near:
        try:
            lat_s, lng_s = near.split(",", 1)
            lat, lng = float(lat_s.strip()), float(lng_s.strip())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="near must be lat,lng") from exc
        radius_m = radius_km * 1000
        point = ST_SetSRID(ST_MakePoint(lng, lat), 4326)
        stmt = stmt.where(
            ST_DWithin(Recording.location, point, radius_m, use_spheroid=True)
        )

    if taxonomy:
        stmt = stmt.where(Recording.taxonomy_code.startswith(taxonomy))

    if recorded_after:
        stmt = stmt.where(Recording.recorded_at >= recorded_after)
    if recorded_before:
        stmt = stmt.where(Recording.recorded_at <= recorded_before)
    if season:
        stmt = stmt.where(Recording.season == season)
    if habitat:
        stmt = stmt.where(Recording.habitat == habitat)
    if quality_min:
        stmt = stmt.where(Recording.quality >= quality_min)
    if tag:
        stmt = stmt.where(Recording.tags.contains([tag.lower().replace(" ", "_")]))
    if source_object:
        stmt = stmt.where(Recording.source_object.ilike(f"%{source_object}%"))
    if material:
        stmt = stmt.where(Recording.material == material)
    if environment:
        stmt = stmt.where(Recording.environment == environment)
    if contributions_only:
        stmt = stmt.where(Recording.is_contribution.is_(True))

    if cursor:
        cursor_at, cursor_id = _decode_cursor(cursor)
        stmt = stmt.where(
            (Recording.recorded_at < cursor_at)
            | ((Recording.recorded_at == cursor_at) & (Recording.id < cursor_id))
        )

    stmt = stmt.order_by(Recording.recorded_at.desc(), Recording.id.desc()).limit(limit + 1)
    rows = db.execute(stmt).all()

    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1][0]
        next_cursor = _encode_cursor(last.recorded_at, last.id)
        rows = rows[:limit]

    items = [_recording_out(r, lat, lng) for r, lat, lng in rows]
    return RecordingListOut(items=items, next_cursor=next_cursor)


@router.get("/{recording_id}", response_model=RecordingOut)
def get_recording(recording_id: uuid.UUID, db: Session = Depends(get_db)):
    lat_col = location_lat(Recording.location).label("lat")
    lng_col = location_lng(Recording.location).label("lng")
    row = db.execute(
        select(Recording, lat_col, lng_col).where(Recording.id == recording_id)
    ).one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Recording not found")
    recording, lat, lng = row
    return _recording_out(recording, lat, lng)


@router.get("/{recording_id}/audio.flac")
def get_audio_flac(recording_id: uuid.UUID, db: Session = Depends(get_db)):
    recording = db.get(Recording, recording_id)
    if not recording or not recording.flac_key:
        raise HTTPException(status_code=404, detail="Audio not available")
    data = get_audio_bytes(recording.flac_key)
    if not data:
        raise HTTPException(status_code=404, detail="Audio file missing from storage")
    from fastapi.responses import Response

    return Response(content=data, media_type="audio/flac")


@router.get("/{recording_id}/audio.mp3")
def get_audio_mp3(recording_id: uuid.UUID, db: Session = Depends(get_db)):
    recording = db.get(Recording, recording_id)
    if not recording or not recording.mp3_key:
        raise HTTPException(status_code=404, detail="Audio not available")
    data = get_audio_bytes(recording.mp3_key)
    if not data:
        raise HTTPException(status_code=404, detail="Audio file missing from storage")
    from fastapi.responses import Response

    return Response(content=data, media_type="audio/mpeg")


@router.get("/{recording_id}/canonical", response_model=CanonicalOut)
def get_recording_canonical(recording_id: uuid.UUID, db: Session = Depends(get_db)):
    lat_col = location_lat(Recording.location).label("lat")
    lng_col = location_lng(Recording.location).label("lng")
    row = db.execute(
        select(Recording, lat_col, lng_col).where(Recording.id == recording_id)
    ).one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Recording not found")
    recording, _lat, _lng = row

    canonical, alternates = get_canonical_chain(db, recording)

    canon_row = db.execute(
        select(Recording, lat_col, lng_col).where(Recording.id == canonical.id)
    ).one()
    canon_rec, canon_lat, canon_lng = canon_row

    alt_items: list[RecordingOut] = []
    if alternates:
        alt_ids = [a.id for a in alternates]
        alt_rows = db.execute(
            select(Recording, lat_col, lng_col).where(Recording.id.in_(alt_ids))
        ).all()
        alt_by_id = {r.id: (r, lat, lng) for r, lat, lng in alt_rows}
        alt_items = [
            _recording_out(alt_by_id[a.id][0], alt_by_id[a.id][1], alt_by_id[a.id][2])
            for a in alternates
            if a.id in alt_by_id
        ]

    return CanonicalOut(
        recording_id=recording_id,
        canonical=_recording_out(canon_rec, canon_lat, canon_lng),
        alternates=alt_items,
    )


@router.get("/{recording_id}/similar", response_model=SimilarRecordingsOut)
def get_similar_recordings(
    recording_id: uuid.UUID,
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    recording = db.get(Recording, recording_id)
    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")

    matches = find_similar_recordings(db, recording, limit=limit)
    items = [_recording_out(rec, lat, lng) for rec, lat, lng, _score in matches]
    return SimilarRecordingsOut(
        recording_id=recording_id,
        items=items,
        total=len(items),
    )


@router.get("/{recording_id}/classifications", response_model=ClassificationListOut)
def get_recording_classifications(recording_id: uuid.UUID, db: Session = Depends(get_db)):
    recording = db.get(Recording, recording_id)
    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")

    rows = db.scalars(
        select(RecordingClassification)
        .where(RecordingClassification.recording_id == recording_id)
        .order_by(RecordingClassification.confidence.desc())
    ).all()

    return ClassificationListOut(
        recording_id=recording_id,
        items=[ClassificationOut.model_validate(row) for row in rows],
    )


@router.get("/{recording_id}/spectrogram.png")
def get_spectrogram(recording_id: uuid.UUID, db: Session = Depends(get_db)):
    from fastapi.responses import Response

    from starscream.pipeline.spectrogram import generate_spectrogram

    recording = db.get(Recording, recording_id)
    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")

    if recording.spectrogram_key:
        data = get_spectrogram_bytes(recording.spectrogram_key)
        if data:
            return Response(content=data, media_type="image/png")

    audio_bytes = None
    if recording.flac_key:
        audio_bytes = get_audio_bytes(recording.flac_key)
    elif recording.mp3_key:
        audio_bytes = get_audio_bytes(recording.mp3_key)

    if not audio_bytes:
        raise HTTPException(status_code=404, detail="No audio available for spectrogram")

    try:
        png_bytes = generate_spectrogram(audio_bytes)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Spectrogram generation failed: {exc}"
        ) from exc

    key = put_spectrogram(str(recording_id), png_bytes)
    if key:
        recording.spectrogram_key = key
        db.commit()

    return Response(content=png_bytes, media_type="image/png")


@router.post("", response_model=RecordingOut, status_code=201)
async def ingest_recording(
    taxonomy_code: str = Form(...),
    lat: float = Form(...),
    lng: float = Form(...),
    recorded_at: datetime = Form(...),
    license: LicenseType = Form(LicenseType.CC0),
    source_slug: str = Form("contributor"),
    location_name: str | None = Form(None),
    country_code: str | None = Form(None),
    recorder_type: RecorderType = Form(RecorderType.UNKNOWN),
    external_id: str | None = Form(None),
    external_url: str | None = Form(None),
    audio: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    source = db.execute(
        select(Source).where(Source.slug == source_slug)
    ).scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=400, detail=f"Unknown source: {source_slug}")

    audio_bytes = await audio.read() if audio else None
    recording = run_pipeline(
        db=db,
        taxonomy_code=taxonomy_code,
        lat=lat,
        lng=lng,
        recorded_at=recorded_at,
        license=license,
        source=source,
        location_name=location_name,
        country_code=country_code,
        recorder_type=recorder_type,
        external_id=external_id,
        external_url=external_url,
        audio_bytes=audio_bytes,
    )
    return _recording_out(recording, lat, lng)
