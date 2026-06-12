import json

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from starscream.api.auth import create_contributor, get_request_contributor
from starscream.api.schemas import (
    BatchItemResult,
    BatchUploadOut,
    BatchValidateOut,
    ContributionJobAcceptedOut,
    ContributionJobStatusOut,
    ContributionOut,
    ContributionValidateOut,
    ContributorRegisterIn,
    ContributorRegisterOut,
    GuidelinesOut,
    RecordingOut,
    TagOut,
)
from starscream.api.geo import location_lat, location_lng
from starscream.jobs.pipeline_jobs import enqueue_contribution_job, get_job_status
from starscream.contrib.batch import packages_from_zip, validate_packages
from starscream.contrib.schema import ContributionManifest
from starscream.contrib.submit import submit_contribution
from starscream.contrib.validator import validate_contribution
from starscream.db.models import Contributor, Recording, Tag
from starscream.db.session import get_db

router = APIRouter(prefix="/contrib", tags=["contributions"])

GUIDELINES_SUMMARY = {
    "mission": (
        "Starscream builds a grounded acoustic corpus so transformers and world models "
        "can learn physical causality — what objects sound like, what actions produce, "
        "and where on Earth they occur."
    ),
    "audio_requirements": {
        "format": "Lossless raw audio only: WAV, FLAC, or AIFF",
        "sample_rate": "Minimum 44.1 kHz (48 kHz or 96 kHz preferred)",
        "bit_depth": "Minimum 16-bit (24-bit preferred)",
        "processing": "No compression, EQ, noise reduction, or normalization — submit the raw capture",
        "duration": "0.5 seconds to 6 hours per clip",
        "pairing": "Every audio file must ship with a manifest.json sidecar",
    },
    "required_metadata": [
        "title — short descriptive name",
        "source_object — what produced the sound (noun)",
        "source_action — what happened (verb phrase)",
        "recorded_at — exact UTC timestamp",
        "location — lat/lng (+ place name and country when known)",
        "license — CC0 or CC-BY only",
        "audio_filename — paired raw file name",
        "physical_properties — structured labels for world model grounding",
    ],
    "recommended_metadata": [
        "taxonomy_code, description, tags",
        "material, environment, distance_m, mic_orientation",
        "background_noise_level, other_sounds_present",
        "recorder_type, recorder_model, sample_rate_hz",
    ],
    "license": "Contributions must be CC0 or CC-BY. No NC, no ND.",
    "docs": "/docs/CONTRIBUTING.md",
    "manifest_schema": "starscream.contrib.schema.ContributionManifest",
    "cli": "starscream-contrib init | validate | upload | validate-batch | upload-batch",
}


def _recording_out(recording: Recording, lat: float, lng: float) -> RecordingOut:
    return RecordingOut(
        id=recording.id,
        spectral_hash=recording.spectral_hash,
        taxonomy_code=recording.taxonomy_code,
        location={"lat": lat, "lng": lng},
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
        location_name=recording.location_name,
        country_code=recording.country_code,
        altitude_m=recording.altitude_m,
        season=recording.season,
        habitat=recording.habitat,
        weather=recording.weather,
        temperature_c=recording.temperature_c,
        recorder_type=recording.recorder_type,
        recorder_model=recording.recorder_model,
        sample_rate_hz=recording.sample_rate_hz,
        channels=recording.channels,
        bit_depth=recording.bit_depth,
        contributor_id=recording.contributor_id,
        contributor_name=recording.contributor_name,
        quality=recording.quality,
        review_status=recording.review_status,
        external_id=recording.external_id,
        external_url=recording.external_url,
        duration_s=recording.duration_s,
        is_contribution=recording.is_contribution,
        has_audio=recording.flac_key is not None,
        canonical_id=recording.canonical_id,
        is_duplicate=recording.is_duplicate,
    )


@router.get("/guidelines", response_model=GuidelinesOut)
def get_guidelines():
    return GuidelinesOut(**GUIDELINES_SUMMARY)


@router.post("/register", response_model=ContributorRegisterOut, status_code=201)
def register_contributor(
    body: ContributorRegisterIn,
    db: Session = Depends(get_db),
):
    if body.github_username:
        existing = db.execute(
            select(Contributor).where(Contributor.github_username == body.github_username)
        ).scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"GitHub username already registered: {body.github_username}",
            )

    contributor, api_key = create_contributor(
        db, body.display_name, body.github_username
    )
    db.commit()

    return ContributorRegisterOut(
        contributor_id=contributor.id,
        display_name=contributor.display_name,
        api_key=api_key,
    )


@router.post("/validate", response_model=ContributionValidateOut)
async def validate_manifest(
    manifest_json: str = Form(..., description="ContributionManifest JSON"),
    audio: UploadFile | None = File(None),
):
    try:
        manifest = ContributionManifest.model_validate(json.loads(manifest_json))
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    audio_bytes = await audio.read() if audio else None
    report = validate_contribution(manifest, audio_bytes, strict=True)
    return ContributionValidateOut(
        valid=report.valid,
        errors=report.errors,
        warnings=report.warnings,
        duration_s=report.duration_s,
        detected_sample_rate_hz=report.detected_sample_rate_hz,
        detected_channels=report.detected_channels,
        detected_bit_depth=report.detected_bit_depth,
    )


@router.post("/upload", response_model=ContributionOut | ContributionJobAcceptedOut)
def upload_contribution(
    request: Request,
    response: Response,
    manifest_json: str = Form(..., description="ContributionManifest JSON"),
    audio: UploadFile = File(..., description="Raw WAV/FLAC audio"),
    async_mode: bool = Query(False, alias="async", description="Enqueue upload as background job"),
    db: Session = Depends(get_db),
):
    try:
        manifest = ContributionManifest.model_validate(json.loads(manifest_json))
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if manifest.audio_filename != audio.filename:
        raise HTTPException(
            status_code=400,
            detail=f"audio filename must match manifest audio_filename ({manifest.audio_filename})",
        )

    audio_bytes = audio.file.read()

    contributor = get_request_contributor(request)
    if contributor:
        manifest = manifest.model_copy(
            update={
                "contributor_id": str(contributor.id),
                "contributor_name": contributor.display_name,
            }
        )

    if async_mode:
        job_id = enqueue_contribution_job(db=db, manifest=manifest, audio_bytes=audio_bytes)
        return JSONResponse(
            status_code=202,
            content=ContributionJobAcceptedOut(job_id=job_id, status="pending").model_dump(
                mode="json"
            ),
        )

    recording, report = submit_contribution(
        db=db, manifest=manifest, audio_bytes=audio_bytes, strict=True
    )

    lat_col = location_lat(Recording.location).label("lat")
    lng_col = location_lng(Recording.location).label("lng")
    row = db.execute(
        select(Recording, lat_col, lng_col).where(Recording.id == recording.id)
    ).one()

    response.status_code = 201
    return ContributionOut(
        recording=_recording_out(row[0], row[1], row[2]),
        warnings=report.warnings,
    )


@router.get("/jobs/{job_id}", response_model=ContributionJobStatusOut)
def get_contribution_job(job_id: UUID, db: Session = Depends(get_db)):
    view = get_job_status(db, job_id)
    if not view:
        raise HTTPException(status_code=404, detail="Job not found")

    recording_out = None
    if view.recording is not None and view.lat is not None and view.lng is not None:
        recording_out = _recording_out(view.recording, view.lat, view.lng)

    return ContributionJobStatusOut(
        job_id=view.job_id,
        status=view.status,
        kind=view.kind,
        error=view.error,
        warnings=view.warnings,
        recording=recording_out,
    )


@router.post("/validate-batch", response_model=BatchValidateOut)
async def validate_batch_zip(
    archive: UploadFile = File(..., description="ZIP of contribution packages"),
):
    data = await archive.read()
    packages, tmp = packages_from_zip(data)
    try:
        validations = validate_packages(packages, strict=True)
        results = []
        valid = 0
        for v in validations:
            ok = v.report.valid
            if ok:
                valid += 1
            results.append(
                BatchItemResult(
                    manifest_path=str(v.package.manifest_path),
                    title=v.package.manifest.title,
                    status="valid" if ok else "invalid",
                    errors=v.report.errors,
                    warnings=v.report.warnings,
                )
            )
        return BatchValidateOut(
            total=len(results),
            valid=valid,
            invalid=len(results) - valid,
            results=results,
        )
    finally:
        tmp.cleanup()


@router.post("/upload-batch", response_model=BatchUploadOut, status_code=201)
def upload_batch_zip(
    archive: UploadFile = File(..., description="ZIP of contribution packages"),
    db: Session = Depends(get_db),
):
    data = archive.file.read()
    packages, tmp = packages_from_zip(data)
    try:
        validations = validate_packages(packages, strict=True)
        results: list[BatchItemResult] = []
        uploaded = failed = skipped = 0

        for v in validations:
            if not v.report.valid:
                failed += 1
                results.append(
                    BatchItemResult(
                        manifest_path=str(v.package.manifest_path),
                        title=v.package.manifest.title,
                        status="failed",
                        errors=v.report.errors,
                        warnings=v.report.warnings,
                    )
                )
                continue

            if not v.package.audio_path.exists():
                failed += 1
                results.append(
                    BatchItemResult(
                        manifest_path=str(v.package.manifest_path),
                        title=v.package.manifest.title,
                        status="failed",
                        errors=[f"audio not found: {v.package.manifest.audio_filename}"],
                    )
                )
                continue

            try:
                recording, report = submit_contribution(
                    db=db,
                    manifest=v.package.manifest,
                    audio_bytes=v.package.audio_path.read_bytes(),
                    strict=True,
                )
                uploaded += 1
                results.append(
                    BatchItemResult(
                        manifest_path=str(v.package.manifest_path),
                        title=v.package.manifest.title,
                        status="uploaded",
                        recording_id=str(recording.id),
                        warnings=report.warnings,
                    )
                )
            except Exception as exc:
                failed += 1
                detail = exc.detail if hasattr(exc, "detail") else str(exc)
                errors = detail if isinstance(detail, list) else [str(detail)]
                results.append(
                    BatchItemResult(
                        manifest_path=str(v.package.manifest_path),
                        title=v.package.manifest.title,
                        status="failed",
                        errors=errors,
                    )
                )

        return BatchUploadOut(
            total=len(results),
            uploaded=uploaded,
            failed=failed,
            skipped=skipped,
            results=results,
        )
    finally:
        tmp.cleanup()


@router.get("/tags", response_model=list[TagOut])
def list_tags(
    q: str | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    stmt = select(Tag).order_by(Tag.usage_count.desc()).limit(limit)
    if q:
        stmt = stmt.where(Tag.name.contains(q.lower().replace(" ", "_")))
    return db.execute(stmt).scalars().all()
