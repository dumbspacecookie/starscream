"""Add events and scene_graph JSON columns to recordings

Revision ID: 007
Revises: 006
Create Date: 2026-06-10

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSON

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("recordings", sa.Column("events", JSON, nullable=True))
    op.add_column("recordings", sa.Column("scene_graph", JSON, nullable=True))


def downgrade() -> None:
    op.drop_column("recordings", "scene_graph")
    op.drop_column("recordings", "events")
