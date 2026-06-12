"""Contribution metadata and tags

Revision ID: 002
Revises: 001
Create Date: 2026-06-10

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSON

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tags",
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("usage_count", sa.Integer(), server_default="1", nullable=False),
        sa.PrimaryKeyConstraint("name"),
    )

    op.add_column("recordings", sa.Column("title", sa.String(length=256), nullable=True))
    op.add_column("recordings", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("recordings", sa.Column("source_object", sa.String(length=256), nullable=True))
    op.add_column("recordings", sa.Column("source_action", sa.String(length=256), nullable=True))
    op.add_column("recordings", sa.Column("tags", JSON(), nullable=True))
    op.add_column("recordings", sa.Column("material", sa.String(length=64), nullable=True))
    op.add_column("recordings", sa.Column("environment", sa.String(length=32), nullable=True))
    op.add_column("recordings", sa.Column("distance_m", sa.Float(), nullable=True))
    op.add_column("recordings", sa.Column("mic_orientation", sa.String(length=64), nullable=True))
    op.add_column("recordings", sa.Column("background_noise_level", sa.String(length=32), nullable=True))
    op.add_column("recordings", sa.Column("other_sounds_present", JSON(), nullable=True))
    op.add_column("recordings", sa.Column("recorder_model", sa.String(length=128), nullable=True))
    op.add_column("recordings", sa.Column("sample_rate_hz", sa.Integer(), nullable=True))
    op.add_column("recordings", sa.Column("channels", sa.Integer(), nullable=True))
    op.add_column("recordings", sa.Column("bit_depth", sa.Integer(), nullable=True))
    op.add_column("recordings", sa.Column("contributor_id", sa.String(length=128), nullable=True))
    op.add_column("recordings", sa.Column("contributor_name", sa.String(length=256), nullable=True))
    op.add_column("recordings", sa.Column("world_model_labels", JSON(), nullable=True))
    op.add_column(
        "recordings",
        sa.Column("is_contribution", sa.Boolean(), server_default="false", nullable=False),
    )

    op.create_index("ix_recordings_title", "recordings", ["title"])
    op.create_index("ix_recordings_source_object", "recordings", ["source_object"])
    op.create_index("ix_recordings_source_action", "recordings", ["source_action"])
    op.create_index("ix_recordings_material", "recordings", ["material"])
    op.create_index("ix_recordings_environment", "recordings", ["environment"])
    op.create_index("ix_recordings_contributor_id", "recordings", ["contributor_id"])


def downgrade() -> None:
    op.drop_index("ix_recordings_contributor_id", table_name="recordings")
    op.drop_index("ix_recordings_environment", table_name="recordings")
    op.drop_index("ix_recordings_material", table_name="recordings")
    op.drop_index("ix_recordings_source_action", table_name="recordings")
    op.drop_index("ix_recordings_source_object", table_name="recordings")
    op.drop_index("ix_recordings_title", table_name="recordings")

    op.drop_column("recordings", "is_contribution")
    op.drop_column("recordings", "world_model_labels")
    op.drop_column("recordings", "contributor_name")
    op.drop_column("recordings", "contributor_id")
    op.drop_column("recordings", "bit_depth")
    op.drop_column("recordings", "channels")
    op.drop_column("recordings", "sample_rate_hz")
    op.drop_column("recordings", "recorder_model")
    op.drop_column("recordings", "other_sounds_present")
    op.drop_column("recordings", "background_noise_level")
    op.drop_column("recordings", "mic_orientation")
    op.drop_column("recordings", "distance_m")
    op.drop_column("recordings", "environment")
    op.drop_column("recordings", "material")
    op.drop_column("recordings", "tags")
    op.drop_column("recordings", "source_action")
    op.drop_column("recordings", "source_object")
    op.drop_column("recordings", "description")
    op.drop_column("recordings", "title")
    op.drop_table("tags")
