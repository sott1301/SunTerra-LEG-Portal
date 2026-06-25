"""add pilot access controls

Revision ID: 0008_pilot_access_controls
Revises: 0007_pilot_feedback
Create Date: 2026-06-24 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0008_pilot_access_controls"
down_revision: str | None = "0007_pilot_feedback"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "portal_interest_records",
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("email"),
    )
    op.create_table(
        "portal_pilot_allowlist_entries",
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("email"),
    )
    op.create_index(
        "ix_portal_interest_records_created_at",
        "portal_interest_records",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_portal_interest_records_created_at",
        table_name="portal_interest_records",
    )
    op.drop_table("portal_pilot_allowlist_entries")
    op.drop_table("portal_interest_records")
