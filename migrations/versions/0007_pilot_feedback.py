"""add pilot feedback

Revision ID: 0007_pilot_feedback
Revises: 0006_password_reset_tokens
Create Date: 2026-06-24 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0007_pilot_feedback"
down_revision: str | None = "0006_password_reset_tokens"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "portal_pilot_feedback",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("message", sa.String(), nullable=False),
        sa.Column("context", sa.String(), nullable=True),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("user_email", sa.String(), nullable=False),
        sa.Column("user_role", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("rollout_relevance", sa.String(), nullable=True),
        sa.Column("admin_note", sa.String(), nullable=True),
        sa.Column("reviewed_at", sa.String(), nullable=True),
        sa.Column("reviewed_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_portal_pilot_feedback_created_at",
        "portal_pilot_feedback",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_portal_pilot_feedback_created_at",
        table_name="portal_pilot_feedback",
    )
    op.drop_table("portal_pilot_feedback")
