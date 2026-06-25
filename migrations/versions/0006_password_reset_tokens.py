"""add password reset tokens

Revision ID: 0006_password_reset_tokens
Revises: 0005_network_topology_entries
Create Date: 2026-06-24 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0006_password_reset_tokens"
down_revision: str | None = "0005_network_topology_entries"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "portal_password_reset_tokens",
        sa.Column("token", sa.String(), nullable=False),
        sa.Column("account_id", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("expires_at", sa.String(), nullable=False),
        sa.Column("used_at", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("token"),
    )
    op.create_index(
        "ix_portal_password_reset_tokens_email",
        "portal_password_reset_tokens",
        ["email"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_portal_password_reset_tokens_email",
        table_name="portal_password_reset_tokens",
    )
    op.drop_table("portal_password_reset_tokens")
