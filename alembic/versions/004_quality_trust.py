"""Quality & trust — contributors, reviews, flags, review_status

Revision ID: 004
Revises: 003
Create Date: 2026-06-10

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM, UUID

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

flag_reason = ENUM(
    "mislabeled_gps",
    "wrong_object",
    "duplicate",
    "other",
    name="flag_reason",
    create_type=False,
)
flag_status = ENUM("pending", "resolved", "dismissed", name="flag_status", create_type=False)
review_status = ENUM(
    "unreviewed",
    "approved",
    "flagged",
    "hidden",
    name="review_status",
    create_type=False,
)


def upgrade() -> None:
    flag_reason.create(op.get_bind(), checkfirst=True)
    flag_status.create(op.get_bind(), checkfirst=True)
    review_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "contributors",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("display_name", sa.String(length=256), nullable=False),
        sa.Column("github_username", sa.String(length=128), nullable=True),
        sa.Column("api_key_hash", sa.String(length=64), nullable=False),
        sa.Column("api_key_prefix", sa.String(length=12), nullable=False),
        sa.Column("citations_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("api_key_hash"),
        sa.UniqueConstraint("github_username"),
    )
    op.create_index("ix_contributors_api_key_prefix", "contributors", ["api_key_prefix"])

    op.create_table(
        "recording_reviews",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("recording_id", UUID(as_uuid=True), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("reviewer_key", sa.String(length=128), nullable=False),
        sa.Column("contributor_id", UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["contributor_id"], ["contributors.id"]),
        sa.ForeignKeyConstraint(["recording_id"], ["recordings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("recording_id", "reviewer_key", name="uq_review_per_reviewer"),
        sa.CheckConstraint("score >= 1 AND score <= 5", name="ck_review_score_range"),
    )
    op.create_index("ix_recording_reviews_recording_id", "recording_reviews", ["recording_id"])

    op.create_table(
        "recording_flags",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("recording_id", UUID(as_uuid=True), nullable=False),
        sa.Column("reason", flag_reason, nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("status", flag_status, server_default="pending", nullable=False),
        sa.Column("reporter_key", sa.String(length=128), nullable=False),
        sa.Column("contributor_id", UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["contributor_id"], ["contributors.id"]),
        sa.ForeignKeyConstraint(["recording_id"], ["recordings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_recording_flags_recording_id", "recording_flags", ["recording_id"])
    op.create_index("ix_recording_flags_status", "recording_flags", ["status"])

    op.add_column(
        "recordings",
        sa.Column(
            "review_status",
            review_status,
            server_default="unreviewed",
            nullable=False,
        ),
    )
    op.create_index("ix_recordings_review_status", "recordings", ["review_status"])


def downgrade() -> None:
    op.drop_index("ix_recordings_review_status", table_name="recordings")
    op.drop_column("recordings", "review_status")

    op.drop_index("ix_recording_flags_status", table_name="recording_flags")
    op.drop_index("ix_recording_flags_recording_id", table_name="recording_flags")
    op.drop_table("recording_flags")

    op.drop_index("ix_recording_reviews_recording_id", table_name="recording_reviews")
    op.drop_table("recording_reviews")

    op.drop_index("ix_contributors_api_key_prefix", table_name="contributors")
    op.drop_table("contributors")

    review_status.drop(op.get_bind(), checkfirst=True)
    flag_status.drop(op.get_bind(), checkfirst=True)
    flag_reason.drop(op.get_bind(), checkfirst=True)
