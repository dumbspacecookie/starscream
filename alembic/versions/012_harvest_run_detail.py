"""Add harvest_runs.detail JSON for page-level harvest errors

Revision ID: 012
Revises: 011
Create Date: 2026-06-10

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSON

revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("harvest_runs", sa.Column("detail", JSON, nullable=True))


def downgrade() -> None:
    op.drop_column("harvest_runs", "detail")
