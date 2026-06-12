"""Add pipeline_jobs table for async upload queue

Revision ID: 011
Revises: 010
Create Date: 2026-06-10

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM, JSON, UUID

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

pipeline_job_status = ENUM(
    "pending",
    "running",
    "completed",
    "failed",
    name="pipeline_job_status",
    create_type=False,
)


def upgrade() -> None:
    pipeline_job_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "pipeline_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("status", pipeline_job_status, nullable=False, server_default="pending"),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("payload_json", JSON, nullable=False),
        sa.Column("result_json", JSON, nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_pipeline_jobs_kind", "pipeline_jobs", ["kind"])
    op.create_index("ix_pipeline_jobs_status", "pipeline_jobs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_pipeline_jobs_status", table_name="pipeline_jobs")
    op.drop_index("ix_pipeline_jobs_kind", table_name="pipeline_jobs")
    op.drop_table("pipeline_jobs")
    pipeline_job_status.drop(op.get_bind(), checkfirst=True)
