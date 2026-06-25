"""add network topology entries

Revision ID: 0005_network_topology_entries
Revises: 0004_participant_eligibility_review
Create Date: 2026-06-24 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0005_network_topology_entries"
down_revision: str | None = "0004_participant_eligibility_review"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "portal_network_topology_entries",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("leg_id", sa.String(), nullable=False),
        sa.Column("source_name", sa.String(), nullable=False),
        sa.Column("metering_point_id", sa.String(), nullable=True),
        sa.Column("street", sa.String(), nullable=False),
        sa.Column("postal_code", sa.String(), nullable=False),
        sa.Column("city", sa.String(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("imported_at", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_portal_network_topology_entries_active",
        "portal_network_topology_entries",
        ["active"],
    )
    op.create_index(
        "ix_portal_network_topology_entries_metering_point_id",
        "portal_network_topology_entries",
        ["metering_point_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_portal_network_topology_entries_metering_point_id",
        table_name="portal_network_topology_entries",
    )
    op.drop_index(
        "ix_portal_network_topology_entries_active",
        table_name="portal_network_topology_entries",
    )
    op.drop_table("portal_network_topology_entries")
