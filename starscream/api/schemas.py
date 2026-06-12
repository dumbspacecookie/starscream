from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from starscream.db.models import (
    FlagReason,
    FlagStatus,
    HarvestRunStatus,
    LicenseType,
    RecorderType,
    ReviewStatus,
    Season,
)


class LocationOut(BaseModel):
    lat: float
    lng: float


class RecordingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    spectral_hash: str
    taxonomy_code: str
    location: LocationOut
    recorded_at: datetime
    source_id: UUID
    license: LicenseType

    # Contribution / world-model fields
    title: str | None = None
    description: str | None = None
    source_object: str | None = None
    source_action: str | None = None
    tags: list[str] = Field(default_factory=list)
    material: str | None = None
    environment: str | None = None
    world_model_labels: dict | None = None
    contributor_id: str | None = None
    contributor_name: str | None = None
    recorder_model: str | None = None
    sample_rate_hz: int | None = None
    channels: int | None = None
    bit_depth: int | None = None
    is_contribution: bool = False

    location_name: str | None = None
    country_code: str | None = None
    altitude_m: float | None = None
    season: Season | None = None
    habitat: str | None = None
    weather: str | None = None
    temperature_c: float | None = None
    cross_modal_links: dict | None = None
    recorder_type: RecorderType
    quality: int | None = None
    review_status: ReviewStatus = ReviewStatus.UNREVIEWED
    external_id: str | None = None
    external_url: str | None = None
    duration_s: float | None = None
    has_audio: bool = False
    canonical_id: UUID | None = None
    is_duplicate: bool = False


class RecordingListOut(BaseModel):
    items: list[RecordingOut]
    next_cursor: str | None = None
    total: int | None = None


class TaxonomyNodeOut(BaseModel):
    code: str
    label: str
    parent_code: str | None = None
    description: str | None = None
    recording_count: int
    children: list["TaxonomyNodeOut"] = Field(default_factory=list)


class SourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    url: str | None = None
    license_default: LicenseType
    record_count: int


class StatsOut(BaseModel):
    total_recordings: int
    total_sources: int
    countries_covered: int
    taxonomy_branches: int
    storage_flac_gb: float
    total_contributions: int = 0
    total_tags: int = 0


class TagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    usage_count: int


class GuidelinesOut(BaseModel):
    mission: str
    audio_requirements: dict
    required_metadata: list[str]
    recommended_metadata: list[str]
    license: str
    docs: str
    manifest_schema: str
    cli: str


class ContributionValidateOut(BaseModel):
    valid: bool
    errors: list[str]
    warnings: list[str]
    duration_s: float | None = None
    detected_sample_rate_hz: int | None = None
    detected_channels: int | None = None
    detected_bit_depth: int | None = None


class ContributionOut(BaseModel):
    recording: RecordingOut
    warnings: list[str]


class ContributionJobAcceptedOut(BaseModel):
    job_id: UUID
    status: str


class ContributionJobStatusOut(BaseModel):
    job_id: UUID
    status: str
    kind: str
    error: str | None = None
    warnings: list[str] | None = None
    recording: RecordingOut | None = None


class BatchItemResult(BaseModel):
    manifest_path: str
    title: str | None = None
    status: str
    recording_id: str | None = None
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class BatchUploadOut(BaseModel):
    total: int
    uploaded: int
    failed: int
    skipped: int
    results: list[BatchItemResult]


class BatchValidateOut(BaseModel):
    total: int
    valid: int
    invalid: int
    results: list[BatchItemResult]


class SearchHitOut(BaseModel):
    id: UUID
    title: str | None = None
    source_object: str | None = None
    source_action: str | None = None
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    material: str | None = None
    environment: str | None = None
    taxonomy_code: str
    location_name: str | None = None
    country_code: str | None = None
    habitat: str | None = None
    season: str | None = None
    quality: int | None = None
    is_contribution: bool = False
    recorded_at: datetime | None = None
    lat: float | None = None
    lng: float | None = None


class SearchOut(BaseModel):
    query: str
    hits: list[SearchHitOut]
    limit: int
    total: int | None = None
    processing_time_ms: int | None = None


class RateIn(BaseModel):
    score: int = Field(ge=1, le=5)


class RateOut(BaseModel):
    recording_id: UUID
    score: int
    quality: int | None = None
    review_count: int
    updated: bool


class FlagIn(BaseModel):
    reason: FlagReason
    details: str | None = Field(None, max_length=2000)


class FlagOut(BaseModel):
    id: UUID
    recording_id: UUID
    reason: FlagReason
    details: str | None = None
    status: FlagStatus
    review_status: ReviewStatus
    created_at: datetime


class ContributorRegisterIn(BaseModel):
    display_name: str = Field(min_length=1, max_length=256)
    github_username: str | None = Field(None, max_length=128)


class ContributorRegisterOut(BaseModel):
    contributor_id: UUID
    display_name: str
    api_key: str
    message: str = "Store this API key securely — it is shown only once."


class ContributorProfileOut(BaseModel):
    id: UUID
    display_name: str
    github_username: str | None = None
    sound_count: int
    citations_count: int
    created_at: datetime


class FlagQueueItemOut(BaseModel):
    id: UUID
    recording_id: UUID
    recording_title: str | None = None
    reason: FlagReason
    details: str | None = None
    status: FlagStatus
    reporter_key: str
    created_at: datetime


class FlagQueueOut(BaseModel):
    items: list[FlagQueueItemOut]
    total: int


class HarvestRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_slug: str
    started_at: datetime
    finished_at: datetime
    created: int
    skipped: int
    failed: int
    status: HarvestRunStatus
    detail: dict | None = None


class HarvestRunListOut(BaseModel):
    items: list[HarvestRunOut]
    total: int


class ClassificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    model_name: str
    label: str
    confidence: float
    taxonomy_suggestion: str | None = None
    created_at: datetime


class ClassificationListOut(BaseModel):
    recording_id: UUID
    items: list[ClassificationOut]


class SimilarRecordingsOut(BaseModel):
    recording_id: UUID
    items: list[RecordingOut]
    total: int


class CanonicalOut(BaseModel):
    recording_id: UUID
    canonical: RecordingOut
    alternates: list[RecordingOut]


class LeaderboardEntryOut(BaseModel):
    rank: int
    id: UUID
    display_name: str
    sound_count: int
    citations_count: int


class LeaderboardOut(BaseModel):
    items: list[LeaderboardEntryOut]
    limit: int
