"""Dedup linking — canonical_id and is_duplicate

Revision ID: 003
Revises: 002
Create Date: 2026-06-10

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "recordings",
        sa.Column("canonical_id", UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "recordings",
        sa.Column("is_duplicate", sa.Boolean(), server_default="false", nullable=False),
    )
    op.create_foreign_key(
        "fk_recordings_canonical_id",
        "recordings",
        "recordings",
        ["canonical_id"],
        ["id"],
    )
    op.create_index("ix_recordings_canonical_id", "recordings", ["canonical_id"])


def downgrade() -> None:
    op.drop_index("ix_recordings_canonical_id", table_name="recordings")
    op.drop_constraint("fk_recordings_canonical_id", "recordings", type_="foreignkey")
    op.drop_column("recordings", "is_duplicate")
    op.drop_column("recordings", "canonical_id")
