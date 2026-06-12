"""Recording ML classifications

Revision ID: 005
Revises: 004
Create Date: 2026-06-10

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "recording_classifications",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("recording_id", UUID(as_uuid=True), nullable=False),
        sa.Column("model_name", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("taxonomy_suggestion", sa.String(length=128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["recording_id"], ["recordings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_recording_classifications_recording_id",
        "recording_classifications",
        ["recording_id"],
    )
    op.create_index(
        "ix_recording_classifications_model",
        "recording_classifications",
        ["recording_id", "model_name"],
    )


def downgrade() -> None:
    op.drop_index("ix_recording_classifications_model", table_name="recording_classifications")
    op.drop_index(
        "ix_recording_classifications_recording_id", table_name="recording_classifications"
    )
    op.drop_table("recording_classifications")
