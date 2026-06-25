"""add user account totp mfa fields

Revision ID: 0003_user_account_totp_mfa
Revises: 0002_portal_state_core_objects
Create Date: 2026-06-24 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0003_user_account_totp_mfa"
down_revision: str | None = "0002_portal_state_core_objects"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "portal_user_accounts",
        sa.Column("mfa_totp_secret", sa.String(), nullable=True),
    )
    op.add_column(
        "portal_user_accounts",
        sa.Column(
            "mfa_totp_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("portal_user_accounts", "mfa_totp_enabled")
    op.drop_column("portal_user_accounts", "mfa_totp_secret")
