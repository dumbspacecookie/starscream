from dataclasses import dataclass
from datetime import datetime

from starscream.db.models import LicenseType


@dataclass
class ValidationResult:
    ok: bool
    errors: list[str]
    warnings: list[str]
    duration_s: float | None = None


def validate_recording(
    *,
    lat: float,
    lng: float,
    recorded_at: datetime,
    license: LicenseType,
    audio_bytes: bytes | None,
    external_url: str | None,
) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []
    duration_s: float | None = None

    if not (-90 <= lat <= 90):
        errors.append("latitude out of range")
    if not (-180 <= lng <= 180):
        errors.append("longitude out of range")
    if recorded_at.year < 1900:
        errors.append("recorded_at before 1900")
    if license == LicenseType.POINTER_ONLY and not external_url:
        errors.append("pointer-only records require external_url")

    if audio_bytes:
        try:
            import io

            import soundfile as sf

            info = sf.info(io.BytesIO(audio_bytes))
            duration_s = info.duration
            if duration_s < 0.5:
                errors.append("duration under 0.5s minimum")
            if duration_s > 6 * 3600:
                warnings.append("duration exceeds 6h — flagged for review")
        except Exception:
            errors.append("unreadable audio format")
    elif license not in (LicenseType.POINTER_ONLY, LicenseType.CC_BY_NC) and not external_url:
        warnings.append("no audio provided — metadata-only record")

    return ValidationResult(
        ok=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        duration_s=duration_s,
    )
