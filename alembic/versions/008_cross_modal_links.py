"""Add cross_modal_links JSON to recordings

Revision ID: 008
Revises: 007
Create Date: 2026-06-10

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSON

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "recordings",
        sa.Column("cross_modal_links", JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("recordings", "cross_modal_links")
