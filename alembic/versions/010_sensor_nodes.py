"""Add sensor_nodes table for IoT node registry

Revision ID: 010
Revises: 009
Create Date: 2026-06-10

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geography

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sensor_nodes",
        sa.Column("node_id", sa.String(length=64), primary_key=True),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lng", sa.Float(), nullable=False),
        sa.Column(
            "location",
            Geography(geometry_type="POINT", srid=4326),
            nullable=False,
        ),
        sa.Column("public_key", sa.Text(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("token_prefix", sa.String(length=12), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("event_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_sensor_nodes_token_prefix", "sensor_nodes", ["token_prefix"], unique=False)
    op.create_index(
        "uq_sensor_nodes_token_hash",
        "sensor_nodes",
        ["token_hash"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_sensor_nodes_token_hash", table_name="sensor_nodes")
    op.drop_index("ix_sensor_nodes_token_prefix", table_name="sensor_nodes")
    op.drop_table("sensor_nodes")
