import enum
import uuid
from datetime import datetime

from geoalchemy2 import Geography
from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _pg_enum(enum_cls: type[enum.Enum], name: str) -> Enum:
    """PostgreSQL native enum using member values (not Python names)."""
    return Enum(enum_cls, name=name, values_callable=lambda x: [e.value for e in x])


class LicenseType(str, enum.Enum):
    CC0 = "CC0"
    CC_BY = "CC-BY"
    CC_BY_NC = "CC-BY-NC"
    CC_BY_SA = "CC-BY-SA"
    PUBLIC_DOMAIN = "public-domain"
    POINTER_ONLY = "pointer-only"


class Season(str, enum.Enum):
    SPRING = "spring"
    SUMMER = "summer"
    AUTUMN = "autumn"
    WINTER = "winter"


class RecorderType(str, enum.Enum):
    BINAURAL = "binaural"
    HYDROPHONE = "hydrophone"
    ULTRASONIC = "ultrasonic"
    SMARTPHONE = "smartphone"
    IOT = "iot"
    UNKNOWN = "unknown"


class ReviewStatus(str, enum.Enum):
    UNREVIEWED = "unreviewed"
    APPROVED = "approved"
    FLAGGED = "flagged"
    HIDDEN = "hidden"


class FlagReason(str, enum.Enum):
    MISLABELED_GPS = "mislabeled_gps"
    WRONG_OBJECT = "wrong_object"
    DUPLICATE = "duplicate"
    OTHER = "other"


class FlagStatus(str, enum.Enum):
    PENDING = "pending"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    url: Mapped[str | None] = mapped_column(String(512))
    license_default: Mapped[LicenseType] = mapped_column(
        _pg_enum(LicenseType, "license_type"), nullable=False
    )
    external_api_url: Mapped[str | None] = mapped_column(String(512))
    record_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    recordings: Mapped[list["Recording"]] = relationship(back_populates="source")


class Tag(Base):
    __tablename__ = "tags"

    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    usage_count: Mapped[int] = mapped_column(Integer, default=1, server_default="1")


class TaxonomyNode(Base):
    __tablename__ = "taxonomy_nodes"

    code: Mapped[str] = mapped_column(String(128), primary_key=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_code: Mapped[str | None] = mapped_column(
        String(128), ForeignKey("taxonomy_nodes.code"), nullable=True
    )
    description: Mapped[str | None] = mapped_column(Text)
    recording_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    parent: Mapped["TaxonomyNode | None"] = relationship(
        remote_side=[code], back_populates="children"
    )
    children: Mapped[list["TaxonomyNode"]] = relationship(back_populates="parent")


class Recording(Base):
    __tablename__ = "recordings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    spectral_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    taxonomy_code: Mapped[str] = mapped_column(
        String(128), ForeignKey("taxonomy_nodes.code"), nullable=False, index=True
    )
    location: Mapped[object] = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=True), nullable=False
    )
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sources.id"), nullable=False, index=True
    )
    license: Mapped[LicenseType] = mapped_column(_pg_enum(LicenseType, "license_type"), nullable=False)

    # Contribution identity (world-model grounding)
    title: Mapped[str | None] = mapped_column(String(256), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    source_object: Mapped[str | None] = mapped_column(String(256), index=True)
    source_action: Mapped[str | None] = mapped_column(String(256), index=True)
    tags: Mapped[list | None] = mapped_column(JSON)
    material: Mapped[str | None] = mapped_column(String(64), index=True)
    environment: Mapped[str | None] = mapped_column(String(32), index=True)
    distance_m: Mapped[float | None] = mapped_column(Float)
    mic_orientation: Mapped[str | None] = mapped_column(String(64))
    background_noise_level: Mapped[str | None] = mapped_column(String(32))
    other_sounds_present: Mapped[list | None] = mapped_column(JSON)
    recorder_model: Mapped[str | None] = mapped_column(String(128))
    sample_rate_hz: Mapped[int | None] = mapped_column(Integer)
    channels: Mapped[int | None] = mapped_column(Integer)
    bit_depth: Mapped[int | None] = mapped_column(Integer)
    contributor_id: Mapped[str | None] = mapped_column(String(128), index=True)
    contributor_name: Mapped[str | None] = mapped_column(String(256))
    world_model_labels: Mapped[dict | None] = mapped_column(JSON)
    events: Mapped[list | None] = mapped_column(JSON)
    scene_graph: Mapped[dict | None] = mapped_column(JSON)
    is_contribution: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    # Contextual fields (best-effort)
    location_name: Mapped[str | None] = mapped_column(String(512))
    country_code: Mapped[str | None] = mapped_column(String(2), index=True)
    altitude_m: Mapped[float | None] = mapped_column(Float)
    season: Mapped[Season | None] = mapped_column(_pg_enum(Season, "season"))
    habitat: Mapped[str | None] = mapped_column(String(128), index=True)
    weather: Mapped[str | None] = mapped_column(String(255))
    temperature_c: Mapped[float | None] = mapped_column(Float)
    cross_modal_links: Mapped[dict | None] = mapped_column(JSON)
    recorder_type: Mapped[RecorderType] = mapped_column(
        _pg_enum(RecorderType, "recorder_type"),
        default=RecorderType.UNKNOWN,
        server_default="unknown",
    )
    quality: Mapped[int | None] = mapped_column(Integer)
    review_status: Mapped[ReviewStatus] = mapped_column(
        _pg_enum(ReviewStatus, "review_status"),
        default=ReviewStatus.UNREVIEWED,
        server_default="unreviewed",
    )

    # Storage pointers
    external_id: Mapped[str | None] = mapped_column(String(255))
    external_url: Mapped[str | None] = mapped_column(String(1024))
    flac_key: Mapped[str | None] = mapped_column(String(512))
    mp3_key: Mapped[str | None] = mapped_column(String(512))
    spectrogram_key: Mapped[str | None] = mapped_column(String(512))
    duration_s: Mapped[float | None] = mapped_column(Float)

    # Deduplication (spectral_hash matches link to canonical record)
    canonical_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("recordings.id"), nullable=True, index=True
    )
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    source: Mapped[Source] = relationship(back_populates="recordings")
    taxonomy: Mapped[TaxonomyNode] = relationship()
    canonical: Mapped["Recording | None"] = relationship(
        remote_side=[id], foreign_keys=[canonical_id]
    )

    reviews: Mapped[list["RecordingReview"]] = relationship(back_populates="recording")
    flags: Mapped[list["RecordingFlag"]] = relationship(back_populates="recording")
    classifications: Mapped[list["RecordingClassification"]] = relationship(
        back_populates="recording"
    )

    __table_args__ = (
        Index("ix_recordings_taxonomy_recorded", "taxonomy_code", "recorded_at"),
        Index("ix_recordings_quality", "quality"),
    )


class SensorNode(Base):
    __tablename__ = "sensor_nodes"

    node_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)
    location: Mapped[object] = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=True), nullable=False
    )
    public_key: Mapped[str] = mapped_column(Text, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    token_prefix: Mapped[str] = mapped_column(String(12), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    event_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Contributor(Base):
    __tablename__ = "contributors"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    display_name: Mapped[str] = mapped_column(String(256), nullable=False)
    github_username: Mapped[str | None] = mapped_column(String(128), unique=True)
    api_key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    api_key_prefix: Mapped[str] = mapped_column(String(12), nullable=False, index=True)
    citations_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class RecordingReview(Base):
    __tablename__ = "recording_reviews"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recording_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("recordings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    reviewer_key: Mapped[str] = mapped_column(String(128), nullable=False)
    contributor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contributors.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    recording: Mapped[Recording] = relationship(back_populates="reviews")

    __table_args__ = (
        Index("uq_review_per_reviewer", "recording_id", "reviewer_key", unique=True),
    )


class RecordingFlag(Base):
    __tablename__ = "recording_flags"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recording_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("recordings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reason: Mapped[FlagReason] = mapped_column(_pg_enum(FlagReason, "flag_reason"), nullable=False)
    details: Mapped[str | None] = mapped_column(Text)
    status: Mapped[FlagStatus] = mapped_column(
        _pg_enum(FlagStatus, "flag_status"),
        default=FlagStatus.PENDING,
        server_default="pending",
    )
    reporter_key: Mapped[str] = mapped_column(String(128), nullable=False)
    contributor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contributors.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    recording: Mapped[Recording] = relationship(back_populates="flags")


class HarvestRunStatus(str, enum.Enum):
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


class HarvestRun(Base):
    __tablename__ = "harvest_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_slug: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    status: Mapped[HarvestRunStatus] = mapped_column(
        _pg_enum(HarvestRunStatus, "harvest_run_status"),
        nullable=False,
    )
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class RecordingClassification(Base):
    __tablename__ = "recording_classifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recording_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("recordings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    model_name: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    taxonomy_suggestion: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    recording: Mapped[Recording] = relationship(back_populates="classifications")

    __table_args__ = (
        Index("ix_recording_classifications_model", "recording_id", "model_name"),
    )


class PipelineJobStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class PipelineJob(Base):
    __tablename__ = "pipeline_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status: Mapped[PipelineJobStatus] = mapped_column(
        _pg_enum(PipelineJobStatus, "pipeline_job_status"),
        nullable=False,
        default=PipelineJobStatus.PENDING,
        server_default="pending",
    )
    kind: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    result_json: Mapped[dict | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
