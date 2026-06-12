import io
from dataclasses import dataclass, field
from pathlib import Path

import soundfile as sf

from starscream.contrib.schema import ContributionManifest, EnvironmentType, SoundEvent

MIN_SAMPLE_RATE = 44100
MIN_BIT_DEPTH = 16
MIN_DURATION_S = 0.5
MAX_DURATION_S = 6 * 3600
REJECTED_AUDIO_EXTENSIONS = {".mp3", ".m4a", ".aac", ".ogg", ".opus", ".wma"}


@dataclass
class ValidationReport:
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    duration_s: float | None = None
    detected_sample_rate_hz: int | None = None
    detected_channels: int | None = None
    detected_bit_depth: int | None = None


def validate_contribution(
    manifest: ContributionManifest,
    audio_bytes: bytes | None = None,
    *,
    strict: bool = True,
) -> ValidationReport:
    """Validate a contribution manifest and optional paired raw audio."""
    errors: list[str] = []
    warnings: list[str] = []
    duration_s: float | None = None
    detected_sr: int | None = None
    detected_ch: int | None = None
    detected_bd: int | None = None

    # Manifest field quality checks
    if len(manifest.title.split()) < 2:
        warnings.append("title should be descriptive (at least two words)")

    if not manifest.tags:
        warnings.append("add tags to improve discoverability for researchers and models")

    if manifest.physical_properties is None:
        if strict:
            errors.append("physical_properties required — world models need structured grounding labels")
        else:
            warnings.append("physical_properties strongly recommended for world model training")

    if manifest.description is None:
        warnings.append("description recommended: explain recording context and mic placement")

    if manifest.taxonomy_code == "NATURAL":
        warnings.append("taxonomy_code should be more specific than NATURAL when possible")

    if not manifest.material:
        warnings.append("material field helps models link sound to physical substance")

    if manifest.environment == EnvironmentType.UNKNOWN:
        warnings.append("specify environment (indoor/outdoor/etc.) for spatial grounding")

    # Audio validation
    if audio_bytes is None:
        errors.append("raw audio file is required for contributions")
    else:
        ext = Path(manifest.audio_filename).suffix.lower()
        if ext in REJECTED_AUDIO_EXTENSIONS:
            errors.append(f"lossy format {ext} rejected — contribute raw WAV/FLAC only")

        try:
            info = sf.info(io.BytesIO(audio_bytes))
            duration_s = info.duration
            detected_sr = info.samplerate
            detected_ch = info.channels
            detected_bd = _subtype_bit_depth(info.subtype)

            if duration_s < MIN_DURATION_S:
                errors.append(f"duration {duration_s:.2f}s under {MIN_DURATION_S}s minimum")
            if duration_s > MAX_DURATION_S:
                warnings.append(f"duration {duration_s:.0f}s exceeds 6h — flagged for review")

            if detected_sr < MIN_SAMPLE_RATE:
                errors.append(
                    f"sample rate {detected_sr} Hz below {MIN_SAMPLE_RATE} Hz minimum — "
                    "record at 44.1 kHz or higher"
                )
            if detected_bd and detected_bd < MIN_BIT_DEPTH:
                warnings.append(
                    f"bit depth {detected_bd} below {MIN_BIT_DEPTH}-bit recommended minimum"
                )

            if manifest.sample_rate_hz and manifest.sample_rate_hz != detected_sr:
                warnings.append(
                    f"manifest sample_rate_hz ({manifest.sample_rate_hz}) "
                    f"differs from file ({detected_sr})"
                )
        except Exception:
            errors.append("unreadable audio — provide uncompressed WAV or FLAC")

    _validate_scene_events(manifest, duration_s, errors)

    return ValidationReport(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        duration_s=duration_s,
        detected_sample_rate_hz=detected_sr,
        detected_channels=detected_ch,
        detected_bit_depth=detected_bd,
    )


def _validate_scene_events(
    manifest: ContributionManifest,
    duration_s: float | None,
    errors: list[str],
) -> None:
    """Validate timed events and entity references in manifest scene data."""
    entity_ids: set[str] = set()
    if manifest.scene_graph:
        entity_ids = {e.id for e in manifest.scene_graph.entities}
        _check_events(
            manifest.scene_graph.events,
            entity_ids,
            duration_s,
            "scene_graph.events",
            errors,
        )

    if manifest.events:
        _check_events(manifest.events, entity_ids, duration_s, "events", errors)


def _check_events(
    events: list[SoundEvent],
    entity_ids: set[str],
    duration_s: float | None,
    prefix: str,
    errors: list[str],
) -> None:
    for i, event in enumerate(events):
        if duration_s is not None:
            if event.t_start_s > duration_s:
                errors.append(
                    f"{prefix}[{i}]: t_start_s {event.t_start_s:.3f}s exceeds "
                    f"audio duration {duration_s:.3f}s"
                )
            if event.t_end_s > duration_s:
                errors.append(
                    f"{prefix}[{i}]: t_end_s {event.t_end_s:.3f}s exceeds "
                    f"audio duration {duration_s:.3f}s"
                )
        if event.entity_id and event.entity_id not in entity_ids:
            errors.append(
                f"{prefix}[{i}]: entity_id '{event.entity_id}' not found in scene_graph.entities"
            )


def _subtype_bit_depth(subtype: str) -> int | None:
    mapping = {
        "PCM_16": 16,
        "PCM_24": 24,
        "PCM_32": 32,
        "PCM_U8": 8,
        "FLOAT": 32,
        "DOUBLE": 64,
    }
    return mapping.get(subtype.upper().replace(" ", "_"))
