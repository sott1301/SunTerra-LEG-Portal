"""create portal core object tables

Revision ID: 0002_portal_state_core_objects
Revises: 0001_portal_state_snapshots
Create Date: 2026-06-23 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0002_portal_state_core_objects"
down_revision: str | None = "0001_portal_state_snapshots"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "portal_participants",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("leg_id", sa.String(), nullable=False),
        sa.Column("email_verified", sa.Boolean(), nullable=False),
        sa.Column("phone_number", sa.String(), nullable=True),
        sa.Column("preferred_contact_channel", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "portal_participant_invitations",
        sa.Column("token", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("leg_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("participant_id", sa.String(), nullable=True),
        sa.Column("source", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("token"),
    )
    op.create_table(
        "portal_identity_verifications",
        sa.Column("participant_id", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("leg_id", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("required_level", sa.String(), nullable=False),
        sa.Column("current_level", sa.String(), nullable=False),
        sa.Column("satisfied", sa.Boolean(), nullable=False),
        sa.Column("verified_at", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("participant_id"),
    )
    op.create_table(
        "portal_document_versions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("document_key", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("version", sa.String(), nullable=False),
        sa.Column("document_hash", sa.String(), nullable=False),
        sa.Column("context", sa.String(), nullable=False),
        sa.Column("published_at", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "portal_consent_evidence",
        sa.Column("participant_id", sa.String(), nullable=False),
        sa.Column("document_version_id", sa.String(), nullable=False),
        sa.Column("accepted_at", sa.String(), nullable=False),
        sa.Column("document_key", sa.String(), nullable=False),
        sa.Column("version", sa.String(), nullable=False),
        sa.Column("document_hash", sa.String(), nullable=False),
        sa.Column("context", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("participant_id", "document_version_id", "accepted_at"),
    )
    op.create_table(
        "portal_mutation_requests",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("participant_id", sa.String(), nullable=False),
        sa.Column("leg_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("submitted_at", sa.String(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "portal_participant_audit_events",
        sa.Column("participant_id", sa.String(), nullable=False),
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("participant_id", "id"),
    )
    op.create_table(
        "portal_mutation_packages",
        sa.Column("package_id", sa.String(), nullable=False),
        sa.Column("leg_id", sa.String(), nullable=False),
        sa.Column("quarter", sa.String(), nullable=False),
        sa.Column("generated_at", sa.String(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("package_id"),
    )
    op.create_table(
        "portal_file_evidence",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("mutation_request_id", sa.String(), nullable=False),
        sa.Column("participant_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "portal_mutation_package_metadata",
        sa.Column("package_id", sa.String(), nullable=False),
        sa.Column("current_status", sa.String(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("package_id"),
    )
    op.create_table(
        "portal_packaged_mutation_requests",
        sa.Column("mutation_request_id", sa.String(), nullable=False),
        sa.Column("package_id", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("mutation_request_id"),
    )
    op.create_table(
        "portal_user_accounts",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("organization", sa.String(), nullable=True),
        sa.Column("password_hash", sa.String(), nullable=True),
        sa.Column("password_salt", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "portal_communication_events",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("channel", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("recipient_email", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("portal_communication_events")
    op.drop_table("portal_user_accounts")
    op.drop_table("portal_packaged_mutation_requests")
    op.drop_table("portal_mutation_package_metadata")
    op.drop_table("portal_file_evidence")
    op.drop_table("portal_mutation_packages")
    op.drop_table("portal_participant_audit_events")
    op.drop_table("portal_mutation_requests")
    op.drop_table("portal_consent_evidence")
    op.drop_table("portal_document_versions")
    op.drop_table("portal_identity_verifications")
    op.drop_table("portal_participant_invitations")
    op.drop_table("portal_participants")
