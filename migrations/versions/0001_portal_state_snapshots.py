"""create portal state snapshots

Revision ID: 0001_portal_state_snapshots
Revises:
Create Date: 2026-06-22 22:40:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0001_portal_state_snapshots"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "portal_state_snapshots",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("portal_state_snapshots")
