"""Canonical metadata schema for user-contributed sounds.

Designed to ground transformer and world models in physical reality:
every recording links raw audio to what produced it, what action caused it,
where it happened, and structured physical properties.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator

from starscream.db.models import LicenseType, RecorderType


class EnvironmentType(str, Enum):
    INDOOR = "indoor"
    OUTDOOR = "outdoor"
    UNDERWATER = "underwater"
    VEHICLE = "vehicle"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class NoiseLevel(str, Enum):
    SILENT = "silent"
    QUIET = "quiet"
    MODERATE = "moderate"
    NOISY = "noisy"


class LocationSpec(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)
    name: str | None = Field(None, description="Human-readable place name")
    country_code: str | None = Field(None, min_length=2, max_length=2)
    altitude_m: float | None = None


class SoundEvent(BaseModel):
    """Timed sound event within a recording, optionally linked to a scene entity."""

    t_start_s: float = Field(..., ge=0, description="Start time in seconds from clip beginning")
    t_end_s: float = Field(..., ge=0, description="End time in seconds from clip beginning")
    source_object: str = Field(..., min_length=2, max_length=256)
    source_action: str = Field(..., min_length=2, max_length=256)
    entity_id: str | None = Field(
        None, description="Optional reference to a SceneEntity.id in scene_graph"
    )

    @model_validator(mode="after")
    def end_after_start(self) -> "SoundEvent":
        if self.t_end_s <= self.t_start_s:
            raise ValueError("t_end_s must be greater than t_start_s")
        return self


class SceneEntity(BaseModel):
    """Named object in the acoustic scene graph."""

    id: str = Field(..., min_length=1, max_length=64)
    label: str = Field(..., min_length=1, max_length=256)
    category: str = Field(..., min_length=1, max_length=128)
    material: str | None = Field(None, max_length=64)


class SceneGraph(BaseModel):
    """Structured scene: entities present and timed events referencing them."""

    entities: list[SceneEntity] = Field(default_factory=list)
    events: list[SoundEvent] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_entity_ids(self) -> "SceneGraph":
        ids = [e.id for e in self.entities]
        if len(ids) != len(set(ids)):
            raise ValueError("scene_graph entity ids must be unique")
        return self


class PhysicalProperties(BaseModel):
    """Structured labels for grounding world models in physical causality."""

    object_category: str = Field(
        ...,
        description="Broad category: furniture, wildlife, weather, vehicle, tool, body, fluid",
    )
    interaction_type: str = Field(
        ...,
        description="How sound was produced: impact, friction, vibration, vocalization, flow, resonance",
    )
    estimated_size: str | None = Field(
        None, description="Relative scale: tiny, small, medium, large, massive"
    )
    force_level: str | None = Field(
        None, description="Energy of event: gentle, moderate, forceful, explosive"
    )
    repeatability: str | None = Field(
        None, description="Temporal pattern: one_shot, periodic, continuous, irregular"
    )
    material_state: str | None = Field(
        None, description="solid, liquid, gas, granular, composite"
    )


class ContributionManifest(BaseModel):
    """Sidecar metadata for a contributed sound recording.

    Required fields ensure every clip is anchored to a physical source and action.
    """

    # --- Required: identity of the sound ---
    title: str = Field(..., min_length=3, max_length=256, description="Short human-readable name")
    source_object: str = Field(
        ...,
        min_length=2,
        max_length=256,
        description="What produced the sound (noun): 'oak interior door', 'American robin'",
    )
    source_action: str = Field(
        ...,
        min_length=2,
        max_length=256,
        description="What happened (verb phrase): 'closing with latch click', 'singing at dawn'",
    )

    # --- Required: when and where ---
    recorded_at: datetime
    location: LocationSpec

    # --- Required: licensing (contributions must be open) ---
    license: LicenseType = Field(
        ...,
        description="Must be CC0 or CC-BY for direct contributions",
    )

    # --- Required: raw audio pairing ---
    audio_filename: str = Field(
        ...,
        description="Filename of the paired raw audio file (WAV/FLAC, unprocessed)",
    )

    # --- Strongly recommended ---
    taxonomy_code: str = Field(
        "NATURAL",
        description="Starscream taxonomy branch, e.g. WILDLIFE.BIRD or URBAN.TRAFFIC",
    )
    description: str | None = Field(
        None,
        max_length=2000,
        description="Longer narrative: context, why this recording matters",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Freeform lowercase tags for search and ML clustering",
    )

    # --- Physical grounding (critical for world models) ---
    material: str | None = Field(
        None,
        description="Primary material: wood, metal, glass, water, organic, synthetic, composite",
    )
    environment: EnvironmentType = EnvironmentType.UNKNOWN
    distance_m: float | None = Field(None, ge=0, le=1000, description="Mic distance from source")
    mic_orientation: str | None = Field(
        None, description="facing_source, ambient, overhead, binaural_left, binaural_right"
    )
    background_noise_level: NoiseLevel | None = None
    other_sounds_present: list[str] = Field(
        default_factory=list,
        description="Other audible events in the clip",
    )

    # --- Recorder provenance ---
    recorder_type: RecorderType = RecorderType.UNKNOWN
    recorder_model: str | None = None
    sample_rate_hz: int | None = Field(None, ge=8000, le=384000)
    channels: int | None = Field(None, ge=1, le=32)
    bit_depth: int | None = Field(None, ge=8, le=32)

    # --- Contributor attribution ---
    contributor_id: str | None = Field(None, description="Stable contributor identifier (email hash, ORCID, etc.)")
    contributor_name: str | None = None

    # --- World model structured labels ---
    physical_properties: PhysicalProperties | None = None

    # --- Scene graph + timed events (optional, backward compatible) ---
    events: list[SoundEvent] | None = Field(
        None,
        description="Top-level timed events in the clip (alternative to scene_graph.events)",
    )
    scene_graph: SceneGraph | None = Field(
        None,
        description="Structured scene with entities and events referencing entity ids",
    )

    @field_validator("license")
    @classmethod
    def contribution_license_must_be_open(cls, v: LicenseType) -> LicenseType:
        if v not in (LicenseType.CC0, LicenseType.CC_BY):
            raise ValueError("contributions must use CC0 or CC-BY license")
        return v

    @field_validator("tags", mode="before")
    @classmethod
    def normalize_tags(cls, v: list[str] | None) -> list[str]:
        if not v:
            return []
        return sorted({tag.strip().lower().replace(" ", "_") for tag in v if tag.strip()})

    @field_validator("audio_filename")
    @classmethod
    def audio_must_be_lossless_raw(cls, v: str) -> str:
        lower = v.lower()
        if not lower.endswith((".wav", ".flac", ".aiff", ".aif")):
            raise ValueError("audio_filename must be a lossless raw format (.wav, .flac, .aiff)")
        return v

    model_config = {"json_schema_extra": {
        "example": {
            "title": "Oak hallway door closing with latch",
            "source_object": "solid oak interior door with brass latch",
            "source_action": "closing from half-open, latch clicking into frame",
            "recorded_at": "2026-03-15T14:32:00Z",
            "location": {"lat": 40.758, "lng": -73.985, "name": "Manhattan apartment hallway", "country_code": "US"},
            "license": "CC0",
            "audio_filename": "door_close_raw.wav",
            "taxonomy_code": "URBAN",
            "description": "Single close of a 1960s apartment door, mic 1m from hinge side.",
            "tags": ["door", "wood", "latch", "indoor", "impact"],
            "material": "wood",
            "environment": "indoor",
            "distance_m": 1.0,
            "mic_orientation": "facing_source",
            "background_noise_level": "quiet",
            "other_sounds_present": ["distant traffic muffled"],
            "recorder_type": "smartphone",
            "recorder_model": "iPhone 15",
            "sample_rate_hz": 48000,
            "channels": 1,
            "bit_depth": 24,
            "physical_properties": {
                "object_category": "furniture",
                "interaction_type": "impact",
                "estimated_size": "large",
                "force_level": "moderate",
                "repeatability": "one_shot",
                "material_state": "solid",
            },
        }
    }}
