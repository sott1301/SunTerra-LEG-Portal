"""add participant eligibility review fields

Revision ID: 0004_participant_eligibility_review
Revises: 0003_user_account_totp_mfa
Create Date: 2026-06-24 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0004_participant_eligibility_review"
down_revision: str | None = "0003_user_account_totp_mfa"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "portal_participants",
        sa.Column(
            "eligibility_status",
            sa.String(),
            nullable=False,
            server_default="approved",
        ),
    )
    op.add_column(
        "portal_participants",
        sa.Column("eligibility_review_reason", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("portal_participants", "eligibility_review_reason")
    op.drop_column("portal_participants", "eligibility_status")
