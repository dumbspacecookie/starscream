"""Initial Starscream schema

Revision ID: 001
Revises:
Create Date: 2026-06-10

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geography
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

license_type = postgresql.ENUM(
    "CC0", "CC-BY", "CC-BY-NC", "CC-BY-SA", "public-domain", "pointer-only",
    name="license_type",
    create_type=False,
)
season = postgresql.ENUM(
    "spring", "summer", "autumn", "winter", name="season", create_type=False
)
recorder_type = postgresql.ENUM(
    "binaural", "hydrophone", "ultrasonic", "smartphone", "iot", "unknown",
    name="recorder_type",
    create_type=False,
)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    license_type.create(op.get_bind(), checkfirst=True)
    season.create(op.get_bind(), checkfirst=True)
    recorder_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "sources",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("url", sa.String(length=512), nullable=True),
        sa.Column("license_default", license_type, nullable=False),
        sa.Column("external_api_url", sa.String(length=512), nullable=True),
        sa.Column("record_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint("slug"),
    )

    op.create_table(
        "taxonomy_nodes",
        sa.Column("code", sa.String(length=128), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("parent_code", sa.String(length=128), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("recording_count", sa.Integer(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(["parent_code"], ["taxonomy_nodes.code"]),
        sa.PrimaryKeyConstraint("code"),
    )

    op.create_table(
        "recordings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("spectral_hash", sa.String(length=64), nullable=False),
        sa.Column("taxonomy_code", sa.String(length=128), nullable=False),
        sa.Column("location", Geography(geometry_type="POINT", srid=4326), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_id", sa.UUID(), nullable=False),
        sa.Column("license", license_type, nullable=False),
        sa.Column("location_name", sa.String(length=512), nullable=True),
        sa.Column("country_code", sa.String(length=2), nullable=True),
        sa.Column("altitude_m", sa.Float(), nullable=True),
        sa.Column("season", season, nullable=True),
        sa.Column("habitat", sa.String(length=128), nullable=True),
        sa.Column("weather", sa.String(length=255), nullable=True),
        sa.Column("temperature_c", sa.Float(), nullable=True),
        sa.Column("recorder_type", recorder_type, server_default="unknown", nullable=False),
        sa.Column("quality", sa.Integer(), nullable=True),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("external_url", sa.String(length=1024), nullable=True),
        sa.Column("flac_key", sa.String(length=512), nullable=True),
        sa.Column("mp3_key", sa.String(length=512), nullable=True),
        sa.Column("duration_s", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"]),
        sa.ForeignKeyConstraint(["taxonomy_code"], ["taxonomy_nodes.code"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("ix_recordings_spectral_hash", "recordings", ["spectral_hash"])
    op.create_index("ix_recordings_taxonomy_code", "recordings", ["taxonomy_code"])
    op.create_index("ix_recordings_recorded_at", "recordings", ["recorded_at"])
    op.create_index("ix_recordings_source_id", "recordings", ["source_id"])
    op.create_index("ix_recordings_country_code", "recordings", ["country_code"])
    op.create_index("ix_recordings_habitat", "recordings", ["habitat"])
    op.create_index("ix_recordings_quality", "recordings", ["quality"])
    op.create_index("ix_recordings_taxonomy_recorded", "recordings", ["taxonomy_code", "recorded_at"])


def downgrade() -> None:
    op.drop_index("ix_recordings_taxonomy_recorded", table_name="recordings")
    op.drop_index("ix_recordings_quality", table_name="recordings")
    op.drop_index("ix_recordings_habitat", table_name="recordings")
    op.drop_index("ix_recordings_country_code", table_name="recordings")
    op.drop_index("ix_recordings_source_id", table_name="recordings")
    op.drop_index("ix_recordings_recorded_at", table_name="recordings")
    op.drop_index("ix_recordings_taxonomy_code", table_name="recordings")
    op.drop_index("ix_recordings_spectral_hash", table_name="recordings")
    op.drop_table("recordings")
    op.drop_table("taxonomy_nodes")
    op.drop_table("sources")
    recorder_type.drop(op.get_bind(), checkfirst=True)
    season.drop(op.get_bind(), checkfirst=True)
    license_type.drop(op.get_bind(), checkfirst=True)
