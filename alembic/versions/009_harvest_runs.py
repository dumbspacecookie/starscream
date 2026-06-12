"""Add harvest_runs table for scheduled federation harvests

Revision ID: 009
Revises: 008
Create Date: 2026-06-10

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM, UUID

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

harvest_run_status = ENUM(
    "completed", "skipped", "failed", name="harvest_run_status", create_type=False
)


def upgrade() -> None:
    harvest_run_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "harvest_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("source_slug", sa.String(64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", harvest_run_status, nullable=False),
    )
    op.create_index("ix_harvest_runs_source_slug", "harvest_runs", ["source_slug"])
    op.create_index("ix_harvest_runs_started_at", "harvest_runs", ["started_at"])


def downgrade() -> None:
    op.drop_index("ix_harvest_runs_started_at", table_name="harvest_runs")
    op.drop_index("ix_harvest_runs_source_slug", table_name="harvest_runs")
    op.drop_table("harvest_runs")
    harvest_run_status.drop(op.get_bind(), checkfirst=True)
