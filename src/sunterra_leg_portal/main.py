import csv
import hmac
import json
import os
import secrets
import struct
from base64 import b32decode, b32encode, b64decode
from datetime import UTC, date, datetime, timedelta
from hashlib import pbkdf2_hmac, sha1, sha256
from io import StringIO
from urllib.parse import quote
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import Session, select

from sunterra_leg_portal.auth import (
    CurrentUser,
    DEV_PARTICIPANT_USERS,
    JWT_ACCESS_TOKEN_SECONDS,
    Role,
    create_access_token,
    current_user,
    development_auth_enabled,
    register_dev_participant_user,
    require_roles,
    require_roles_before_mfa,
    set_jwt_user_resolver,
)
from sunterra_leg_portal.config import production_lifespan
from sunterra_leg_portal.db import (
    PortalCommunicationEvent,
    PortalConsentEvidence,
    PortalDocumentVersion,
    PortalFileEvidence,
    PortalIdentityVerification,
    PortalInterestRecord,
    PortalMutationPackage,
    PortalMutationPackageMetadata,
    PortalMutationRequest,
    PortalNetworkTopologyEntry,
    PortalPackagedMutationRequest,
    PortalPasswordResetToken,
    PortalParticipant,
    PortalParticipantAuditEvent,
    PortalParticipantInvitation,
    PortalPilotAllowlistEntry,
    PortalPilotFeedback,
    PortalStateSnapshot,
    PortalUserAccount,
    async_database_runtime_check,
    async_session_for_current_database,
    persistence_enabled,
)
from sunterra_leg_portal.mail import (
    production_smtp_enabled,
    send_transactional_email,
)


LOCAL_DEV_ORIGINS = [
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "http://localhost:5173",
    "http://localhost:5174",
]
BASADINGEN_LEG_ID = "basadingen"
BASADINGEN_LEG_NAME = "SunTerra LEG Basadingen"
PARTICIPANT_BILLING_NOTICE = "Abrechnung und Inkasso bleiben bei Gemeinde/EW."
ADMIN_MFA_ROLES = {Role.LEG_ADMIN, Role.PARTNER_ADMIN, Role.PLATFORM_ADMIN}
TOTP_ISSUER = "SunTerra LEG"
TOTP_PERIOD_SECONDS = 30
TOTP_DIGITS = 6
REQUIRED_PARTICIPANT_DOCUMENT_CONTEXT = "participant_onboarding"
REQUIRED_PARTICIPANT_DOCUMENT_KEYS = (
    "privacy_notice",
    "portal_terms",
    "leg_contract",
)


def _cors_allowed_origins() -> list[str]:
    if os.environ.get("SUNTERRA_ENV") != "production":
        return LOCAL_DEV_ORIGINS

    configured = os.environ.get("SUNTERRA_ALLOWED_ORIGINS", "")
    return [origin.strip() for origin in configured.split(",") if origin.strip()]


class HealthStatus(BaseModel):
    status: str
    service: str
    version: str


class DatabaseReadinessStatus(BaseModel):
    status: str
    query_result: int


class ReadinessStatus(HealthStatus):
    database: DatabaseReadinessStatus


class ParticipantList(BaseModel):
    participants: list[dict[str, str]]


class LoginRequest(BaseModel):
    email: str
    password: str
    totp_code: str | None = None


class PasswordResetRequestCreate(BaseModel):
    email: str


class PasswordResetConfirm(BaseModel):
    token: str
    password: str


class PasswordResetStatusRead(BaseModel):
    status: str


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in_seconds: int
    user: CurrentUser


class TotpEnrollmentResponse(BaseModel):
    secret: str
    otpauth_url: str


class UserAccountRead(BaseModel):
    id: str
    email: str
    display_name: str
    role: Role
    active: bool
    organization: str | None = None


class UserAccountRecord(UserAccountRead):
    password_hash: str | None = None
    password_salt: str | None = None
    mfa_totp_secret: str | None = None
    mfa_totp_enabled: bool = False


class PasswordResetTokenRecord(BaseModel):
    token: str
    account_id: str
    email: str
    expires_at: str
    used_at: str | None = None


class UserAccountCreate(BaseModel):
    email: str
    display_name: str
    role: Role
    password: str


class UserAccountUpdate(BaseModel):
    display_name: str | None = None
    role: Role | None = None
    active: bool | None = None


class UserPasswordReset(BaseModel):
    password: str


class PartnerAdminUserCreate(BaseModel):
    email: str
    display_name: str
    organization: str
    password: str


class ParticipantAccountSetup(BaseModel):
    display_name: str
    password: str


class ParticipantInvitationCreate(BaseModel):
    email: str
    display_name: str


class SelfServiceOnboardingCreate(BaseModel):
    email: str
    display_name: str | None = None
    metering_point_id: str | None = None
    street: str | None = None
    postal_code: str | None = None
    city: str | None = None


class InterestRecordRead(BaseModel):
    id: str
    email: str
    display_name: str
    status: str
    created_at: str


class PilotAllowlistCreate(BaseModel):
    email: str


class PilotAllowlistRead(BaseModel):
    email: str
    created_at: str


class NetworkTopologyEntryCreate(BaseModel):
    metering_point_id: str | None = None
    street: str
    postal_code: str
    city: str


class NetworkTopologyImportCreate(BaseModel):
    source_name: str
    entries: list[NetworkTopologyEntryCreate]


class NetworkTopologyImportRead(BaseModel):
    source_name: str
    imported_entries: int
    active_entries: int
    imported_at: str


class NetworkTopologyEntryRecord(BaseModel):
    id: str
    leg_id: str
    source_name: str
    metering_point_id: str | None = None
    street: str
    postal_code: str
    city: str
    active: bool
    imported_at: str


class PilotFeedbackCreate(BaseModel):
    category: str
    message: str
    context: str | None = None


class PilotFeedbackUpdate(BaseModel):
    status: str
    rollout_relevance: str | None = None
    admin_note: str | None = None


class PilotFeedbackRead(BaseModel):
    id: str
    category: str
    message: str
    context: str | None = None
    user_id: str
    user_email: str
    user_role: Role
    status: str
    rollout_relevance: str | None = None
    admin_note: str | None = None
    reviewed_at: str | None = None
    reviewed_by: str | None = None
    created_at: str


class PilotFeedbackRecord(PilotFeedbackRead):
    pass


class ParticipantInvitationRead(BaseModel):
    token: str
    email: str
    display_name: str
    leg_id: str
    status: str


class ParticipantInvitationRecord(ParticipantInvitationRead):
    participant_id: str | None = None
    source: str = "admin_invitation"


class CommunicationEventRead(BaseModel):
    id: str
    channel: str
    event_type: str
    recipient_email: str
    status: str
    created_at: str


class ParticipantRecord(BaseModel):
    id: str
    email: str
    display_name: str
    leg_id: str
    email_verified: bool
    phone_number: str | None = None
    preferred_contact_channel: str = "email"
    eligibility_status: str = "approved"
    eligibility_review_reason: str | None = None


class IdentityCheckpointRead(BaseModel):
    required_level: str
    current_level: str
    satisfied: bool


class ParticipantIdentityCheckpointRead(IdentityCheckpointRead):
    action: str


class IdentityVerificationRead(BaseModel):
    participant_id: str
    email: str
    display_name: str
    leg_id: str
    source: str
    required_level: str
    current_level: str
    satisfied: bool
    verified_at: str | None = None


class SelfServiceOnboardingResponse(BaseModel):
    access_token: str
    token_type: str
    participant_id: str
    participant_status: str
    identity_checkpoint: IdentityCheckpointRead
    dev_email_verification_token: str | None


class InvitationAcceptResponse(BaseModel):
    access_token: str
    token_type: str
    participant_id: str
    email_verification_required: bool


class EmailVerificationResponse(BaseModel):
    participant_id: str
    email_verified: bool


class ParticipantMembershipRead(BaseModel):
    participant_id: str
    display_name: str
    email: str
    leg_id: str
    leg_name: str
    membership_status: str
    eligibility_status: str
    eligibility_review_reason: str | None = None
    billing_notice: str


class EligibilityReviewDecision(BaseModel):
    decision: str
    reason: str


class EligibilityReviewRead(BaseModel):
    participant_id: str
    eligibility_status: str
    eligibility_review_reason: str | None = None


class ParticipantContactChannelsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phone_number: str | None
    preferred_contact_channel: str


class DocumentVersionCreate(BaseModel):
    document_key: str
    title: str
    version: str
    content: str
    context: str


class DocumentVersionRead(BaseModel):
    id: str
    document_key: str
    title: str
    version: str
    document_hash: str
    context: str
    published_at: str


class CurrentDocumentRead(DocumentVersionRead):
    content: str


class DocumentVersionRecord(DocumentVersionRead):
    content: str


class ConsentEvidenceCreate(BaseModel):
    document_version_id: str
    context: str
    accepted: bool


class ConsentEvidenceRead(BaseModel):
    participant_id: str
    document_version_id: str
    document_key: str
    version: str
    document_hash: str
    context: str
    accepted_at: str


class AddressRead(BaseModel):
    street: str
    postal_code: str
    city: str
    country: str


class MutationRequestCreate(BaseModel):
    mutation_type: str
    mode: str
    requested_quarter: str | None = None
    submitted_on: date | None = None
    event_date: date | None = None
    new_address: AddressRead | None = None
    metering_code: str | None = None
    requested_role: str | None = None
    technology: str | None = None
    installed_capacity_kw: float | None = None
    commissioned_on: date | None = None
    reason: str | None = None


class MutationRequestRead(BaseModel):
    id: str
    participant_id: str
    leg_id: str
    mutation_type: str
    mode: str
    status: str
    quarter: str | None
    quarter_end: str | None
    participant_deadline: str | None
    effective_date: str
    submitted_at: str
    new_address: AddressRead | None = None
    mutation_details: dict[str, str | float]


class AuditEventRead(BaseModel):
    id: str
    action: str
    actor_role: str
    created_at: str
    from_status: str | None = None
    to_status: str | None = None
    reason: str | None = None


class ParticipantContactChannelsRead(BaseModel):
    participant_id: str
    email: str
    phone_number: str | None
    preferred_contact_channel: str
    audit_events: list[AuditEventRead] = Field(default_factory=list)


class MutationRequestRecord(MutationRequestRead):
    reviewed_at: str | None = None
    review_reason: str | None = None
    audit_events: list[AuditEventRead] = Field(default_factory=list)


class ParticipantMutationRequestRead(MutationRequestRecord):
    pass


class AdminMutationParticipantRead(BaseModel):
    participant_id: str
    display_name: str
    email: str


class AdminMutationRequestRead(MutationRequestRecord):
    participant: AdminMutationParticipantRead


class MutationReviewDecision(BaseModel):
    decision: str
    reason: str | None = None


class MutationPackageReadinessDecision(BaseModel):
    ready: bool
    reason: str
    status: str | None = None


class FileEvidenceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_type: str
    purpose: str
    version: str
    filename: str
    content_type: str
    content_base64: str


class FileEvidenceMetadataRead(BaseModel):
    id: str
    mutation_request_id: str
    participant_id: str
    document_type: str
    purpose: str
    version: str
    filename: str
    content_type: str
    sha256_hash: str
    access_protection: str
    retention_status: str
    created_at: str


class FileEvidenceRecord(FileEvidenceMetadataRead):
    content_base64: str


class FileEvidenceContentRead(FileEvidenceMetadataRead):
    content_base64: str


class MutationPackageCreate(BaseModel):
    quarter: str


class MutationPackageRecord(BaseModel):
    mutation_request_id: str
    participant_id: str
    mutation_type: str
    mode: str
    effective_date: str
    new_address: AddressRead | None = None
    mutation_details: dict[str, str | float]


class MutationPackageStatusEvent(BaseModel):
    status: str
    actor_id: str
    actor_role: str
    created_at: str


class MutationPackageRead(BaseModel):
    schema_version: str
    package_id: str
    leg_id: str
    quarter: str
    effective_date: str
    records: list[MutationPackageRecord]
    hash: str
    generated_at: str
    status_history: list[MutationPackageStatusEvent]


class MutationPackageStatusUpdate(BaseModel):
    status: str
    reference: str | None = None
    reason: str | None = None


class MutableMutationPackageStatusEvent(BaseModel):
    status: str
    actor_id: str
    actor_role: str
    created_at: str
    reference: str | None = None
    reason: str | None = None


class AdminMutationPackageMetadataRead(BaseModel):
    package_id: str
    current_status: str
    status_history: list[MutableMutationPackageStatusEvent]


class PartnerMutationPackageStatusEvent(BaseModel):
    status: str
    actor_role: str
    created_at: str
    reference: str | None = None
    reason: str | None = None


class PartnerMutationPackageSummary(BaseModel):
    package_id: str
    leg_id: str
    quarter: str
    effective_date: str
    generated_at: str
    record_count: int
    current_status: str
    status_updated_at: str


class PartnerMutationPackageStatusRead(BaseModel):
    package_id: str
    current_status: str
    status_history: list[PartnerMutationPackageStatusEvent]


class PartnerMutationPackageDetail(PartnerMutationPackageSummary):
    records: list[MutationPackageRecord]
    status_history: list[PartnerMutationPackageStatusEvent]


class PartnerMemberLatestPackageStatus(BaseModel):
    package_id: str
    quarter: str
    effective_date: str
    status: str


class PartnerMemberRead(BaseModel):
    participant_id: str
    display_name: str
    membership_status: str
    reporting_address: AddressRead | None
    latest_package_status: PartnerMemberLatestPackageStatus


class PartnerMemberRegisterRead(BaseModel):
    leg_id: str
    leg_name: str
    members: list[PartnerMemberRead]


class PartnerTaskRead(BaseModel):
    task_id: str
    package_id: str
    leg_id: str
    quarter: str
    effective_date: str
    status: str
    reference: str | None = None
    reason: str | None = None
    created_at: str
    record_count: int


class AdminPartnerTaskMutationRead(BaseModel):
    mutation_request_id: str
    participant_id: str
    mutation_type: str
    effective_date: str


class AdminPartnerTaskRead(PartnerTaskRead):
    records: list[AdminPartnerTaskMutationRead]


INVITATIONS: dict[str, ParticipantInvitationRecord] = {}
COMMUNICATION_EVENTS: list[CommunicationEventRead] = []
USER_ACCOUNTS: dict[str, UserAccountRecord] = {}
PASSWORD_RESET_TOKENS: dict[str, PasswordResetTokenRecord] = {}
PARTICIPANTS: dict[str, ParticipantRecord] = {}
IDENTITY_VERIFICATIONS: dict[str, IdentityVerificationRead] = {}
DOCUMENT_VERSIONS: dict[str, DocumentVersionRecord] = {}
CONSENT_EVIDENCE: dict[str, list[ConsentEvidenceRead]] = {}
INTEREST_RECORDS: dict[str, InterestRecordRead] = {}
PILOT_ALLOWLIST: dict[str, PilotAllowlistRead] = {}
NETWORK_TOPOLOGY_ENTRIES: dict[str, NetworkTopologyEntryRecord] = {}
PILOT_FEEDBACK: dict[str, PilotFeedbackRecord] = {}
MUTATION_REQUESTS: dict[str, list[MutationRequestRecord]] = {}
PARTICIPANT_AUDIT_EVENTS: dict[str, list[AuditEventRead]] = {}
FILE_EVIDENCE: dict[str, list[FileEvidenceRecord]] = {}
MUTATION_PACKAGES: dict[str, MutationPackageRead] = {}
MUTATION_PACKAGE_METADATA: dict[str, AdminMutationPackageMetadataRead] = {}
PACKAGED_MUTATION_REQUEST_IDS: set[str] = set()

FILE_EVIDENCE_PURPOSES = {
    ("mutation_review_supporting_document", "mutation_review"): {
        "access_protection": "mutation_review_owner_and_leg_admin",
        "retention_status": "retained_for_mutation_review",
    },
}


def _participant_invitation_read(
    invitation: ParticipantInvitationRecord,
) -> ParticipantInvitationRead:
    return ParticipantInvitationRead(
        token=invitation.token,
        email=invitation.email,
        display_name=invitation.display_name,
        leg_id=invitation.leg_id,
        status=invitation.status,
    )
SUPPORTED_PARTNER_PACKAGE_STATUSES = {
    "received",
    "in_review",
    "processed",
    "question",
    "technically_not_possible",
}
SUPPORTED_MUTATION_ROLES = {"owner", "tenant", "producer", "prosumer"}
SUPPORTED_REGULAR_MUTATION_TYPES = {
    "address",
    "meter_point",
    "role",
    "generation_asset",
    "entry",
    "exit",
}
SUPPORTED_SPECIAL_MUTATION_TYPES = {
    "move_out",
    "death",
    "owner_tenant_change",
    "meter_point_error",
    "municipality_utility_correction",
}
REGULAR_MUTATION_SUPPORT_ERROR = (
    "Only regular address, meter point, role, generation asset, entry, "
    "and exit mutations are supported"
)
PACKAGE_READY_MUTATION_STATUSES = {"approved", "package_ready"}
NO_PACKAGE_READY_MUTATIONS_DETAIL = (
    "No package-ready un-packaged mutation requests for quarter"
)
PORTAL_STATE_SNAPSHOT_ID = "default"
DEFAULT_DEMO_PASSWORD = "SunTerra123!"
PASSWORD_RESET_TOKEN_TTL_SECONDS = 60 * 60
DEVELOPMENT_MFA_SATISFIED_ACCOUNT_IDS = {
    "dev-leg-admin",
    "dev-partner-admin",
    "dev-platform-admin",
}


def legacy_portal_state_enabled() -> bool:
    return os.environ.get("SUNTERRA_ENABLE_LEGACY_PORTAL_STATE") == "1"


def _normalized_email(email: str) -> str:
    return email.strip().lower()


def _registration_mode() -> str:
    return os.environ.get("SUNTERRA_REGISTRATION_MODE", "public").strip().lower()


def _pilot_registration_enabled() -> bool:
    return _registration_mode() == "pilot"


def _public_rollout_gate_incomplete() -> bool:
    return (
        os.environ.get("SUNTERRA_ENV") == "production"
        and _registration_mode() == "public"
        and os.environ.get("SUNTERRA_PUBLIC_ROLLOUT_APPROVED") != "1"
    )


def _env_pilot_allowlist() -> set[str]:
    configured = os.environ.get("SUNTERRA_PILOT_ALLOWLIST_EMAILS", "")
    return {
        _normalized_email(email)
        for email in configured.split(",")
        if email.strip()
    }


def _email_has_pending_invitation(email: str) -> bool:
    normalized_email = _normalized_email(email)
    return any(
        _normalized_email(invitation.email) == normalized_email
        for invitation in INVITATIONS.values()
    )


def _email_is_pilot_allowed(email: str) -> bool:
    normalized_email = _normalized_email(email)
    return (
        normalized_email in _env_pilot_allowlist()
        or normalized_email in PILOT_ALLOWLIST
        or _email_has_pending_invitation(email)
    )


async def _async_email_has_pending_invitation(
    session: AsyncSession,
    email: str,
) -> bool:
    normalized_email = _normalized_email(email)
    rows = await _async_table_rows(session, PortalParticipantInvitation)
    return any(_normalized_email(row.email) == normalized_email for row in rows)


async def _async_email_is_pilot_allowed(
    session: AsyncSession,
    email: str,
) -> bool:
    normalized_email = _normalized_email(email)
    if (
        normalized_email in _env_pilot_allowlist()
        or normalized_email in PILOT_ALLOWLIST
        or _email_has_pending_invitation(email)
    ):
        return True

    row = await session.get(PortalPilotAllowlistEntry, normalized_email)
    if row is not None:
        record = _pilot_allowlist_from_row(row)
        PILOT_ALLOWLIST[record.email] = record
        return True

    return await _async_email_has_pending_invitation(session, email)


def _interest_record_for(
    onboarding_request: SelfServiceOnboardingCreate,
) -> InterestRecordRead:
    normalized_email = _normalized_email(onboarding_request.email)
    existing = INTEREST_RECORDS.get(normalized_email)
    if existing is not None:
        return existing

    record = InterestRecordRead(
        id=uuid4().hex,
        email=normalized_email,
        display_name=onboarding_request.display_name or "Interessent",
        status="interest_recorded",
        created_at=datetime.now(UTC).isoformat(),
    )
    INTEREST_RECORDS[normalized_email] = record
    return record


async def _async_interest_record_for(
    session: AsyncSession,
    onboarding_request: SelfServiceOnboardingCreate,
) -> InterestRecordRead:
    normalized_email = _normalized_email(onboarding_request.email)
    row = await session.get(PortalInterestRecord, normalized_email)
    if row is not None:
        record = _interest_record_from_row(row)
        INTEREST_RECORDS[record.email] = record
        return record

    record = _interest_record_for(onboarding_request)
    session.add(_interest_record_row(record))
    return record


def _interest_record_from_row(row: PortalInterestRecord) -> InterestRecordRead:
    return InterestRecordRead(
        id=row.id,
        email=row.email,
        display_name=row.display_name,
        status=row.status,
        created_at=row.created_at,
    )


def _interest_record_row(record: InterestRecordRead) -> PortalInterestRecord:
    return PortalInterestRecord(
        id=record.id,
        email=record.email,
        display_name=record.display_name,
        status=record.status,
        created_at=record.created_at,
    )


def _pilot_allowlist_from_row(row: PortalPilotAllowlistEntry) -> PilotAllowlistRead:
    return PilotAllowlistRead(email=row.email, created_at=row.created_at)


def _pilot_allowlist_row(record: PilotAllowlistRead) -> PortalPilotAllowlistEntry:
    return PortalPilotAllowlistEntry(
        email=record.email,
        created_at=record.created_at,
    )


def _normalized_topology_text(value: str | None) -> str:
    return " ".join((value or "").strip().lower().split())


def _network_topology_entry_from_row(
    row: PortalNetworkTopologyEntry,
) -> NetworkTopologyEntryRecord:
    return NetworkTopologyEntryRecord(
        id=row.id,
        leg_id=row.leg_id,
        source_name=row.source_name,
        metering_point_id=row.metering_point_id,
        street=row.street,
        postal_code=row.postal_code,
        city=row.city,
        active=row.active,
        imported_at=row.imported_at,
    )


def _network_topology_entry_row(
    record: NetworkTopologyEntryRecord,
) -> PortalNetworkTopologyEntry:
    return PortalNetworkTopologyEntry(
        id=record.id,
        leg_id=record.leg_id,
        source_name=record.source_name,
        metering_point_id=record.metering_point_id,
        street=record.street,
        postal_code=record.postal_code,
        city=record.city,
        active=record.active,
        imported_at=record.imported_at,
    )


def _pilot_feedback_from_row(row: PortalPilotFeedback) -> PilotFeedbackRecord:
    return PilotFeedbackRecord(
        id=row.id,
        category=row.category,
        message=row.message,
        context=row.context,
        user_id=row.user_id,
        user_email=row.user_email,
        user_role=Role(row.user_role),
        status=row.status,
        rollout_relevance=row.rollout_relevance,
        admin_note=row.admin_note,
        reviewed_at=row.reviewed_at,
        reviewed_by=row.reviewed_by,
        created_at=row.created_at,
    )


def _pilot_feedback_row(record: PilotFeedbackRecord) -> PortalPilotFeedback:
    return PortalPilotFeedback(
        id=record.id,
        category=record.category,
        message=record.message,
        context=record.context,
        user_id=record.user_id,
        user_email=record.user_email,
        user_role=record.user_role.value,
        status=record.status,
        rollout_relevance=record.rollout_relevance,
        admin_note=record.admin_note,
        reviewed_at=record.reviewed_at,
        reviewed_by=record.reviewed_by,
        created_at=record.created_at,
    )


def _network_topology_match_from_entries(
    onboarding_request: SelfServiceOnboardingCreate,
    entries: list[NetworkTopologyEntryRecord],
) -> NetworkTopologyEntryRecord | None:
    metering_point_id = _normalized_topology_text(onboarding_request.metering_point_id)
    street = _normalized_topology_text(onboarding_request.street)
    postal_code = _normalized_topology_text(onboarding_request.postal_code)
    city = _normalized_topology_text(onboarding_request.city)

    for entry in sorted(entries, key=lambda item: (item.imported_at, item.id), reverse=True):
        if not entry.active:
            continue
        if metering_point_id and metering_point_id == _normalized_topology_text(
            entry.metering_point_id,
        ):
            return entry
        if street and postal_code and city:
            if (
                street == _normalized_topology_text(entry.street)
                and postal_code == _normalized_topology_text(entry.postal_code)
                and city == _normalized_topology_text(entry.city)
            ):
                return entry

    return None


async def _async_network_topology_match(
    session: AsyncSession,
    onboarding_request: SelfServiceOnboardingCreate,
) -> NetworkTopologyEntryRecord | None:
    result = await session.execute(
        select(PortalNetworkTopologyEntry).where(
            PortalNetworkTopologyEntry.active == True,  # noqa: E712
        ),
    )
    return _network_topology_match_from_entries(
        onboarding_request,
        [_network_topology_entry_from_row(row) for row in result.scalars().all()],
    )


def _eligibility_reason_for_topology_match(
    match: NetworkTopologyEntryRecord,
) -> str:
    return f"Netzwerktopologie vorgeprueft: {match.source_name}"


def _password_hash(password: str, salt: str) -> str:
    return pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("ascii"),
        120_000,
    ).hex()


def _password_salt() -> str:
    return secrets.token_hex(16)


def _account_with_password(
    *,
    user_id: str,
    email: str,
    display_name: str,
    role: Role,
    password: str,
    active: bool = True,
    organization: str | None = None,
) -> UserAccountRecord:
    salt = _password_salt()
    return UserAccountRecord(
        id=user_id,
        email=email,
        display_name=display_name,
        role=role,
        active=active,
        organization=organization,
        password_hash=_password_hash(password, salt),
        password_salt=salt,
    )


def _set_account_password(account: UserAccountRecord, password: str) -> None:
    account.password_salt = _password_salt()
    account.password_hash = _password_hash(password, account.password_salt)


def _verify_account_password(account: UserAccountRecord, password: str) -> bool:
    if account.password_hash is None or account.password_salt is None:
        return False

    return secrets.compare_digest(
        account.password_hash,
        _password_hash(password, account.password_salt),
    )


def _password_reset_record_for_account(
    account: UserAccountRecord,
) -> PasswordResetTokenRecord:
    return PasswordResetTokenRecord(
        token=secrets.token_urlsafe(32),
        account_id=account.id,
        email=_normalized_email(account.email),
        expires_at=(
            datetime.now(UTC) + timedelta(seconds=PASSWORD_RESET_TOKEN_TTL_SECONDS)
        ).isoformat(),
    )


def _password_reset_token_valid(record: PasswordResetTokenRecord) -> bool:
    return (
        record.used_at is None
        and datetime.fromisoformat(record.expires_at) > datetime.now(UTC)
    )


def _totp_secret() -> str:
    return b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _totp_key(secret: str) -> bytes:
    normalized = secret.replace(" ", "").upper()
    padding = "=" * (-len(normalized) % 8)
    return b32decode(normalized + padding, casefold=True)


def _totp_code(secret: str, timestamp: datetime) -> str:
    counter = int(timestamp.timestamp()) // TOTP_PERIOD_SECONDS
    digest = hmac.new(_totp_key(secret), struct.pack(">Q", counter), sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return f"{value % (10 ** TOTP_DIGITS):0{TOTP_DIGITS}d}"


def _verify_totp_code(secret: str, code: str | None) -> bool:
    if code is None:
        return False
    normalized_code = code.strip()
    if not normalized_code.isdigit() or len(normalized_code) != TOTP_DIGITS:
        return False

    now = datetime.now(UTC)
    return any(
        secrets.compare_digest(
            normalized_code,
            _totp_code(
                secret,
                now + timedelta(seconds=TOTP_PERIOD_SECONDS * offset),
            ),
        )
        for offset in (-1, 0, 1)
    )


def _account_requires_totp(account: UserAccountRecord) -> bool:
    return (
        account.role in ADMIN_MFA_ROLES
        and account.mfa_totp_enabled
        and account.mfa_totp_secret is not None
    )


def _login_mfa_satisfied(
    account: UserAccountRecord,
    credentials: LoginRequest,
) -> bool:
    if account.role not in ADMIN_MFA_ROLES:
        return True
    if _account_requires_totp(account):
        return _verify_totp_code(account.mfa_totp_secret or "", credentials.totp_code)
    return (
        development_auth_enabled()
        and account.id in DEVELOPMENT_MFA_SATISFIED_ACCOUNT_IDS
    )


def _totp_otpauth_url(account: UserAccountRecord) -> str:
    label = f"{quote(TOTP_ISSUER)}:{quote(account.email)}"
    issuer = quote(TOTP_ISSUER)
    return (
        f"otpauth://totp/{label}"
        f"?secret={account.mfa_totp_secret}"
        f"&issuer={issuer}"
        "&algorithm=SHA1"
        f"&digits={TOTP_DIGITS}"
        f"&period={TOTP_PERIOD_SECONDS}"
    )


def _user_read(account: UserAccountRecord) -> UserAccountRead:
    return UserAccountRead(
        **account.model_dump(
            exclude={
                "password_hash",
                "password_salt",
                "mfa_totp_secret",
                "mfa_totp_enabled",
            },
        ),
    )


async def _async_ensure_seed_user_accounts(session: AsyncSession) -> None:
    if not development_auth_enabled():
        return

    _ensure_seed_user_accounts()
    seed_added = False
    for user_id in [
        "dev-participant",
        "dev-leg-admin",
        "dev-partner-admin",
        "dev-platform-admin",
    ]:
        if await session.get(PortalUserAccount, user_id) is None:
            session.add(_user_account_row(USER_ACCOUNTS[user_id]))
            seed_added = True
    if seed_added:
        await session.commit()


async def _async_user_account_by_email(
    session: AsyncSession,
    email: str,
) -> UserAccountRecord | None:
    await _async_ensure_seed_user_accounts(session)
    result = await session.execute(
        select(PortalUserAccount)
        .where(func.lower(PortalUserAccount.email) == email.lower())
        .limit(1),
    )
    row = result.scalars().first()
    if row is None:
        return None

    return _user_account_from_row(row)


async def _async_user_account_by_id(
    session: AsyncSession,
    user_id: str,
) -> UserAccountRecord | None:
    await _async_ensure_seed_user_accounts(session)
    row = await session.get(PortalUserAccount, user_id)
    if row is None:
        return None

    return _user_account_from_row(row)


async def _async_user_accounts(session: AsyncSession) -> list[UserAccountRecord]:
    await _async_ensure_seed_user_accounts(session)
    result = await session.execute(
        select(PortalUserAccount).order_by(
            PortalUserAccount.email,
            PortalUserAccount.id,
        ),
    )
    return [_user_account_from_row(row) for row in result.scalars().all()]


def _current_user_from_account(user_id: str) -> CurrentUser | None:
    _ensure_seed_user_accounts()
    account = USER_ACCOUNTS.get(user_id)
    if account is None or not account.active:
        return None

    return CurrentUser(
        id=account.id,
        email=account.email,
        display_name=account.display_name,
        role=account.role,
        mfa_satisfied=False,
    )


def _ensure_seed_user_accounts() -> None:
    if not development_auth_enabled():
        return

    seeds = [
        (
            "dev-participant",
            "participant@example.test",
            "Teilnehmer Demo",
            Role.PARTICIPANT,
            None,
        ),
        (
            "dev-leg-admin",
            "leg-admin@example.test",
            "LEG Admin Demo",
            Role.LEG_ADMIN,
            None,
        ),
        (
            "dev-partner-admin",
            "partner-admin@example.test",
            "Partner Admin Demo",
            Role.PARTNER_ADMIN,
            "Gemeinde/EW Basadingen",
        ),
        (
            "dev-platform-admin",
            "platform-admin@example.test",
            "Plattform Admin Demo",
            Role.PLATFORM_ADMIN,
            None,
        ),
    ]
    for user_id, email, display_name, role, organization in seeds:
        if user_id not in USER_ACCOUNTS:
            USER_ACCOUNTS[user_id] = _account_with_password(
                user_id=user_id,
                email=email,
                display_name=display_name,
                role=role,
                password=DEFAULT_DEMO_PASSWORD,
                organization=organization,
            )


set_jwt_user_resolver(_current_user_from_account)


def _dump_models(values: list[BaseModel]) -> list[dict]:
    return [value.model_dump(mode="json") for value in values]


def _dump_model_mapping(values: dict[str, BaseModel]) -> dict[str, dict]:
    return {
        key: value.model_dump(mode="json")
        for key, value in values.items()
    }


def _dump_model_list_mapping(values: dict[str, list[BaseModel]]) -> dict[str, list[dict]]:
    return {
        key: _dump_models(nested_values)
        for key, nested_values in values.items()
    }


def _portal_state_payload() -> dict:
    return {
        "invitations": _dump_model_mapping(INVITATIONS),
        "communication_events": _dump_models(COMMUNICATION_EVENTS),
        "user_accounts": _dump_model_mapping(USER_ACCOUNTS),
        "password_reset_tokens": _dump_model_mapping(PASSWORD_RESET_TOKENS),
        "participants": _dump_model_mapping(PARTICIPANTS),
        "network_topology_entries": _dump_model_mapping(NETWORK_TOPOLOGY_ENTRIES),
        "identity_verifications": _dump_model_mapping(IDENTITY_VERIFICATIONS),
        "document_versions": _dump_model_mapping(DOCUMENT_VERSIONS),
        "consent_evidence": _dump_model_list_mapping(CONSENT_EVIDENCE),
        "mutation_requests": _dump_model_list_mapping(MUTATION_REQUESTS),
        "participant_audit_events": _dump_model_list_mapping(
            PARTICIPANT_AUDIT_EVENTS,
        ),
        "file_evidence": _dump_model_list_mapping(FILE_EVIDENCE),
        "mutation_packages": _dump_model_mapping(MUTATION_PACKAGES),
        "mutation_package_metadata": _dump_model_mapping(MUTATION_PACKAGE_METADATA),
        "packaged_mutation_request_ids": sorted(PACKAGED_MUTATION_REQUEST_IDS),
        "dev_participant_users": _dump_model_mapping(DEV_PARTICIPANT_USERS),
    }


def _load_model_mapping(
    payload: dict,
    key: str,
    model: type[BaseModel],
) -> dict[str, BaseModel]:
    return {
        item_key: model.model_validate(item)
        for item_key, item in payload.get(key, {}).items()
    }


def _load_model_list_mapping(
    payload: dict,
    key: str,
    model: type[BaseModel],
) -> dict[str, list[BaseModel]]:
    return {
        item_key: [model.model_validate(item) for item in nested_items]
        for item_key, nested_items in payload.get(key, {}).items()
    }


def _restore_portal_state_payload(payload: dict) -> None:
    INVITATIONS.clear()
    INVITATIONS.update(
        _load_model_mapping(payload, "invitations", ParticipantInvitationRecord),
    )
    COMMUNICATION_EVENTS.clear()
    COMMUNICATION_EVENTS.extend(
        CommunicationEventRead.model_validate(item)
        for item in payload.get("communication_events", [])
    )
    USER_ACCOUNTS.clear()
    USER_ACCOUNTS.update(_load_model_mapping(payload, "user_accounts", UserAccountRecord))
    _ensure_seed_user_accounts()
    PASSWORD_RESET_TOKENS.clear()
    PASSWORD_RESET_TOKENS.update(
        _load_model_mapping(
            payload,
            "password_reset_tokens",
            PasswordResetTokenRecord,
        ),
    )
    PARTICIPANTS.clear()
    PARTICIPANTS.update(_load_model_mapping(payload, "participants", ParticipantRecord))
    NETWORK_TOPOLOGY_ENTRIES.clear()
    NETWORK_TOPOLOGY_ENTRIES.update(
        _load_model_mapping(
            payload,
            "network_topology_entries",
            NetworkTopologyEntryRecord,
        ),
    )
    IDENTITY_VERIFICATIONS.clear()
    IDENTITY_VERIFICATIONS.update(
        _load_model_mapping(
            payload,
            "identity_verifications",
            IdentityVerificationRead,
        ),
    )
    DOCUMENT_VERSIONS.clear()
    DOCUMENT_VERSIONS.update(
        _load_model_mapping(payload, "document_versions", DocumentVersionRecord),
    )
    CONSENT_EVIDENCE.clear()
    CONSENT_EVIDENCE.update(
        _load_model_list_mapping(payload, "consent_evidence", ConsentEvidenceRead),
    )
    MUTATION_REQUESTS.clear()
    MUTATION_REQUESTS.update(
        _load_model_list_mapping(
            payload,
            "mutation_requests",
            MutationRequestRecord,
        ),
    )
    PARTICIPANT_AUDIT_EVENTS.clear()
    PARTICIPANT_AUDIT_EVENTS.update(
        _load_model_list_mapping(
            payload,
            "participant_audit_events",
            AuditEventRead,
        ),
    )
    FILE_EVIDENCE.clear()
    FILE_EVIDENCE.update(
        _load_model_list_mapping(payload, "file_evidence", FileEvidenceRecord),
    )
    MUTATION_PACKAGES.clear()
    MUTATION_PACKAGES.update(
        _load_model_mapping(payload, "mutation_packages", MutationPackageRead),
    )
    MUTATION_PACKAGE_METADATA.clear()
    MUTATION_PACKAGE_METADATA.update(
        _load_model_mapping(
            payload,
            "mutation_package_metadata",
            AdminMutationPackageMetadataRead,
        ),
    )
    PACKAGED_MUTATION_REQUEST_IDS.clear()
    PACKAGED_MUTATION_REQUEST_IDS.update(
        payload.get("packaged_mutation_request_ids", []),
    )
    DEV_PARTICIPANT_USERS.clear()
    DEV_PARTICIPANT_USERS.update(
        _load_model_mapping(payload, "dev_participant_users", CurrentUser),
    )


def _participant_from_row(row: PortalParticipant) -> ParticipantRecord:
    return ParticipantRecord(
        id=row.id,
        email=row.email,
        display_name=row.display_name,
        leg_id=row.leg_id,
        email_verified=row.email_verified,
        phone_number=row.phone_number,
        preferred_contact_channel=row.preferred_contact_channel,
        eligibility_status=getattr(row, "eligibility_status", "approved"),
        eligibility_review_reason=getattr(row, "eligibility_review_reason", None),
    )


def _participant_row(participant: ParticipantRecord) -> PortalParticipant:
    return PortalParticipant(
        id=participant.id,
        email=participant.email,
        display_name=participant.display_name,
        leg_id=participant.leg_id,
        email_verified=participant.email_verified,
        phone_number=participant.phone_number,
        preferred_contact_channel=participant.preferred_contact_channel,
        eligibility_status=participant.eligibility_status,
        eligibility_review_reason=participant.eligibility_review_reason,
    )


def _invitation_from_row(row: PortalParticipantInvitation) -> ParticipantInvitationRecord:
    return ParticipantInvitationRecord(
        token=row.token,
        email=row.email,
        display_name=row.display_name,
        leg_id=row.leg_id,
        status=row.status,
        participant_id=row.participant_id,
        source=row.source,
    )


def _invitation_row(
    invitation: ParticipantInvitationRecord,
) -> PortalParticipantInvitation:
    return PortalParticipantInvitation(
        token=invitation.token,
        email=invitation.email,
        display_name=invitation.display_name,
        leg_id=invitation.leg_id,
        status=invitation.status,
        participant_id=invitation.participant_id,
        source=invitation.source,
    )


def _identity_verification_from_row(
    row: PortalIdentityVerification,
) -> IdentityVerificationRead:
    return IdentityVerificationRead(
        participant_id=row.participant_id,
        email=row.email,
        display_name=row.display_name,
        leg_id=row.leg_id,
        source=row.source,
        required_level=row.required_level,
        current_level=row.current_level,
        satisfied=row.satisfied,
        verified_at=row.verified_at,
    )


def _identity_verification_row(
    verification: IdentityVerificationRead,
) -> PortalIdentityVerification:
    return PortalIdentityVerification(
        participant_id=verification.participant_id,
        email=verification.email,
        display_name=verification.display_name,
        leg_id=verification.leg_id,
        source=verification.source,
        required_level=verification.required_level,
        current_level=verification.current_level,
        satisfied=verification.satisfied,
        verified_at=verification.verified_at,
    )


def _document_version_from_row(row: PortalDocumentVersion) -> DocumentVersionRecord:
    return DocumentVersionRecord(
        id=row.id,
        document_key=row.document_key,
        title=row.title,
        version=row.version,
        document_hash=row.document_hash,
        context=row.context,
        published_at=row.published_at,
        content=row.content,
    )


def _document_version_row(document: DocumentVersionRecord) -> PortalDocumentVersion:
    return PortalDocumentVersion(
        id=document.id,
        document_key=document.document_key,
        title=document.title,
        version=document.version,
        document_hash=document.document_hash,
        context=document.context,
        published_at=document.published_at,
        content=document.content,
    )


def _consent_evidence_from_row(row: PortalConsentEvidence) -> ConsentEvidenceRead:
    return ConsentEvidenceRead(
        participant_id=row.participant_id,
        document_version_id=row.document_version_id,
        document_key=row.document_key,
        version=row.version,
        document_hash=row.document_hash,
        context=row.context,
        accepted_at=row.accepted_at,
    )


def _consent_evidence_row(consent: ConsentEvidenceRead) -> PortalConsentEvidence:
    return PortalConsentEvidence(
        participant_id=consent.participant_id,
        document_version_id=consent.document_version_id,
        accepted_at=consent.accepted_at,
        document_key=consent.document_key,
        version=consent.version,
        document_hash=consent.document_hash,
        context=consent.context,
    )


def _mutation_request_from_row(row: PortalMutationRequest) -> MutationRequestRecord:
    return MutationRequestRecord.model_validate(json.loads(row.payload_json))


def _mutation_request_row(
    mutation_request: MutationRequestRecord,
) -> PortalMutationRequest:
    return PortalMutationRequest(
        id=mutation_request.id,
        participant_id=mutation_request.participant_id,
        leg_id=mutation_request.leg_id,
        status=mutation_request.status,
        submitted_at=mutation_request.submitted_at,
        payload_json=json.dumps(
            mutation_request.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        ),
    )


def _participant_audit_event_from_row(row: PortalParticipantAuditEvent) -> AuditEventRead:
    return AuditEventRead.model_validate(json.loads(row.payload_json))


def _participant_audit_event_row(
    participant_id: str,
    audit_event: AuditEventRead,
) -> PortalParticipantAuditEvent:
    return PortalParticipantAuditEvent(
        participant_id=participant_id,
        id=audit_event.id,
        created_at=audit_event.created_at,
        payload_json=json.dumps(
            audit_event.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        ),
    )


def _mutation_package_from_row(row: PortalMutationPackage) -> MutationPackageRead:
    return MutationPackageRead.model_validate(json.loads(row.payload_json))


def _mutation_package_row(package: MutationPackageRead) -> PortalMutationPackage:
    return PortalMutationPackage(
        package_id=package.package_id,
        leg_id=package.leg_id,
        quarter=package.quarter,
        generated_at=package.generated_at,
        payload_json=json.dumps(
            package.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        ),
    )


def _file_evidence_from_row(row: PortalFileEvidence) -> FileEvidenceRecord:
    return FileEvidenceRecord.model_validate(json.loads(row.payload_json))


def _file_evidence_row(evidence: FileEvidenceRecord) -> PortalFileEvidence:
    return PortalFileEvidence(
        id=evidence.id,
        mutation_request_id=evidence.mutation_request_id,
        participant_id=evidence.participant_id,
        created_at=evidence.created_at,
        payload_json=json.dumps(
            evidence.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        ),
    )


def _mutation_package_metadata_from_row(
    row: PortalMutationPackageMetadata,
) -> AdminMutationPackageMetadataRead:
    return AdminMutationPackageMetadataRead.model_validate(json.loads(row.payload_json))


def _mutation_package_metadata_row(
    metadata: AdminMutationPackageMetadataRead,
) -> PortalMutationPackageMetadata:
    return PortalMutationPackageMetadata(
        package_id=metadata.package_id,
        current_status=metadata.current_status,
        payload_json=json.dumps(
            metadata.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        ),
    )


def _user_account_from_row(row: PortalUserAccount) -> UserAccountRecord:
    return UserAccountRecord(
        id=row.id,
        email=row.email,
        display_name=row.display_name,
        role=Role(row.role),
        active=row.active,
        organization=row.organization,
        password_hash=row.password_hash,
        password_salt=row.password_salt,
        mfa_totp_secret=row.mfa_totp_secret,
        mfa_totp_enabled=row.mfa_totp_enabled,
    )


def _user_account_row(account: UserAccountRecord) -> PortalUserAccount:
    return PortalUserAccount(
        id=account.id,
        email=account.email,
        display_name=account.display_name,
        role=account.role.value,
        active=account.active,
        organization=account.organization,
        password_hash=account.password_hash,
        password_salt=account.password_salt,
        mfa_totp_secret=account.mfa_totp_secret,
        mfa_totp_enabled=account.mfa_totp_enabled,
    )


def _password_reset_token_from_row(
    row: PortalPasswordResetToken,
) -> PasswordResetTokenRecord:
    return PasswordResetTokenRecord(
        token=row.token,
        account_id=row.account_id,
        email=row.email,
        expires_at=row.expires_at,
        used_at=row.used_at,
    )


def _password_reset_token_row(
    token: PasswordResetTokenRecord,
) -> PortalPasswordResetToken:
    return PortalPasswordResetToken(
        token=token.token,
        account_id=token.account_id,
        email=token.email,
        expires_at=token.expires_at,
        used_at=token.used_at,
    )


def _communication_event_from_row(
    row: PortalCommunicationEvent,
) -> CommunicationEventRead:
    return CommunicationEventRead(
        id=row.id,
        channel=row.channel,
        event_type=row.event_type,
        recipient_email=row.recipient_email,
        status=row.status,
        created_at=row.created_at,
    )


def _communication_event_row(
    event: CommunicationEventRead,
) -> PortalCommunicationEvent:
    return PortalCommunicationEvent(
        id=event.id,
        channel=event.channel,
        event_type=event.event_type,
        recipient_email=event.recipient_email,
        status=event.status,
        created_at=event.created_at,
    )


def _replace_table_rows(session: Session, row_type, rows: list) -> None:
    for existing in session.exec(select(row_type)).all():
        session.delete(existing)

    for row in rows:
        session.add(row)


def _has_table_rows(session: Session, row_types: list) -> bool:
    return any(
        session.exec(select(row_type).limit(1)).first() is not None
        for row_type in row_types
    )


def _has_table_backed_onboarding_state(session: Session) -> bool:
    return _has_table_rows(
        session,
        [
            PortalParticipantInvitation,
            PortalParticipant,
            PortalNetworkTopologyEntry,
            PortalIdentityVerification,
            PortalUserAccount,
            PortalPasswordResetToken,
            PortalCommunicationEvent,
        ],
    )


def _has_table_backed_document_state(session: Session) -> bool:
    return _has_table_rows(session, [PortalDocumentVersion])


def _has_table_backed_consent_state(session: Session) -> bool:
    return _has_table_rows(session, [PortalConsentEvidence])


def _has_table_backed_mutation_state(session: Session) -> bool:
    return _has_table_rows(
        session,
        [PortalMutationRequest, PortalParticipantAuditEvent],
    )


def _has_table_backed_package_state(session: Session) -> bool:
    return _has_table_rows(
        session,
        [
            PortalMutationPackage,
            PortalMutationPackageMetadata,
            PortalPackagedMutationRequest,
        ],
    )


def _has_table_backed_file_evidence_state(session: Session) -> bool:
    return _has_table_rows(session, [PortalFileEvidence])


def _restore_table_backed_onboarding_state(session: Session) -> None:
    INVITATIONS.clear()
    INVITATIONS.update(
        {
            row.token: _invitation_from_row(row)
            for row in session.exec(select(PortalParticipantInvitation)).all()
        },
    )

    PARTICIPANTS.clear()
    PARTICIPANTS.update(
        {
            row.id: _participant_from_row(row)
            for row in session.exec(select(PortalParticipant)).all()
        },
    )

    NETWORK_TOPOLOGY_ENTRIES.clear()
    NETWORK_TOPOLOGY_ENTRIES.update(
        {
            row.id: _network_topology_entry_from_row(row)
            for row in session.exec(select(PortalNetworkTopologyEntry)).all()
        },
    )

    IDENTITY_VERIFICATIONS.clear()
    IDENTITY_VERIFICATIONS.update(
        {
            row.participant_id: _identity_verification_from_row(row)
            for row in session.exec(select(PortalIdentityVerification)).all()
        },
    )

    USER_ACCOUNTS.clear()
    USER_ACCOUNTS.update(
        {
            row.id: _user_account_from_row(row)
            for row in session.exec(select(PortalUserAccount)).all()
        },
    )
    _ensure_seed_user_accounts()

    PASSWORD_RESET_TOKENS.clear()
    PASSWORD_RESET_TOKENS.update(
        {
            row.token: _password_reset_token_from_row(row)
            for row in session.exec(select(PortalPasswordResetToken)).all()
        },
    )

    DEV_PARTICIPANT_USERS.clear()
    for account in USER_ACCOUNTS.values():
        if account.role == Role.PARTICIPANT and account.active:
            register_dev_participant_user(
                participant_id=account.id,
                email=account.email,
                display_name=account.display_name,
            )

    COMMUNICATION_EVENTS.clear()
    COMMUNICATION_EVENTS.extend(
        _communication_event_from_row(row)
        for row in sorted(
            session.exec(select(PortalCommunicationEvent)).all(),
            key=lambda item: (item.created_at, item.id),
        )
    )


def _restore_table_backed_document_state(session: Session) -> None:
    DOCUMENT_VERSIONS.clear()
    DOCUMENT_VERSIONS.update(
        {
            row.id: _document_version_from_row(row)
            for row in sorted(
                session.exec(select(PortalDocumentVersion)).all(),
                key=lambda item: (item.published_at, item.id),
            )
        },
    )


def _restore_table_backed_consent_state(session: Session) -> None:
    CONSENT_EVIDENCE.clear()
    for row in sorted(
        session.exec(select(PortalConsentEvidence)).all(),
        key=lambda item: (item.accepted_at, item.participant_id, item.document_version_id),
    ):
        consent = _consent_evidence_from_row(row)
        CONSENT_EVIDENCE.setdefault(consent.participant_id, []).append(consent)


def _restore_table_backed_mutation_state(session: Session) -> None:
    MUTATION_REQUESTS.clear()
    for row in sorted(
        session.exec(select(PortalMutationRequest)).all(),
        key=lambda item: (item.submitted_at, item.id),
    ):
        mutation_request = _mutation_request_from_row(row)
        MUTATION_REQUESTS.setdefault(mutation_request.participant_id, []).append(
            mutation_request,
        )

    PARTICIPANT_AUDIT_EVENTS.clear()
    for row in sorted(
        session.exec(select(PortalParticipantAuditEvent)).all(),
        key=lambda item: (item.created_at, item.participant_id, item.id),
    ):
        audit_event = _participant_audit_event_from_row(row)
        PARTICIPANT_AUDIT_EVENTS.setdefault(row.participant_id, []).append(audit_event)


def _restore_table_backed_package_state(session: Session) -> None:
    MUTATION_PACKAGES.clear()
    MUTATION_PACKAGES.update(
        {
            row.package_id: _mutation_package_from_row(row)
            for row in sorted(
                session.exec(select(PortalMutationPackage)).all(),
                key=lambda item: (item.generated_at, item.package_id),
            )
        },
    )

    MUTATION_PACKAGE_METADATA.clear()
    MUTATION_PACKAGE_METADATA.update(
        {
            row.package_id: _mutation_package_metadata_from_row(row)
            for row in session.exec(select(PortalMutationPackageMetadata)).all()
        },
    )

    PACKAGED_MUTATION_REQUEST_IDS.clear()
    PACKAGED_MUTATION_REQUEST_IDS.update(
        row.mutation_request_id
        for row in session.exec(select(PortalPackagedMutationRequest)).all()
    )
    if not PACKAGED_MUTATION_REQUEST_IDS:
        PACKAGED_MUTATION_REQUEST_IDS.update(
            record.mutation_request_id
            for package in MUTATION_PACKAGES.values()
            for record in package.records
        )


def _restore_table_backed_file_evidence_state(session: Session) -> None:
    FILE_EVIDENCE.clear()
    for row in sorted(
        session.exec(select(PortalFileEvidence)).all(),
        key=lambda item: (item.created_at, item.mutation_request_id, item.id),
    ):
        evidence = _file_evidence_from_row(row)
        FILE_EVIDENCE.setdefault(evidence.mutation_request_id, []).append(evidence)


def _save_table_backed_onboarding_state(session: Session) -> None:
    _ensure_seed_user_accounts()
    _replace_table_rows(
        session,
        PortalParticipantInvitation,
        [_invitation_row(invitation) for invitation in INVITATIONS.values()],
    )
    _replace_table_rows(
        session,
        PortalParticipant,
        [_participant_row(participant) for participant in PARTICIPANTS.values()],
    )
    _replace_table_rows(
        session,
        PortalNetworkTopologyEntry,
        [
            _network_topology_entry_row(record)
            for record in NETWORK_TOPOLOGY_ENTRIES.values()
        ],
    )
    _replace_table_rows(
        session,
        PortalIdentityVerification,
        [
            _identity_verification_row(verification)
            for verification in IDENTITY_VERIFICATIONS.values()
        ],
    )
    _replace_table_rows(
        session,
        PortalUserAccount,
        [_user_account_row(account) for account in USER_ACCOUNTS.values()],
    )
    _replace_table_rows(
        session,
        PortalPasswordResetToken,
        [
            _password_reset_token_row(token)
            for token in PASSWORD_RESET_TOKENS.values()
        ],
    )
    _replace_table_rows(
        session,
        PortalCommunicationEvent,
        [_communication_event_row(event) for event in COMMUNICATION_EVENTS],
    )


def _save_table_backed_document_state(session: Session) -> None:
    _replace_table_rows(
        session,
        PortalDocumentVersion,
        [_document_version_row(document) for document in DOCUMENT_VERSIONS.values()],
    )


def _save_table_backed_consent_state(session: Session) -> None:
    _replace_table_rows(
        session,
        PortalConsentEvidence,
        [
            _consent_evidence_row(consent)
            for participant_consents in CONSENT_EVIDENCE.values()
            for consent in participant_consents
        ],
    )


def _save_table_backed_mutation_state(session: Session) -> None:
    _replace_table_rows(
        session,
        PortalMutationRequest,
        [
            _mutation_request_row(mutation_request)
            for participant_requests in MUTATION_REQUESTS.values()
            for mutation_request in participant_requests
        ],
    )
    _replace_table_rows(
        session,
        PortalParticipantAuditEvent,
        [
            _participant_audit_event_row(participant_id, audit_event)
            for participant_id, audit_events in PARTICIPANT_AUDIT_EVENTS.items()
            for audit_event in audit_events
        ],
    )


def _save_table_backed_package_state(session: Session) -> None:
    _replace_table_rows(
        session,
        PortalMutationPackage,
        [_mutation_package_row(package) for package in MUTATION_PACKAGES.values()],
    )
    _replace_table_rows(
        session,
        PortalMutationPackageMetadata,
        [
            _mutation_package_metadata_row(metadata)
            for metadata in MUTATION_PACKAGE_METADATA.values()
        ],
    )
    _replace_table_rows(
        session,
        PortalPackagedMutationRequest,
        [
            PortalPackagedMutationRequest(
                mutation_request_id=record.mutation_request_id,
                package_id=package.package_id,
            )
            for package in MUTATION_PACKAGES.values()
            for record in package.records
        ],
    )


def _save_table_backed_file_evidence_state(session: Session) -> None:
    _replace_table_rows(
        session,
        PortalFileEvidence,
        [
            _file_evidence_row(evidence)
            for mutation_evidence in FILE_EVIDENCE.values()
            for evidence in mutation_evidence
        ],
    )


async def _async_table_rows(session: AsyncSession, row_type) -> list:
    result = await session.execute(select(row_type))
    return list(result.scalars().all())


async def _async_replace_table_rows(
    session: AsyncSession,
    row_type,
    rows: list,
) -> None:
    await session.execute(delete(row_type))
    session.add_all(rows)


async def _async_has_table_rows(session: AsyncSession, row_types: list) -> bool:
    for row_type in row_types:
        result = await session.execute(select(row_type).limit(1))
        if result.scalars().first() is not None:
            return True

    return False


async def _async_has_table_backed_onboarding_state(
    session: AsyncSession,
) -> bool:
    return await _async_has_table_rows(
        session,
        [
            PortalParticipantInvitation,
            PortalParticipant,
            PortalNetworkTopologyEntry,
            PortalIdentityVerification,
            PortalUserAccount,
            PortalPasswordResetToken,
            PortalCommunicationEvent,
        ],
    )


async def _async_restore_table_backed_onboarding_state(
    session: AsyncSession,
) -> None:
    invitation_rows = await _async_table_rows(session, PortalParticipantInvitation)
    participant_rows = await _async_table_rows(session, PortalParticipant)
    topology_rows = await _async_table_rows(session, PortalNetworkTopologyEntry)
    verification_rows = await _async_table_rows(session, PortalIdentityVerification)
    password_reset_rows = await _async_table_rows(session, PortalPasswordResetToken)
    communication_rows = await _async_table_rows(session, PortalCommunicationEvent)

    INVITATIONS.clear()
    INVITATIONS.update(
        {
            row.token: _invitation_from_row(row)
            for row in invitation_rows
        },
    )

    PARTICIPANTS.clear()
    PARTICIPANTS.update(
        {
            row.id: _participant_from_row(row)
            for row in participant_rows
        },
    )

    NETWORK_TOPOLOGY_ENTRIES.clear()
    NETWORK_TOPOLOGY_ENTRIES.update(
        {
            row.id: _network_topology_entry_from_row(row)
            for row in topology_rows
        },
    )

    IDENTITY_VERIFICATIONS.clear()
    IDENTITY_VERIFICATIONS.update(
        {
            row.participant_id: _identity_verification_from_row(row)
            for row in verification_rows
        },
    )

    await _async_restore_table_backed_user_account_state(session)

    PASSWORD_RESET_TOKENS.clear()
    PASSWORD_RESET_TOKENS.update(
        {
            row.token: _password_reset_token_from_row(row)
            for row in password_reset_rows
        },
    )

    COMMUNICATION_EVENTS.clear()
    COMMUNICATION_EVENTS.extend(
        _communication_event_from_row(row)
        for row in sorted(
            communication_rows,
            key=lambda item: (item.created_at, item.id),
        )
    )


async def _async_restore_table_backed_user_account_state(
    session: AsyncSession,
) -> None:
    account_rows = await _async_table_rows(session, PortalUserAccount)
    USER_ACCOUNTS.clear()
    USER_ACCOUNTS.update(
        {
            row.id: _user_account_from_row(row)
            for row in account_rows
        },
    )
    _ensure_seed_user_accounts()

    DEV_PARTICIPANT_USERS.clear()
    for account in USER_ACCOUNTS.values():
        if account.role == Role.PARTICIPANT and account.active:
            register_dev_participant_user(
                participant_id=account.id,
                email=account.email,
                display_name=account.display_name,
            )


async def _async_restore_table_backed_document_state(session: AsyncSession) -> None:
    document_rows = await _async_table_rows(session, PortalDocumentVersion)
    DOCUMENT_VERSIONS.clear()
    DOCUMENT_VERSIONS.update(
        {
            row.id: _document_version_from_row(row)
            for row in sorted(
                document_rows,
                key=lambda item: (item.published_at, item.id),
            )
        },
    )


async def _async_restore_table_backed_consent_state(session: AsyncSession) -> None:
    consent_rows = await _async_table_rows(session, PortalConsentEvidence)
    CONSENT_EVIDENCE.clear()
    for row in sorted(
        consent_rows,
        key=lambda item: (item.accepted_at, item.participant_id, item.document_version_id),
    ):
        consent = _consent_evidence_from_row(row)
        CONSENT_EVIDENCE.setdefault(consent.participant_id, []).append(consent)


async def _async_restore_table_backed_mutation_state(session: AsyncSession) -> None:
    mutation_rows = await _async_table_rows(session, PortalMutationRequest)
    audit_rows = await _async_table_rows(session, PortalParticipantAuditEvent)

    MUTATION_REQUESTS.clear()
    for row in sorted(
        mutation_rows,
        key=lambda item: (item.submitted_at, item.id),
    ):
        mutation_request = _mutation_request_from_row(row)
        MUTATION_REQUESTS.setdefault(mutation_request.participant_id, []).append(
            mutation_request,
        )

    PARTICIPANT_AUDIT_EVENTS.clear()
    for row in sorted(
        audit_rows,
        key=lambda item: (item.created_at, item.participant_id, item.id),
    ):
        audit_event = _participant_audit_event_from_row(row)
        PARTICIPANT_AUDIT_EVENTS.setdefault(row.participant_id, []).append(audit_event)


async def _async_restore_table_backed_package_state(session: AsyncSession) -> None:
    package_rows = await _async_table_rows(session, PortalMutationPackage)
    metadata_rows = await _async_table_rows(session, PortalMutationPackageMetadata)
    packaged_rows = await _async_table_rows(session, PortalPackagedMutationRequest)

    MUTATION_PACKAGES.clear()
    MUTATION_PACKAGES.update(
        {
            row.package_id: _mutation_package_from_row(row)
            for row in sorted(
                package_rows,
                key=lambda item: (item.generated_at, item.package_id),
            )
        },
    )

    MUTATION_PACKAGE_METADATA.clear()
    MUTATION_PACKAGE_METADATA.update(
        {
            row.package_id: _mutation_package_metadata_from_row(row)
            for row in metadata_rows
        },
    )

    PACKAGED_MUTATION_REQUEST_IDS.clear()
    PACKAGED_MUTATION_REQUEST_IDS.update(
        row.mutation_request_id
        for row in packaged_rows
    )
    if not PACKAGED_MUTATION_REQUEST_IDS:
        PACKAGED_MUTATION_REQUEST_IDS.update(
            record.mutation_request_id
            for package in MUTATION_PACKAGES.values()
            for record in package.records
        )


async def _async_restore_table_backed_file_evidence_state(
    session: AsyncSession,
) -> None:
    evidence_rows = await _async_table_rows(session, PortalFileEvidence)
    FILE_EVIDENCE.clear()
    for row in sorted(
        evidence_rows,
        key=lambda item: (item.created_at, item.mutation_request_id, item.id),
    ):
        evidence = _file_evidence_from_row(row)
        FILE_EVIDENCE.setdefault(evidence.mutation_request_id, []).append(evidence)


async def _async_save_table_backed_onboarding_state(
    session: AsyncSession,
) -> None:
    _ensure_seed_user_accounts()
    await _async_replace_table_rows(
        session,
        PortalParticipantInvitation,
        [_invitation_row(invitation) for invitation in INVITATIONS.values()],
    )
    await _async_replace_table_rows(
        session,
        PortalParticipant,
        [_participant_row(participant) for participant in PARTICIPANTS.values()],
    )
    await _async_replace_table_rows(
        session,
        PortalNetworkTopologyEntry,
        [
            _network_topology_entry_row(record)
            for record in NETWORK_TOPOLOGY_ENTRIES.values()
        ],
    )
    await _async_replace_table_rows(
        session,
        PortalIdentityVerification,
        [
            _identity_verification_row(verification)
            for verification in IDENTITY_VERIFICATIONS.values()
        ],
    )
    await _async_replace_table_rows(
        session,
        PortalUserAccount,
        [_user_account_row(account) for account in USER_ACCOUNTS.values()],
    )
    await _async_replace_table_rows(
        session,
        PortalPasswordResetToken,
        [
            _password_reset_token_row(token)
            for token in PASSWORD_RESET_TOKENS.values()
        ],
    )
    await _async_replace_table_rows(
        session,
        PortalCommunicationEvent,
        [_communication_event_row(event) for event in COMMUNICATION_EVENTS],
    )


async def _async_save_table_backed_document_state(session: AsyncSession) -> None:
    await _async_replace_table_rows(
        session,
        PortalDocumentVersion,
        [_document_version_row(document) for document in DOCUMENT_VERSIONS.values()],
    )


async def _async_save_table_backed_consent_state(session: AsyncSession) -> None:
    await _async_replace_table_rows(
        session,
        PortalConsentEvidence,
        [
            _consent_evidence_row(consent)
            for participant_consents in CONSENT_EVIDENCE.values()
            for consent in participant_consents
        ],
    )


async def _async_save_table_backed_mutation_state(session: AsyncSession) -> None:
    await _async_replace_table_rows(
        session,
        PortalMutationRequest,
        [
            _mutation_request_row(mutation_request)
            for participant_requests in MUTATION_REQUESTS.values()
            for mutation_request in participant_requests
        ],
    )
    await _async_replace_table_rows(
        session,
        PortalParticipantAuditEvent,
        [
            _participant_audit_event_row(participant_id, audit_event)
            for participant_id, audit_events in PARTICIPANT_AUDIT_EVENTS.items()
            for audit_event in audit_events
        ],
    )


async def _async_save_table_backed_package_state(session: AsyncSession) -> None:
    await _async_replace_table_rows(
        session,
        PortalMutationPackage,
        [_mutation_package_row(package) for package in MUTATION_PACKAGES.values()],
    )
    await _async_replace_table_rows(
        session,
        PortalMutationPackageMetadata,
        [
            _mutation_package_metadata_row(metadata)
            for metadata in MUTATION_PACKAGE_METADATA.values()
        ],
    )
    await _async_replace_table_rows(
        session,
        PortalPackagedMutationRequest,
        [
            PortalPackagedMutationRequest(
                mutation_request_id=record.mutation_request_id,
                package_id=package.package_id,
            )
            for package in MUTATION_PACKAGES.values()
            for record in package.records
        ],
    )


async def _async_save_table_backed_file_evidence_state(
    session: AsyncSession,
) -> None:
    await _async_replace_table_rows(
        session,
        PortalFileEvidence,
        [
            _file_evidence_row(evidence)
            for mutation_evidence in FILE_EVIDENCE.values()
            for evidence in mutation_evidence
        ],
    )


def _uses_direct_table_backed_participant_route(path: str) -> bool:
    return (
        path in {
            "/api/auth/login",
            "/api/auth/password-reset/request",
            "/api/auth/password-reset/confirm",
            "/api/me",
            "/api/admin/users",
            "/api/admin/partner-admin-users",
            "/api/admin/participants",
            "/api/admin/communication-events",
            "/api/admin/participant-invitations",
            "/api/admin/document-versions",
            "/api/auth/self-service-onboarding-requests",
            "/api/auth/participant-account-setup",
            "/api/documents/current",
            "/api/participants/me/consent-evidence",
            "/api/participants/me/contact-channels",
            "/api/participants/me/identity-checkpoint",
            "/api/participants/me/membership",
            "/api/participants/me/mutation-requests",
            "/api/admin/mutation-requests",
        }
        or (
            path.startswith("/api/admin/users/")
        )
        or (
            path.startswith("/api/admin/participants/")
            and path.endswith("/identity-verification")
        )
        or (
            path.startswith("/api/auth/invitations/")
            and path.endswith("/accept")
        )
        or (
            path.startswith("/api/auth/email-verifications/")
            and path.endswith("/verify")
        )
        or (
            path.startswith("/api/participants/")
            and path.endswith("/membership")
        )
        or (
            path.startswith("/api/admin/mutation-requests/")
            and path.endswith("/review-decision")
        )
        or (
            path.startswith("/api/admin/mutation-requests/")
            and path.endswith("/file-evidence")
        )
        or (
            path.startswith("/api/mutation-requests/")
            and "/file-evidence/" in path
        )
        or path in {
            "/api/admin/mutation-packages",
            "/api/partner/member-register",
            "/api/partner/tasks",
        }
        or path == "/api/partner/mutation-packages"
        or path.startswith("/api/partner/mutation-packages/")
        or path.startswith("/api/admin/mutation-packages/")
    )


async def _load_persisted_portal_state(
    *,
    restore_legacy_snapshot: bool = True,
    restore_onboarding_state: bool = True,
    restore_user_accounts_only: bool = False,
) -> None:
    if not persistence_enabled():
        return

    async with async_session_for_current_database() as session:
        snapshot = (
            await session.get(PortalStateSnapshot, PORTAL_STATE_SNAPSHOT_ID)
            if restore_legacy_snapshot
            else None
        )
        if snapshot is not None:
            _restore_portal_state_payload(json.loads(snapshot.payload_json))

        if restore_user_accounts_only:
            await _async_restore_table_backed_user_account_state(session)
            return
        if restore_onboarding_state and (
            snapshot is None or await _async_has_table_backed_onboarding_state(session)
        ):
            await _async_restore_table_backed_onboarding_state(session)
        await _async_restore_table_backed_document_state(session)
        await _async_restore_table_backed_consent_state(session)
        if snapshot is None or await _async_has_table_rows(
            session,
            [PortalMutationRequest, PortalParticipantAuditEvent],
        ):
            await _async_restore_table_backed_mutation_state(session)
        if snapshot is None or await _async_has_table_rows(
            session,
            [
                PortalMutationPackage,
                PortalMutationPackageMetadata,
                PortalPackagedMutationRequest,
            ],
        ):
            await _async_restore_table_backed_package_state(session)
        if snapshot is None or await _async_has_table_rows(session, [PortalFileEvidence]):
            await _async_restore_table_backed_file_evidence_state(session)


async def _save_persisted_portal_state() -> None:
    if not persistence_enabled():
        return

    payload_json = json.dumps(
        _portal_state_payload(),
        sort_keys=True,
        separators=(",", ":"),
    )
    async with async_session_for_current_database() as session:
        snapshot = await session.get(PortalStateSnapshot, PORTAL_STATE_SNAPSHOT_ID)
        if snapshot is None:
            snapshot = PortalStateSnapshot(
                id=PORTAL_STATE_SNAPSHOT_ID,
                payload_json=payload_json,
            )
            session.add(snapshot)
        else:
            snapshot.payload_json = payload_json
            session.add(snapshot)

        await _async_save_table_backed_onboarding_state(session)
        await _async_save_table_backed_document_state(session)
        await _async_save_table_backed_consent_state(session)
        await _async_save_table_backed_mutation_state(session)
        await _async_save_table_backed_package_state(session)
        await _async_save_table_backed_file_evidence_state(session)
        await session.commit()


def _document_hash(document: DocumentVersionCreate) -> str:
    source = "\x1f".join(
        [
            document.document_key,
            document.version,
            document.content,
            document.context,
        ],
    )
    return sha256(source.encode("utf-8")).hexdigest()


def _current_document_version(
    document_key: str,
    *,
    context: str | None = None,
) -> DocumentVersionRecord | None:
    for document in reversed(DOCUMENT_VERSIONS.values()):
        if document.document_key == document_key and (
            context is None or document.context == context
        ):
            return document

    return None


def _current_required_participant_documents() -> tuple[list[DocumentVersionRecord], list[str]]:
    documents: list[DocumentVersionRecord] = []
    missing_document_keys: list[str] = []
    for document_key in REQUIRED_PARTICIPANT_DOCUMENT_KEYS:
        document = _current_document_version(
            document_key,
            context=REQUIRED_PARTICIPANT_DOCUMENT_CONTEXT,
        )
        if document is None or document.context != REQUIRED_PARTICIPANT_DOCUMENT_CONTEXT:
            missing_document_keys.append(document_key)
            continue
        documents.append(document)

    if not documents:
        return [], []

    return documents, missing_document_keys


def _raise_for_missing_required_documents(missing_document_keys: list[str]) -> None:
    if missing_document_keys:
        joined_keys = ", ".join(missing_document_keys)
        raise HTTPException(
            status_code=403,
            detail=(
                "Required documents must be accepted before submitting binding "
                f"mutations: {joined_keys}"
            ),
        )


def _require_required_document_acceptance(participant: ParticipantRecord) -> None:
    _raise_for_missing_required_documents(
        _missing_required_document_keys(participant),
    )


def _require_eligibility_approved(participant: ParticipantRecord) -> None:
    if participant.eligibility_status == "approved":
        return
    if participant.eligibility_status == "stopped":
        raise HTTPException(
            status_code=403,
            detail="Network topology eligibility review stopped",
        )
    raise HTTPException(
        status_code=403,
        detail="Network topology eligibility review required",
    )


def _missing_required_document_keys(participant: ParticipantRecord) -> list[str]:
    required_documents, missing_document_keys = _current_required_participant_documents()
    if not required_documents:
        return []

    accepted_document_ids = {
        consent.document_version_id
        for consent in CONSENT_EVIDENCE.get(participant.id, [])
        if consent.context == REQUIRED_PARTICIPANT_DOCUMENT_CONTEXT
    }
    return missing_document_keys + [
        document.document_key
        for document in required_documents
        if document.id not in accepted_document_ids
    ]


def _participant_account_setup_completed(participant: ParticipantRecord) -> bool:
    account = USER_ACCOUNTS.get(participant.id)
    return bool(
        account is not None
        and account.password_hash is not None
        and account.password_salt is not None
    )


def _participant_requires_account_setup(participant: ParticipantRecord) -> bool:
    return any(
        invitation.participant_id == participant.id
        and invitation.source == "self_service_onboarding"
        for invitation in INVITATIONS.values()
    )


def _verified_participant(user: CurrentUser) -> ParticipantRecord:
    participant = PARTICIPANTS.get(user.id)
    if participant is None or not participant.email_verified:
        raise HTTPException(status_code=403, detail="Email verification required")
    if (
        _participant_requires_account_setup(participant)
        and not _participant_account_setup_completed(participant)
    ):
        raise HTTPException(status_code=403, detail="Account setup required")

    return participant


async def _async_merge_rows(session: AsyncSession, rows: list) -> None:
    for row in rows:
        await session.merge(row)


async def _async_participant_account_setup_completed(
    session: AsyncSession,
    participant: ParticipantRecord,
) -> bool:
    account = await session.get(PortalUserAccount, participant.id)
    return bool(
        account is not None
        and account.password_hash is not None
        and account.password_salt is not None
    )


async def _async_participant_requires_account_setup(
    session: AsyncSession,
    participant: ParticipantRecord,
) -> bool:
    result = await session.execute(
        select(PortalParticipantInvitation)
        .where(
            PortalParticipantInvitation.participant_id == participant.id,
            PortalParticipantInvitation.source == "self_service_onboarding",
        )
        .limit(1),
    )
    return result.scalars().first() is not None


async def _async_verified_participant(
    session: AsyncSession,
    user: CurrentUser,
) -> ParticipantRecord:
    participant_row = await session.get(PortalParticipant, user.id)
    if participant_row is None:
        raise HTTPException(status_code=403, detail="Email verification required")

    participant = _participant_from_row(participant_row)
    if not participant.email_verified:
        raise HTTPException(status_code=403, detail="Email verification required")
    if (
        await _async_participant_requires_account_setup(session, participant)
        and not await _async_participant_account_setup_completed(session, participant)
    ):
        raise HTTPException(status_code=403, detail="Account setup required")

    return participant


async def _async_current_required_participant_documents(
    session: AsyncSession,
) -> tuple[list[DocumentVersionRecord], list[str]]:
    documents: list[DocumentVersionRecord] = []
    missing_document_keys: list[str] = []
    for document_key in REQUIRED_PARTICIPANT_DOCUMENT_KEYS:
        result = await session.execute(
            select(PortalDocumentVersion)
            .where(
                PortalDocumentVersion.document_key == document_key,
                PortalDocumentVersion.context == REQUIRED_PARTICIPANT_DOCUMENT_CONTEXT,
            )
            .order_by(
                PortalDocumentVersion.published_at.desc(),
                PortalDocumentVersion.id.desc(),
            )
            .limit(1),
        )
        row = result.scalars().first()
        if row is None:
            missing_document_keys.append(document_key)
            continue
        documents.append(_document_version_from_row(row))

    if not documents:
        return [], []

    return documents, missing_document_keys


async def _async_require_required_document_acceptance(
    session: AsyncSession,
    participant: ParticipantRecord,
) -> None:
    _raise_for_missing_required_documents(
        await _async_missing_required_document_keys(session, participant),
    )


async def _async_missing_required_document_keys(
    session: AsyncSession,
    participant: ParticipantRecord,
) -> list[str]:
    required_documents, missing_document_keys = (
        await _async_current_required_participant_documents(session)
    )
    if not required_documents:
        return []

    result = await session.execute(
        select(PortalConsentEvidence).where(
            PortalConsentEvidence.participant_id == participant.id,
            PortalConsentEvidence.context == REQUIRED_PARTICIPANT_DOCUMENT_CONTEXT,
        ),
    )
    accepted_document_ids = {
        row.document_version_id
        for row in result.scalars().all()
    }
    return missing_document_keys + [
        document.document_key
        for document in required_documents
        if document.id not in accepted_document_ids
    ]


def _email_verification_checkpoint(participant: ParticipantRecord) -> IdentityCheckpointRead:
    current_level = "email_verified" if participant.email_verified else "unverified"

    return IdentityCheckpointRead(
        required_level="email_verified",
        current_level=current_level,
        satisfied=participant.email_verified,
    )


def _identity_checkpoint(participant: ParticipantRecord) -> IdentityCheckpointRead:
    if not participant.email_verified:
        return _email_verification_checkpoint(participant)
    if not _participant_requires_account_setup(participant):
        return _email_verification_checkpoint(participant)
    if not _participant_account_setup_completed(participant):
        return IdentityCheckpointRead(
            required_level="account_setup",
            current_level="email_verified",
            satisfied=False,
        )

    return IdentityCheckpointRead(
        required_level="account_setup",
        current_level="account_setup",
        satisfied=True,
    )


async def _async_identity_checkpoint(
    session: AsyncSession,
    participant: ParticipantRecord,
) -> IdentityCheckpointRead:
    if not participant.email_verified:
        return _email_verification_checkpoint(participant)
    if not await _async_participant_requires_account_setup(session, participant):
        return _email_verification_checkpoint(participant)
    if not await _async_participant_account_setup_completed(session, participant):
        return IdentityCheckpointRead(
            required_level="account_setup",
            current_level="email_verified",
            satisfied=False,
        )

    return IdentityCheckpointRead(
        required_level="account_setup",
        current_level="account_setup",
        satisfied=True,
    )


def _record_identity_verification(
    participant: ParticipantRecord,
    *,
    source: str,
    verified_at: str | None = None,
) -> IdentityVerificationRead:
    checkpoint = _email_verification_checkpoint(participant)
    record = IdentityVerificationRead(
        participant_id=participant.id,
        email=participant.email,
        display_name=participant.display_name,
        leg_id=participant.leg_id,
        source=source,
        verified_at=verified_at,
        **checkpoint.model_dump(),
    )
    IDENTITY_VERIFICATIONS[participant.id] = record

    return record


def _public_url(path: str) -> str:
    base_url = os.environ.get("SUNTERRA_PUBLIC_BASE_URL", "").rstrip("/")
    return f"{base_url}{path}" if base_url else path


def _email_message_for_event(
    event_type: str,
    *,
    invitation_token: str | None = None,
    verification_token: str | None = None,
    password_reset_token: str | None = None,
) -> tuple[str, str]:
    if event_type == "participant_invitation":
        invitation_url = (
            _public_url(f"/api/auth/invitations/{invitation_token}/accept")
            if invitation_token
            else None
        )
        body = "Sie wurden zum SunTerra LEG Portal eingeladen."
        if invitation_url:
            body = f"{body}\n\n{invitation_url}"
        return (
            "SunTerra LEG Einladung",
            body,
        )
    if event_type == "email_verification":
        verification_url = (
            _public_url(f"/api/auth/email-verifications/{verification_token}/verify")
            if verification_token
            else None
        )
        body = "Bitte verifizieren Sie Ihre E-Mail-Adresse im SunTerra LEG Portal."
        if verification_url:
            body = f"{body}\n\n{verification_url}"
        return (
            "SunTerra LEG E-Mail-Verifikation",
            body,
        )
    if event_type == "password_reset":
        reset_url = (
            _public_url(f"/reset-password?token={password_reset_token}")
            if password_reset_token
            else None
        )
        body = "Sie koennen Ihr Passwort im SunTerra LEG Portal zuruecksetzen."
        if reset_url:
            body = f"{body}\n\n{reset_url}"
        return (
            "SunTerra LEG Passwort zuruecksetzen",
            body,
        )
    return (
        "SunTerra LEG Portal",
        "Im SunTerra LEG Portal liegt eine neue Nachricht fuer Sie vor.",
    )


def _queue_email_event(
    event_type: str,
    recipient_email: str,
    *,
    invitation_token: str | None = None,
    verification_token: str | None = None,
    password_reset_token: str | None = None,
) -> CommunicationEventRead:
    event = CommunicationEventRead(
        id=uuid4().hex,
        channel="email",
        event_type=event_type,
        recipient_email=recipient_email,
        status="queued",
        created_at=datetime.now(UTC).isoformat(),
    )
    COMMUNICATION_EVENTS.append(event)
    if production_smtp_enabled():
        subject, body = _email_message_for_event(
            event_type,
            invitation_token=invitation_token,
            verification_token=verification_token,
            password_reset_token=password_reset_token,
        )
        try:
            send_transactional_email(
                recipient_email=recipient_email,
                subject=subject,
                body=body,
            )
        except Exception:
            event.status = "failed"
            return event
        event.status = "sent"

    return event


def _participant_membership_read(
    participant: ParticipantRecord,
    *,
    missing_required_document_keys: list[str] | None = None,
) -> ParticipantMembershipRead:
    if not participant.email_verified:
        membership_status = "pending_email_verification"
    elif participant.eligibility_status == "stopped":
        membership_status = "eligibility_stopped"
    elif participant.eligibility_status != "approved":
        membership_status = "pending_eligibility_review"
    elif (
        missing_required_document_keys
        if missing_required_document_keys is not None
        else _missing_required_document_keys(participant)
    ):
        membership_status = "pending_required_documents"
    else:
        membership_status = "active"

    return ParticipantMembershipRead(
        participant_id=participant.id,
        display_name=participant.display_name,
        email=participant.email,
        leg_id=participant.leg_id,
        leg_name=BASADINGEN_LEG_NAME,
        membership_status=membership_status,
        eligibility_status=participant.eligibility_status,
        eligibility_review_reason=participant.eligibility_review_reason,
        billing_notice=PARTICIPANT_BILLING_NOTICE,
    )


def _admin_participant_directory_row(participant: ParticipantRecord) -> dict[str, str]:
    return {
        "participant_id": participant.id,
        "display_name": participant.display_name,
        "email": participant.email,
        "leg_id": participant.leg_id,
        "membership_status": (
            "active" if participant.email_verified else "pending_email_verification"
        ),
    }


def _participant_contact_channels_read(
    participant: ParticipantRecord,
) -> ParticipantContactChannelsRead:
    return ParticipantContactChannelsRead(
        participant_id=participant.id,
        email=participant.email,
        phone_number=participant.phone_number,
        preferred_contact_channel=participant.preferred_contact_channel,
        audit_events=PARTICIPANT_AUDIT_EVENTS.get(participant.id, []),
    )


async def _async_participant_audit_events(
    session: AsyncSession,
    participant_id: str,
) -> list[AuditEventRead]:
    result = await session.execute(
        select(PortalParticipantAuditEvent).where(
            PortalParticipantAuditEvent.participant_id == participant_id,
        ),
    )
    return [
        _participant_audit_event_from_row(row)
        for row in sorted(
            result.scalars().all(),
            key=lambda item: (item.created_at, item.id),
        )
    ]


async def _async_participant_contact_channels_read(
    session: AsyncSession,
    participant: ParticipantRecord,
) -> ParticipantContactChannelsRead:
    return ParticipantContactChannelsRead(
        participant_id=participant.id,
        email=participant.email,
        phone_number=participant.phone_number,
        preferred_contact_channel=participant.preferred_contact_channel,
        audit_events=await _async_participant_audit_events(session, participant.id),
    )


def _regular_address_quarter_dates(quarter: str) -> tuple[str, str, str]:
    try:
        year_text, quarter_text = quarter.split("-Q", maxsplit=1)
        year = int(year_text)
        quarter_number = int(quarter_text)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="Requested quarter must use YYYY-Q1 through YYYY-Q4",
        ) from exc

    if quarter_number not in {1, 2, 3, 4}:
        raise HTTPException(
            status_code=400,
            detail="Requested quarter must use YYYY-Q1 through YYYY-Q4",
        )

    quarter_end_by_number = {
        1: date(year, 3, 31),
        2: date(year, 6, 30),
        3: date(year, 9, 30),
        4: date(year, 12, 31),
    }
    participant_deadline_by_number = {
        1: date(year - 1, 12, 31),
        2: date(year, 3, 31),
        3: date(year, 6, 30),
        4: date(year, 9, 30),
    }

    quarter_end = quarter_end_by_number[quarter_number]
    participant_deadline = participant_deadline_by_number[quarter_number]
    effective_date = quarter_end + timedelta(days=1)

    return (
        participant_deadline.isoformat(),
        quarter_end.isoformat(),
        effective_date.isoformat(),
    )


def _build_mutation_request(
    participant: ParticipantRecord,
    mutation: MutationRequestCreate,
) -> MutationRequestRecord:
    if mutation.mode == "special":
        if mutation.mutation_type not in SUPPORTED_SPECIAL_MUTATION_TYPES:
            raise HTTPException(
                status_code=400,
                detail=REGULAR_MUTATION_SUPPORT_ERROR,
            )
        reason = (mutation.reason or "").strip()
        if not reason:
            raise HTTPException(
                status_code=400,
                detail="Special mutation requires reason",
            )
        if mutation.event_date is None:
            raise HTTPException(
                status_code=400,
                detail="Special mutation requires event_date",
            )
        mutation_details = {
            "reason": reason,
            "event_date": mutation.event_date.isoformat(),
        }
        quarter = None
        quarter_end = None
        participant_deadline = None
        effective_date = mutation.event_date.isoformat()
    elif mutation.mode == "regular":
        if mutation.mutation_type not in SUPPORTED_REGULAR_MUTATION_TYPES:
            raise HTTPException(
                status_code=400,
                detail=REGULAR_MUTATION_SUPPORT_ERROR,
            )
        if mutation.mutation_type == "address":
            if mutation.new_address is None:
                raise HTTPException(
                    status_code=400,
                    detail="Address mutation requires new_address",
                )
            mutation_details = {
                "street": mutation.new_address.street,
                "postal_code": mutation.new_address.postal_code,
                "city": mutation.new_address.city,
                "country": mutation.new_address.country,
            }
        elif mutation.mutation_type == "meter_point":
            metering_code = (mutation.metering_code or "").strip()
            if not metering_code:
                raise HTTPException(
                    status_code=400,
                    detail="Meter point mutation requires metering_code",
                )
            mutation_details = {"metering_code": metering_code}
        elif mutation.mutation_type == "role":
            requested_role = (mutation.requested_role or "").strip()
            if requested_role not in SUPPORTED_MUTATION_ROLES:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Role mutation requested_role must be one of owner, "
                        "producer, prosumer, tenant"
                    ),
                )
            mutation_details = {"requested_role": requested_role}
        elif mutation.mutation_type in {"entry", "exit"}:
            reason = (mutation.reason or "").strip()
            if not reason:
                raise HTTPException(
                    status_code=400,
                    detail=f"{mutation.mutation_type.capitalize()} mutation requires reason",
                )
            mutation_details = {"reason": reason}
        else:
            technology = (mutation.technology or "").strip()
            if (
                not technology
                or mutation.installed_capacity_kw is None
                or mutation.installed_capacity_kw <= 0
                or mutation.commissioned_on is None
            ):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Generation asset mutation requires technology, positive "
                        "installed_capacity_kw, and commissioned_on"
                    ),
                )
            mutation_details = {
                "technology": technology,
                "installed_capacity_kw": mutation.installed_capacity_kw,
                "commissioned_on": mutation.commissioned_on.isoformat(),
            }

        participant_deadline, quarter_end, effective_date = (
            _regular_address_quarter_dates(mutation.requested_quarter or "")
        )
        if mutation.mutation_type == "exit":
            effective_date = quarter_end
        submitted_on = mutation.submitted_on or date.today()
        if submitted_on > date.fromisoformat(participant_deadline):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Regular address mutation for {mutation.requested_quarter} "
                    "must be submitted by participant deadline "
                    f"{participant_deadline}"
                ),
            )
        quarter = mutation.requested_quarter
    else:
        raise HTTPException(
            status_code=400,
            detail=REGULAR_MUTATION_SUPPORT_ERROR,
        )

    return MutationRequestRecord(
        id=uuid4().hex,
        participant_id=participant.id,
        leg_id=participant.leg_id,
        mutation_type=mutation.mutation_type,
        mode=mutation.mode,
        status="submitted",
        quarter=quarter,
        quarter_end=quarter_end,
        participant_deadline=participant_deadline,
        effective_date=effective_date,
        submitted_at=datetime.now(UTC).isoformat(),
        new_address=mutation.new_address,
        mutation_details=mutation_details,
    )


def _apply_mutation_review_decision(
    mutation_request: MutationRequestRecord,
    decision: MutationReviewDecision,
    user: CurrentUser,
) -> MutationRequestRecord:
    if decision.decision not in {"approved", "rejected"}:
        raise HTTPException(status_code=400, detail="Unsupported review decision")

    if mutation_request.status != "submitted":
        raise HTTPException(
            status_code=400,
            detail="Mutation request has already been reviewed",
        )
    if decision.decision == "rejected" and not (decision.reason or "").strip():
        raise HTTPException(
            status_code=400,
            detail="Rejecting a mutation request requires a reason",
        )

    from_status = mutation_request.status
    reviewed_at = datetime.now(UTC).isoformat()
    mutation_request.status = decision.decision
    mutation_request.reviewed_at = reviewed_at
    mutation_request.review_reason = (
        decision.reason if decision.decision == "rejected" else None
    )
    mutation_request.audit_events.append(
        AuditEventRead(
            id=uuid4().hex,
            action=f"mutation_request.{decision.decision}",
            actor_role=user.role.value,
            created_at=reviewed_at,
            from_status=from_status,
            to_status=decision.decision,
            reason=mutation_request.review_reason,
        ),
    )

    return mutation_request


def _apply_mutation_package_readiness(
    mutation_request: MutationRequestRecord,
    decision: MutationPackageReadinessDecision,
    user: CurrentUser,
) -> MutationRequestRecord:
    if mutation_request.mutation_type == "entry":
        raise HTTPException(
            status_code=400,
            detail="Entry mutations require LEG approval before package readiness",
        )
    if mutation_request.status != "submitted":
        raise HTTPException(
            status_code=400,
            detail="Mutation request has already been reviewed",
        )
    reason = decision.reason.strip()
    if not reason:
        raise HTTPException(
            status_code=400,
            detail="Package readiness check requires a reason",
        )

    from_status = mutation_request.status
    reviewed_at = datetime.now(UTC).isoformat()
    if decision.ready:
        to_status = "package_ready"
    else:
        to_status = (decision.status or "needs_clarification").strip()
        if to_status not in {"needs_clarification", "stopped_invalid"}:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Package readiness stop status must be "
                    "needs_clarification or stopped_invalid"
                ),
            )
    mutation_request.status = to_status
    mutation_request.reviewed_at = reviewed_at
    mutation_request.review_reason = reason
    mutation_request.audit_events.append(
        AuditEventRead(
            id=uuid4().hex,
            action=f"mutation_request.{to_status}",
            actor_role=user.role.value,
            created_at=reviewed_at,
            from_status=from_status,
            to_status=to_status,
            reason=reason,
        ),
    )

    return mutation_request


def _mutation_request_is_package_ready(
    mutation_request: MutationRequestRecord,
) -> bool:
    return mutation_request.status == "package_ready" or (
        mutation_request.status == "approved"
        and mutation_request.mutation_type == "entry"
    )


def _admin_mutation_request_read_with_participant(
    mutation_request: MutationRequestRecord,
    participant: ParticipantRecord,
) -> AdminMutationRequestRead:
    return AdminMutationRequestRead(
        **mutation_request.model_dump(),
        participant=AdminMutationParticipantRead(
            participant_id=participant.id,
            display_name=participant.display_name,
            email=participant.email,
        ),
    )


def _admin_mutation_request_read(
    mutation_request: MutationRequestRecord,
) -> AdminMutationRequestRead:
    participant = PARTICIPANTS[mutation_request.participant_id]
    return _admin_mutation_request_read_with_participant(mutation_request, participant)


def _find_mutation_request(mutation_request_id: str) -> MutationRequestRecord:
    for participant_requests in MUTATION_REQUESTS.values():
        for mutation_request in participant_requests:
            if mutation_request.id == mutation_request_id:
                return mutation_request

    raise HTTPException(status_code=404, detail="Mutation request not found")


def _find_file_evidence(
    mutation_request_id: str,
    file_evidence_id: str,
) -> FileEvidenceRecord:
    for evidence in FILE_EVIDENCE.get(mutation_request_id, []):
        if evidence.id == file_evidence_id:
            return evidence

    raise HTTPException(status_code=404, detail="File evidence not found")


def _authorize_file_evidence_access(
    evidence: FileEvidenceRecord,
    user: CurrentUser,
) -> None:
    if user.role == Role.LEG_ADMIN:
        return

    if user.role == Role.PARTICIPANT:
        participant = _verified_participant(user)
        if participant.id == evidence.participant_id:
            return

    raise HTTPException(status_code=403, detail="File evidence is not accessible")


async def _async_authorize_file_evidence_access(
    session: AsyncSession,
    evidence: FileEvidenceRecord,
    user: CurrentUser,
) -> None:
    if user.role == Role.LEG_ADMIN:
        return

    if user.role == Role.PARTICIPANT:
        participant = await _async_verified_participant(session, user)
        if participant.id == evidence.participant_id:
            return

    raise HTTPException(status_code=403, detail="File evidence is not accessible")


def _find_mutation_package(package_id: str) -> MutationPackageRead:
    mutation_package = MUTATION_PACKAGES.get(package_id)
    if mutation_package is None:
        raise HTTPException(status_code=404, detail="Mutation package not found")

    return mutation_package


def _mutation_package_metadata(
    package: MutationPackageRead,
) -> AdminMutationPackageMetadataRead:
    metadata = MUTATION_PACKAGE_METADATA.get(package.package_id)
    if metadata is not None:
        return metadata

    metadata = _default_mutation_package_metadata(package)
    MUTATION_PACKAGE_METADATA[package.package_id] = metadata

    return metadata


def _default_mutation_package_metadata(
    package: MutationPackageRead,
) -> AdminMutationPackageMetadataRead:
    status_history = [
        MutableMutationPackageStatusEvent(
            status=event.status,
            actor_id=event.actor_id,
            actor_role=event.actor_role,
            created_at=event.created_at,
        )
        for event in package.status_history
    ]
    metadata = AdminMutationPackageMetadataRead(
        package_id=package.package_id,
        current_status=status_history[-1].status,
        status_history=status_history,
    )

    return metadata


async def _async_find_mutation_package(
    session: AsyncSession,
    package_id: str,
) -> MutationPackageRead:
    row = await session.get(PortalMutationPackage, package_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Mutation package not found")

    return _mutation_package_from_row(row)


async def _async_mutation_packages(session: AsyncSession) -> list[MutationPackageRead]:
    return [
        _mutation_package_from_row(row)
        for row in await _async_table_rows(session, PortalMutationPackage)
    ]


async def _async_mutation_package_metadata(
    session: AsyncSession,
    package: MutationPackageRead,
) -> AdminMutationPackageMetadataRead:
    row = await session.get(PortalMutationPackageMetadata, package.package_id)
    if row is None:
        return _default_mutation_package_metadata(package)

    return _mutation_package_metadata_from_row(row)


def _partner_mutation_package_summary_with_metadata(
    package: MutationPackageRead,
    metadata: AdminMutationPackageMetadataRead,
) -> PartnerMutationPackageSummary:
    current_status = metadata.status_history[-1]
    return PartnerMutationPackageSummary(
        package_id=package.package_id,
        leg_id=package.leg_id,
        quarter=package.quarter,
        effective_date=package.effective_date,
        generated_at=package.generated_at,
        record_count=len(package.records),
        current_status=current_status.status,
        status_updated_at=current_status.created_at,
    )


def _partner_mutation_package_detail_with_metadata(
    package: MutationPackageRead,
    metadata: AdminMutationPackageMetadataRead,
) -> PartnerMutationPackageDetail:
    return PartnerMutationPackageDetail(
        **_partner_mutation_package_summary_with_metadata(package, metadata).model_dump(),
        records=package.records,
        status_history=_partner_status_read(metadata).status_history,
    )


def _partner_status_read(
    metadata: AdminMutationPackageMetadataRead,
) -> PartnerMutationPackageStatusRead:
    return PartnerMutationPackageStatusRead(
        package_id=metadata.package_id,
        current_status=metadata.current_status,
        status_history=[
            PartnerMutationPackageStatusEvent(
                status=event.status,
                actor_role=event.actor_role,
                created_at=event.created_at,
                reference=event.reference,
                reason=event.reason,
            )
            for event in metadata.status_history
        ],
    )


def _partner_mutation_package_summary(
    package: MutationPackageRead,
) -> PartnerMutationPackageSummary:
    metadata = _mutation_package_metadata(package)
    return _partner_mutation_package_summary_with_metadata(package, metadata)


def _partner_mutation_package_detail(
    package: MutationPackageRead,
) -> PartnerMutationPackageDetail:
    metadata = _mutation_package_metadata(package)
    return _partner_mutation_package_detail_with_metadata(package, metadata)


def _partner_member_read(
    package: MutationPackageRead,
    record: MutationPackageRecord,
) -> PartnerMemberRead:
    participant = PARTICIPANTS[record.participant_id]
    membership_status = (
        "active" if participant.email_verified else "pending_email_verification"
    )
    return PartnerMemberRead(
        participant_id=participant.id,
        display_name=participant.display_name,
        membership_status=membership_status,
        reporting_address=record.new_address,
        latest_package_status=PartnerMemberLatestPackageStatus(
            package_id=package.package_id,
            quarter=package.quarter,
            effective_date=record.effective_date,
            status=_mutation_package_metadata(package).current_status,
        ),
    )


def _partner_task_read(
    package: MutationPackageRead,
    status_event: MutableMutationPackageStatusEvent,
) -> PartnerTaskRead:
    return PartnerTaskRead(
        task_id=f"{package.package_id}:{status_event.status}",
        package_id=package.package_id,
        leg_id=package.leg_id,
        quarter=package.quarter,
        effective_date=package.effective_date,
        status=status_event.status,
        reference=status_event.reference,
        reason=status_event.reason,
        created_at=status_event.created_at,
        record_count=len(package.records),
    )


def _admin_partner_task_read(
    package: MutationPackageRead,
    status_event: MutableMutationPackageStatusEvent,
) -> AdminPartnerTaskRead:
    return AdminPartnerTaskRead(
        **_partner_task_read(package, status_event).model_dump(),
        records=[
            AdminPartnerTaskMutationRead(
                mutation_request_id=record.mutation_request_id,
                participant_id=record.participant_id,
                mutation_type=record.mutation_type,
                effective_date=record.effective_date,
            )
            for record in package.records
        ],
    )


def _build_mutation_package(
    *,
    quarter: str,
    effective_date: str,
    approved_requests: list[MutationRequestRecord],
    user: CurrentUser,
) -> MutationPackageRead:
    generated_at = datetime.now(UTC).isoformat()
    package_id = uuid4().hex
    records = [
        MutationPackageRecord(
            mutation_request_id=mutation_request.id,
            participant_id=mutation_request.participant_id,
            mutation_type=mutation_request.mutation_type,
            mode=mutation_request.mode,
            effective_date=mutation_request.effective_date,
            new_address=mutation_request.new_address,
            mutation_details=mutation_request.mutation_details,
        )
        for mutation_request in approved_requests
    ]
    status_history = [
        MutationPackageStatusEvent(
            status="created",
            actor_id=user.id,
            actor_role=user.role.value,
            created_at=generated_at,
        ),
    ]
    package_data = {
        "schema_version": "mutation-package.v1",
        "package_id": package_id,
        "leg_id": BASADINGEN_LEG_ID,
        "quarter": quarter,
        "effective_date": effective_date,
        "records": [record.model_dump() for record in records],
        "generated_at": generated_at,
        "status_history": [event.model_dump() for event in status_history],
    }

    return MutationPackageRead(
        **package_data,
        hash=_mutation_package_hash(package_data),
    )


def _mutation_package_hash(package_data: dict) -> str:
    canonical = json.dumps(
        package_data,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(canonical.encode("utf-8")).hexdigest()


def _mutation_details_json(record: MutationPackageRecord) -> str:
    return json.dumps(
        record.mutation_details,
        sort_keys=True,
        separators=(",", ":"),
    )


def _mutation_package_csv(package: MutationPackageRead) -> str:
    output = StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        [
            "schema_version",
            "package_id",
            "leg_id",
            "quarter",
            "effective_date",
            "hash",
            "generated_at",
            "record_index",
            "mutation_request_id",
            "participant_id",
            "mutation_type",
            "mode",
            "record_effective_date",
            "mutation_details_json",
            "street",
            "postal_code",
            "city",
            "country",
            "status",
            "status_actor_id",
            "status_actor_role",
            "status_created_at",
        ],
    )
    creation_event = package.status_history[0]
    for index, record in enumerate(package.records, start=1):
        address = record.new_address
        writer.writerow(
            [
                package.schema_version,
                package.package_id,
                package.leg_id,
                package.quarter,
                package.effective_date,
                package.hash,
                package.generated_at,
                index,
                record.mutation_request_id,
                record.participant_id,
                record.mutation_type,
                record.mode,
                record.effective_date,
                _mutation_details_json(record),
                address.street if address else "",
                address.postal_code if address else "",
                address.city if address else "",
                address.country if address else "",
                creation_event.status,
                creation_event.actor_id,
                creation_event.actor_role,
                creation_event.created_at,
            ],
        )

    return output.getvalue()


def _pdf_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _mutation_package_pdf_stream(package: MutationPackageRead) -> str:
    lines = [
        "MutationPackage Export",
        f"schema_version: {package.schema_version}",
        f"package_id: {package.package_id}",
        f"leg_id: {package.leg_id}",
        f"quarter: {package.quarter}",
        f"effective_date: {package.effective_date}",
        f"hash: {package.hash}",
        f"generated_at: {package.generated_at}",
    ]
    for index, record in enumerate(package.records, start=1):
        address = record.new_address
        address_text = (
            (
                f" {address.street}, {address.postal_code} "
                f"{address.city}, {address.country}"
            )
            if address
            else ""
        )
        lines.append(
            (
                f"record {index}: {record.mutation_request_id} "
                f"{record.participant_id} {record.mutation_type} {record.mode} "
                f"{record.effective_date} {_mutation_details_json(record)}"
                f"{address_text}"
            ),
        )
    creation_event = package.status_history[0]
    lines.append(
        (
            f"status: {creation_event.status} by {creation_event.actor_id} "
            f"{creation_event.actor_role} at {creation_event.created_at}"
        ),
    )

    commands = ["BT", "/F1 10 Tf", "40 800 Td"]
    for index, line in enumerate(lines):
        commands.append(f"({_pdf_escape(line)}) Tj")
        if index != len(lines) - 1:
            commands.append("0 -14 Td")
    commands.append("ET")

    return "\n".join(commands)


def _mutation_package_pdf(package: MutationPackageRead) -> bytes:
    stream = _mutation_package_pdf_stream(package).encode("latin-1", "replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
        ),
        b"<< /Length "
        + str(len(stream)).encode("ascii")
        + b" >>\nstream\n"
        + stream
        + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for object_number, body in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{object_number} 0 obj\n".encode("ascii"))
        pdf.extend(body)
        pdf.extend(b"\nendobj\n")

    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii"),
    )

    return bytes(pdf)


app = FastAPI(title="SunTerra LEG Portal", version="0.1.0", lifespan=production_lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_allowed_origins(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def persist_portal_state(request, call_next):
    if request.url.path in {"/api/health", "/api/readiness"}:
        return await call_next(request)

    uses_direct_participant_tables = _uses_direct_table_backed_participant_route(
        request.url.path,
    )
    if uses_direct_participant_tables:
        await _load_persisted_portal_state(
            restore_legacy_snapshot=False,
            restore_onboarding_state=False,
            restore_user_accounts_only=True,
        )
        return await call_next(request)

    if request.url.path.startswith("/api/") or not legacy_portal_state_enabled():
        return await call_next(request)

    await _load_persisted_portal_state()
    response = await call_next(request)
    if (
        request.method in {"POST", "PUT", "PATCH", "DELETE"}
        and response.status_code < 400
    ):
        await _save_persisted_portal_state()

    return response


@app.get("/api/health", response_model=HealthStatus)
def health() -> HealthStatus:
    return HealthStatus(
        status="ok",
        service="sunterra-leg-portal",
        version="0.1.0",
    )


@app.get("/api/readiness", response_model=ReadinessStatus)
async def readiness() -> ReadinessStatus:
    try:
        query_result = await async_database_runtime_check()
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=503,
            detail="Async database readiness check failed",
        ) from error

    return ReadinessStatus(
        status="ok",
        service="sunterra-leg-portal",
        version="0.1.0",
        database=DatabaseReadinessStatus(
            status="ok",
            query_result=query_result,
        ),
    )


@app.post("/api/auth/login", response_model=AuthTokenResponse)
async def login(credentials: LoginRequest) -> AuthTokenResponse:
    if persistence_enabled():
        async with async_session_for_current_database() as session:
            account = await _async_user_account_by_email(session, credentials.email)
    else:
        _ensure_seed_user_accounts()
        account = next(
            (
                candidate
                for candidate in USER_ACCOUNTS.values()
                if candidate.email.lower() == credentials.email.lower()
            ),
            None,
        )
    if (
        account is None
        or not account.active
        or not _verify_account_password(account, credentials.password)
    ):
        raise HTTPException(status_code=401, detail="Invalid login credentials")
    if _account_requires_totp(account) and not _verify_totp_code(
        account.mfa_totp_secret or "",
        credentials.totp_code,
    ):
        raise HTTPException(status_code=401, detail="Valid TOTP code required")

    user = CurrentUser(
        id=account.id,
        email=account.email,
        display_name=account.display_name,
        role=account.role,
        mfa_satisfied=_login_mfa_satisfied(account, credentials),
    )
    return AuthTokenResponse(
        access_token=create_access_token(user),
        token_type="bearer",
        expires_in_seconds=JWT_ACCESS_TOKEN_SECONDS,
        user=user,
    )


@app.post(
    "/api/auth/password-reset/request",
    response_model=PasswordResetStatusRead,
    status_code=202,
)
async def request_password_reset(
    reset_request: PasswordResetRequestCreate,
) -> PasswordResetStatusRead:
    normalized_email = _normalized_email(reset_request.email)
    if persistence_enabled():
        async with async_session_for_current_database() as session:
            account = await _async_user_account_by_email(session, normalized_email)
            if account is not None and account.active:
                reset_token = _password_reset_record_for_account(account)
                event = _queue_email_event(
                    "password_reset",
                    account.email,
                    password_reset_token=reset_token.token,
                )
                session.add(_communication_event_row(event))
                if event.status != "failed":
                    session.add(_password_reset_token_row(reset_token))
                    PASSWORD_RESET_TOKENS[reset_token.token] = reset_token
                await session.commit()
            return PasswordResetStatusRead(status="password_reset_requested")

    _ensure_seed_user_accounts()
    account = next(
        (
            candidate
            for candidate in USER_ACCOUNTS.values()
            if _normalized_email(candidate.email) == normalized_email
        ),
        None,
    )
    if account is not None and account.active:
        reset_token = _password_reset_record_for_account(account)
        event = _queue_email_event(
            "password_reset",
            account.email,
            password_reset_token=reset_token.token,
        )
        if event.status != "failed":
            PASSWORD_RESET_TOKENS[reset_token.token] = reset_token

    return PasswordResetStatusRead(status="password_reset_requested")


@app.post(
    "/api/auth/password-reset/confirm",
    response_model=PasswordResetStatusRead,
)
async def confirm_password_reset(
    confirmation: PasswordResetConfirm,
) -> PasswordResetStatusRead:
    used_at = datetime.now(UTC).isoformat()
    if persistence_enabled():
        async with async_session_for_current_database() as session:
            token_row = await session.get(PortalPasswordResetToken, confirmation.token)
            if token_row is None:
                raise HTTPException(status_code=400, detail="Invalid password reset token")
            reset_token = _password_reset_token_from_row(token_row)
            if not _password_reset_token_valid(reset_token):
                raise HTTPException(status_code=400, detail="Invalid password reset token")
            account_row = await session.get(PortalUserAccount, reset_token.account_id)
            if account_row is None or not account_row.active:
                raise HTTPException(status_code=400, detail="Invalid password reset token")
            account = _user_account_from_row(account_row)
            _set_account_password(account, confirmation.password)
            token_row.used_at = used_at
            reset_token.used_at = used_at
            PASSWORD_RESET_TOKENS[reset_token.token] = reset_token
            await session.merge(_user_account_row(account))
            await session.merge(token_row)
            await session.commit()
            USER_ACCOUNTS[account.id] = account
            return PasswordResetStatusRead(status="password_reset_completed")

    reset_token = PASSWORD_RESET_TOKENS.get(confirmation.token)
    if reset_token is None or not _password_reset_token_valid(reset_token):
        raise HTTPException(status_code=400, detail="Invalid password reset token")
    account = USER_ACCOUNTS.get(reset_token.account_id)
    if account is None or not account.active:
        raise HTTPException(status_code=400, detail="Invalid password reset token")
    _set_account_password(account, confirmation.password)
    reset_token.used_at = used_at
    PASSWORD_RESET_TOKENS[reset_token.token] = reset_token
    USER_ACCOUNTS[account.id] = account

    return PasswordResetStatusRead(status="password_reset_completed")


@app.post(
    "/api/auth/mfa/totp/enroll",
    response_model=TotpEnrollmentResponse,
    status_code=201,
)
async def enroll_totp_mfa(
    user: CurrentUser = Depends(
        require_roles_before_mfa(
            Role.LEG_ADMIN,
            Role.PARTNER_ADMIN,
            Role.PLATFORM_ADMIN,
        ),
    ),
) -> TotpEnrollmentResponse:
    if persistence_enabled():
        async with async_session_for_current_database() as session:
            account = await _async_user_account_by_id(session, user.id)
            if account is None:
                raise HTTPException(status_code=404, detail="User account not found")
            if _account_requires_totp(account) and not user.mfa_satisfied:
                raise HTTPException(status_code=403, detail="Admin MFA required")
            account.mfa_totp_secret = _totp_secret()
            account.mfa_totp_enabled = True
            await session.merge(_user_account_row(account))
            await session.commit()
            return TotpEnrollmentResponse(
                secret=account.mfa_totp_secret,
                otpauth_url=_totp_otpauth_url(account),
            )

    _ensure_seed_user_accounts()
    account = USER_ACCOUNTS.get(user.id)
    if account is None:
        raise HTTPException(status_code=404, detail="User account not found")
    if _account_requires_totp(account) and not user.mfa_satisfied:
        raise HTTPException(status_code=403, detail="Admin MFA required")
    account.mfa_totp_secret = _totp_secret()
    account.mfa_totp_enabled = True
    USER_ACCOUNTS[account.id] = account

    return TotpEnrollmentResponse(
        secret=account.mfa_totp_secret,
        otpauth_url=_totp_otpauth_url(account),
    )


@app.get("/api/me", response_model=CurrentUser)
def me(user: CurrentUser = Depends(current_user)) -> CurrentUser:
    return user


@app.get("/api/admin/users", response_model=list[UserAccountRead])
async def admin_users(
    _user: CurrentUser = Depends(require_roles(Role.PLATFORM_ADMIN)),
) -> list[UserAccountRead]:
    if persistence_enabled():
        async with async_session_for_current_database() as session:
            return [_user_read(account) for account in await _async_user_accounts(session)]

    _ensure_seed_user_accounts()
    return [_user_read(account) for account in USER_ACCOUNTS.values()]


@app.post("/api/admin/users", response_model=UserAccountRead, status_code=201)
async def create_admin_user(
    account_create: UserAccountCreate,
    _user: CurrentUser = Depends(require_roles(Role.PLATFORM_ADMIN)),
) -> UserAccountRead:
    if account_create.role not in {Role.LEG_ADMIN, Role.PLATFORM_ADMIN}:
        raise HTTPException(
            status_code=400,
            detail="Platform admin can only create internal admin users",
        )
    if persistence_enabled():
        async with async_session_for_current_database() as session:
            if await _async_user_account_by_email(session, account_create.email) is not None:
                raise HTTPException(status_code=409, detail="User account already exists")

            account = _account_with_password(
                user_id=uuid4().hex,
                email=account_create.email,
                display_name=account_create.display_name,
                role=account_create.role,
                password=account_create.password,
            )
            await session.merge(_user_account_row(account))
            await session.commit()
            USER_ACCOUNTS[account.id] = account
            return _user_read(account)

    _ensure_seed_user_accounts()
    if any(
        account.email.lower() == account_create.email.lower()
        for account in USER_ACCOUNTS.values()
    ):
        raise HTTPException(status_code=409, detail="User account already exists")

    account = _account_with_password(
        user_id=uuid4().hex,
        email=account_create.email,
        display_name=account_create.display_name,
        role=account_create.role,
        password=account_create.password,
    )
    USER_ACCOUNTS[account.id] = account
    return _user_read(account)


@app.patch("/api/admin/users/{user_id}", response_model=UserAccountRead)
async def update_admin_user(
    user_id: str,
    account_update: UserAccountUpdate,
    _user: CurrentUser = Depends(require_roles(Role.PLATFORM_ADMIN)),
) -> UserAccountRead:
    if (
        account_update.role is not None
        and account_update.role not in {Role.LEG_ADMIN, Role.PLATFORM_ADMIN}
    ):
        raise HTTPException(
            status_code=400,
            detail="Platform admin can only manage internal admin roles",
        )

    if persistence_enabled():
        async with async_session_for_current_database() as session:
            account = await _async_user_account_by_id(session, user_id)
            if account is None:
                raise HTTPException(status_code=404, detail="User account not found")

            if account_update.display_name is not None:
                account.display_name = account_update.display_name
                participant_row = await session.get(PortalParticipant, account.id)
                if participant_row is not None:
                    participant_row.display_name = account_update.display_name
                    session.add(participant_row)
            if account_update.role is not None:
                account.role = account_update.role
            if account_update.active is not None:
                account.active = account_update.active

            await session.merge(_user_account_row(account))
            await session.commit()
            USER_ACCOUNTS[account.id] = account
            return _user_read(account)

    _ensure_seed_user_accounts()
    account = USER_ACCOUNTS.get(user_id)
    if account is None:
        raise HTTPException(status_code=404, detail="User account not found")

    if account_update.display_name is not None:
        account.display_name = account_update.display_name
        participant = PARTICIPANTS.get(account.id)
        if participant is not None:
            participant.display_name = account_update.display_name
    if account_update.role is not None:
        account.role = account_update.role
    if account_update.active is not None:
        account.active = account_update.active

    return _user_read(account)


@app.post("/api/admin/users/{user_id}/reset-password", response_model=UserAccountRead)
async def reset_admin_user_password(
    user_id: str,
    password_reset: UserPasswordReset,
    _user: CurrentUser = Depends(require_roles(Role.PLATFORM_ADMIN)),
) -> UserAccountRead:
    if persistence_enabled():
        async with async_session_for_current_database() as session:
            account = await _async_user_account_by_id(session, user_id)
            if account is None:
                raise HTTPException(status_code=404, detail="User account not found")

            _set_account_password(account, password_reset.password)
            await session.merge(_user_account_row(account))
            await session.commit()
            USER_ACCOUNTS[account.id] = account
            return _user_read(account)

    _ensure_seed_user_accounts()
    account = USER_ACCOUNTS.get(user_id)
    if account is None:
        raise HTTPException(status_code=404, detail="User account not found")

    _set_account_password(account, password_reset.password)
    return _user_read(account)


@app.post(
    "/api/admin/partner-admin-users",
    response_model=UserAccountRead,
    status_code=201,
)
async def create_partner_admin_user(
    account_create: PartnerAdminUserCreate,
    _user: CurrentUser = Depends(require_roles(Role.LEG_ADMIN)),
) -> UserAccountRead:
    if persistence_enabled():
        async with async_session_for_current_database() as session:
            if await _async_user_account_by_email(session, account_create.email) is not None:
                raise HTTPException(status_code=409, detail="User account already exists")

            account = _account_with_password(
                user_id=uuid4().hex,
                email=account_create.email,
                display_name=account_create.display_name,
                role=Role.PARTNER_ADMIN,
                password=account_create.password,
                organization=account_create.organization,
            )
            session.add(_user_account_row(account))
            await session.commit()
            USER_ACCOUNTS[account.id] = account
            return _user_read(account)

    _ensure_seed_user_accounts()
    if any(
        account.email.lower() == account_create.email.lower()
        for account in USER_ACCOUNTS.values()
    ):
        raise HTTPException(status_code=409, detail="User account already exists")

    account = _account_with_password(
        user_id=uuid4().hex,
        email=account_create.email,
        display_name=account_create.display_name,
        role=Role.PARTNER_ADMIN,
        password=account_create.password,
        organization=account_create.organization,
    )
    USER_ACCOUNTS[account.id] = account
    return _user_read(account)


@app.get("/api/admin/participants", response_model=ParticipantList)
async def admin_participants(
    _user: CurrentUser = Depends(require_roles(Role.LEG_ADMIN, Role.PLATFORM_ADMIN)),
) -> ParticipantList:
    if persistence_enabled():
        async with async_session_for_current_database() as session:
            result = await session.execute(select(PortalParticipant))
            participants = [
                _admin_participant_directory_row(_participant_from_row(row))
                for row in sorted(
                    result.scalars().all(),
                    key=lambda item: (item.display_name, item.email, item.id),
                )
            ]
            return ParticipantList(participants=participants)

    return ParticipantList(
        participants=[
            _admin_participant_directory_row(participant)
            for participant in sorted(
                PARTICIPANTS.values(),
                key=lambda item: (item.display_name, item.email, item.id),
            )
        ],
    )


@app.get(
    "/api/admin/communication-events",
    response_model=list[CommunicationEventRead],
)
async def admin_communication_events(
    recipient_email: str | None = None,
    event_type: str | None = None,
    _user: CurrentUser = Depends(require_roles(Role.LEG_ADMIN, Role.PLATFORM_ADMIN)),
) -> list[CommunicationEventRead]:
    if persistence_enabled():
        async with async_session_for_current_database() as session:
            result = await session.execute(select(PortalCommunicationEvent))
            events = [
                _communication_event_from_row(row)
                for row in sorted(
                    result.scalars().all(),
                    key=lambda item: (item.created_at, item.id),
                )
            ]
    else:
        events = COMMUNICATION_EVENTS

    if recipient_email is not None:
        events = [
            event
            for event in events
            if event.recipient_email == recipient_email
        ]
    if event_type is not None:
        events = [event for event in events if event.event_type == event_type]

    return events


@app.get(
    "/api/admin/participant-invitations",
    response_model=list[ParticipantInvitationRead],
)
async def admin_participant_invitations(
    _user: CurrentUser = Depends(require_roles(Role.LEG_ADMIN, Role.PLATFORM_ADMIN)),
) -> list[ParticipantInvitationRead]:
    if persistence_enabled():
        async with async_session_for_current_database() as session:
            result = await session.execute(select(PortalParticipantInvitation))
            invitations = [
                _participant_invitation_read(_invitation_from_row(row))
                for row in sorted(
                    result.scalars().all(),
                    key=lambda item: (item.email, item.token),
                )
            ]
            return invitations

    return [
        _participant_invitation_read(invitation)
        for invitation in sorted(
            INVITATIONS.values(),
            key=lambda item: (item.email, item.token),
        )
    ]


@app.post(
    "/api/admin/participant-invitations",
    response_model=ParticipantInvitationRead,
    status_code=201,
)
async def create_participant_invitation(
    invitation: ParticipantInvitationCreate,
    _user: CurrentUser = Depends(require_roles(Role.LEG_ADMIN, Role.PLATFORM_ADMIN)),
) -> ParticipantInvitationRead:
    record = ParticipantInvitationRecord(
        token=uuid4().hex,
        email=invitation.email,
        display_name=invitation.display_name,
        leg_id=BASADINGEN_LEG_ID,
        status="pending_email_verification",
    )
    INVITATIONS[record.token] = record
    event = _queue_email_event(
        "participant_invitation",
        record.email,
        invitation_token=record.token,
    )

    if persistence_enabled():
        async with async_session_for_current_database() as session:
            await _async_merge_rows(
                session,
                [
                    _invitation_row(record),
                    _communication_event_row(event),
                ],
            )
            await session.commit()

    if event.status == "failed":
        raise HTTPException(
            status_code=503,
            detail="Email delivery failed",
        )

    return _participant_invitation_read(record)


@app.get(
    "/api/admin/interest-records",
    response_model=list[InterestRecordRead],
)
async def admin_interest_records(
    _user: CurrentUser = Depends(require_roles(Role.LEG_ADMIN, Role.PLATFORM_ADMIN)),
) -> list[InterestRecordRead]:
    if persistence_enabled():
        async with async_session_for_current_database() as session:
            rows = await _async_table_rows(session, PortalInterestRecord)
            records = [_interest_record_from_row(row) for row in rows]
            INTEREST_RECORDS.clear()
            INTEREST_RECORDS.update({record.email: record for record in records})
            return sorted(
                records,
                key=lambda record: (record.created_at, record.email),
            )

    return sorted(
        INTEREST_RECORDS.values(),
        key=lambda record: (record.created_at, record.email),
    )


@app.post(
    "/api/pilot-feedback",
    response_model=PilotFeedbackRead,
    status_code=201,
)
async def submit_pilot_feedback(
    feedback: PilotFeedbackCreate,
    user: CurrentUser = Depends(current_user),
) -> PilotFeedbackRead:
    category = feedback.category.strip()
    message = feedback.message.strip()
    context = feedback.context.strip() if feedback.context is not None else None
    if not category:
        raise HTTPException(status_code=400, detail="Feedback category required")
    if not message:
        raise HTTPException(status_code=400, detail="Feedback message required")

    record = PilotFeedbackRecord(
        id=uuid4().hex,
        category=category,
        message=message,
        context=context or None,
        user_id=user.id,
        user_email=user.email,
        user_role=user.role,
        status="submitted",
        created_at=datetime.now(UTC).isoformat(),
    )
    PILOT_FEEDBACK[record.id] = record

    if persistence_enabled():
        async with async_session_for_current_database() as session:
            session.add(_pilot_feedback_row(record))
            await session.commit()

    return record


@app.get(
    "/api/admin/pilot-feedback",
    response_model=list[PilotFeedbackRead],
)
async def admin_pilot_feedback(
    _user: CurrentUser = Depends(require_roles(Role.LEG_ADMIN, Role.PLATFORM_ADMIN)),
) -> list[PilotFeedbackRead]:
    if persistence_enabled():
        async with async_session_for_current_database() as session:
            result = await session.execute(select(PortalPilotFeedback))
            return [
                _pilot_feedback_from_row(row)
                for row in sorted(
                    result.scalars().all(),
                    key=lambda item: (item.created_at, item.id),
                )
            ]

    return sorted(
        PILOT_FEEDBACK.values(),
        key=lambda record: (record.created_at, record.id),
    )


@app.patch(
    "/api/admin/pilot-feedback/{feedback_id}",
    response_model=PilotFeedbackRead,
)
async def update_pilot_feedback_review(
    feedback_id: str,
    feedback_update: PilotFeedbackUpdate,
    user: CurrentUser = Depends(require_roles(Role.LEG_ADMIN, Role.PLATFORM_ADMIN)),
) -> PilotFeedbackRead:
    status = feedback_update.status.strip()
    rollout_relevance = (
        feedback_update.rollout_relevance.strip()
        if feedback_update.rollout_relevance is not None
        else None
    )
    admin_note = (
        feedback_update.admin_note.strip()
        if feedback_update.admin_note is not None
        else None
    )
    if not status:
        raise HTTPException(status_code=400, detail="Feedback status required")

    reviewed_at = datetime.now(UTC).isoformat()

    if persistence_enabled():
        async with async_session_for_current_database() as session:
            row = await session.get(PortalPilotFeedback, feedback_id)
            if row is None:
                raise HTTPException(status_code=404, detail="Pilot feedback not found")
            row.status = status
            row.rollout_relevance = rollout_relevance or None
            row.admin_note = admin_note or None
            row.reviewed_at = reviewed_at
            row.reviewed_by = user.id
            await session.commit()
            await session.refresh(row)
            record = _pilot_feedback_from_row(row)
            PILOT_FEEDBACK[record.id] = record
            return record

    record = PILOT_FEEDBACK.get(feedback_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Pilot feedback not found")
    updated = record.model_copy(
        update={
            "status": status,
            "rollout_relevance": rollout_relevance or None,
            "admin_note": admin_note or None,
            "reviewed_at": reviewed_at,
            "reviewed_by": user.id,
        }
    )
    PILOT_FEEDBACK[updated.id] = updated
    return updated


@app.post(
    "/api/admin/pilot-allowlist",
    response_model=PilotAllowlistRead,
    status_code=201,
)
async def allow_pilot_email(
    allowlist_entry: PilotAllowlistCreate,
    _user: CurrentUser = Depends(require_roles(Role.LEG_ADMIN, Role.PLATFORM_ADMIN)),
) -> PilotAllowlistRead:
    normalized_email = _normalized_email(allowlist_entry.email)
    if persistence_enabled():
        async with async_session_for_current_database() as session:
            row = await session.get(PortalPilotAllowlistEntry, normalized_email)
            if row is not None:
                record = _pilot_allowlist_from_row(row)
                PILOT_ALLOWLIST[record.email] = record
                return record

            record = PilotAllowlistRead(
                email=normalized_email,
                created_at=datetime.now(UTC).isoformat(),
            )
            session.add(_pilot_allowlist_row(record))
            await session.commit()
            PILOT_ALLOWLIST[normalized_email] = record
            return record

    existing = PILOT_ALLOWLIST.get(normalized_email)
    if existing is not None:
        return existing

    record = PilotAllowlistRead(
        email=normalized_email,
        created_at=datetime.now(UTC).isoformat(),
    )
    PILOT_ALLOWLIST[normalized_email] = record
    return record


@app.post(
    "/api/admin/network-topology-entries",
    response_model=NetworkTopologyImportRead,
    status_code=201,
)
async def import_network_topology_entries(
    topology_import: NetworkTopologyImportCreate,
    _user: CurrentUser = Depends(require_roles(Role.LEG_ADMIN, Role.PLATFORM_ADMIN)),
) -> NetworkTopologyImportRead:
    source_name = topology_import.source_name.strip()
    if not source_name:
        raise HTTPException(status_code=400, detail="Network topology source required")
    if not topology_import.entries:
        raise HTTPException(status_code=400, detail="Network topology entries required")

    imported_at = datetime.now(UTC).isoformat()
    for record in NETWORK_TOPOLOGY_ENTRIES.values():
        record.active = False

    records = [
        NetworkTopologyEntryRecord(
            id=uuid4().hex,
            leg_id=BASADINGEN_LEG_ID,
            source_name=source_name,
            metering_point_id=entry.metering_point_id,
            street=entry.street,
            postal_code=entry.postal_code,
            city=entry.city,
            active=True,
            imported_at=imported_at,
        )
        for entry in topology_import.entries
    ]
    for record in records:
        NETWORK_TOPOLOGY_ENTRIES[record.id] = record

    if persistence_enabled():
        async with async_session_for_current_database() as session:
            existing_result = await session.execute(
                select(PortalNetworkTopologyEntry).where(
                    PortalNetworkTopologyEntry.active == True,  # noqa: E712
                ),
            )
            for existing in existing_result.scalars().all():
                existing.active = False
            session.add_all([_network_topology_entry_row(record) for record in records])
            await session.commit()

    return NetworkTopologyImportRead(
        source_name=source_name,
        imported_entries=len(records),
        active_entries=len(records),
        imported_at=imported_at,
    )


@app.post(
    "/api/auth/self-service-onboarding-requests",
    response_model=SelfServiceOnboardingResponse,
    status_code=201,
)
async def create_self_service_onboarding_request(
    onboarding_request: SelfServiceOnboardingCreate,
) -> SelfServiceOnboardingResponse | JSONResponse:
    _ensure_seed_user_accounts()
    if _public_rollout_gate_incomplete():
        raise HTTPException(status_code=403, detail="Public rollout gate incomplete")
    if _pilot_registration_enabled():
        pilot_allowed = _email_is_pilot_allowed(onboarding_request.email)
        if not pilot_allowed and persistence_enabled():
            async with async_session_for_current_database() as session:
                pilot_allowed = await _async_email_is_pilot_allowed(
                    session,
                    onboarding_request.email,
                )
                if not pilot_allowed:
                    interest_record = await _async_interest_record_for(
                        session,
                        onboarding_request,
                    )
                    await session.commit()
                    return JSONResponse(
                        status_code=202,
                        content=interest_record.model_dump(mode="json"),
                    )
        if not pilot_allowed:
            interest_record = _interest_record_for(onboarding_request)
            return JSONResponse(
                status_code=202,
                content=interest_record.model_dump(mode="json"),
            )

    participant_id = uuid4().hex
    verification_token = uuid4().hex
    initial_display_name = onboarding_request.display_name or "Teilnehmer"
    topology_match = _network_topology_match_from_entries(
        onboarding_request,
        list(NETWORK_TOPOLOGY_ENTRIES.values()),
    )
    participant = ParticipantRecord(
        id=participant_id,
        email=onboarding_request.email,
        display_name=initial_display_name,
        leg_id=BASADINGEN_LEG_ID,
        email_verified=False,
        eligibility_status="approved" if topology_match is not None else "pending_review",
        eligibility_review_reason=(
            _eligibility_reason_for_topology_match(topology_match)
            if topology_match is not None
            else None
        ),
    )
    PARTICIPANTS[participant.id] = participant
    invitation = ParticipantInvitationRecord(
        token=verification_token,
        email=participant.email,
        display_name=participant.display_name,
        leg_id=participant.leg_id,
        status="pending_email_verification",
        participant_id=participant.id,
        source="self_service_onboarding",
    )
    INVITATIONS[verification_token] = invitation
    register_dev_participant_user(
        participant_id=participant.id,
        email=participant.email,
        display_name=participant.display_name,
    )
    account = UserAccountRecord(
        id=participant.id,
        email=participant.email,
        display_name=participant.display_name,
        role=Role.PARTICIPANT,
        active=True,
    )
    USER_ACCOUNTS[participant.id] = account
    verification = _record_identity_verification(
        participant,
        source="self_service_onboarding",
    )
    event = _queue_email_event(
        "email_verification",
        participant.email,
        verification_token=verification_token,
    )
    if persistence_enabled():
        async with async_session_for_current_database() as session:
            if topology_match is None:
                topology_match = await _async_network_topology_match(
                    session,
                    onboarding_request,
                )
                if topology_match is not None:
                    participant.eligibility_status = "approved"
                    participant.eligibility_review_reason = (
                        _eligibility_reason_for_topology_match(topology_match)
                    )
                    PARTICIPANTS[participant.id] = participant
            await _async_merge_rows(
                session,
                [
                    _participant_row(participant),
                    _invitation_row(invitation),
                    _user_account_row(account),
                    _identity_verification_row(verification),
                    _communication_event_row(event),
                ],
            )
            await session.commit()
    if event.status == "failed":
        raise HTTPException(
            status_code=503,
            detail="Email delivery failed",
        )
    user = CurrentUser(
        id=participant.id,
        email=participant.email,
        display_name=participant.display_name,
        role=Role.PARTICIPANT,
    )

    return SelfServiceOnboardingResponse(
        access_token=create_access_token(user),
        token_type="bearer",
        participant_id=participant.id,
        participant_status="pending_email_verification",
        identity_checkpoint=_identity_checkpoint(participant),
        dev_email_verification_token=(
            verification_token if development_auth_enabled() else None
        ),
    )


@app.post(
    "/api/admin/document-versions",
    response_model=DocumentVersionRead,
    status_code=201,
)
async def publish_document_version(
    document: DocumentVersionCreate,
    _user: CurrentUser = Depends(require_roles(Role.LEG_ADMIN)),
) -> DocumentVersionRead:
    record = DocumentVersionRecord(
        id=uuid4().hex,
        document_key=document.document_key,
        title=document.title,
        version=document.version,
        content=document.content,
        document_hash=_document_hash(document),
        context=document.context,
        published_at=datetime.now(UTC).isoformat(),
    )

    if persistence_enabled():
        async with async_session_for_current_database() as session:
            session.add(_document_version_row(record))
            await session.commit()

    DOCUMENT_VERSIONS[record.id] = record

    return DocumentVersionRead(**record.model_dump())


@app.get(
    "/api/admin/document-versions",
    response_model=list[DocumentVersionRead],
)
async def admin_document_versions(
    _user: CurrentUser = Depends(require_roles(Role.LEG_ADMIN, Role.PLATFORM_ADMIN)),
) -> list[DocumentVersionRead]:
    if persistence_enabled():
        async with async_session_for_current_database() as session:
            result = await session.execute(
                select(PortalDocumentVersion).order_by(
                    PortalDocumentVersion.published_at,
                    PortalDocumentVersion.id,
                ),
            )
            return [
                DocumentVersionRead(**_document_version_from_row(row).model_dump())
                for row in result.scalars().all()
            ]

    return [
        DocumentVersionRead(**document.model_dump())
        for document in DOCUMENT_VERSIONS.values()
    ]


@app.get(
    "/api/admin/mutation-requests",
    response_model=list[AdminMutationRequestRead],
)
async def admin_mutation_requests(
    status: str | None = None,
    _user: CurrentUser = Depends(require_roles(Role.LEG_ADMIN, Role.PLATFORM_ADMIN)),
) -> list[AdminMutationRequestRead]:
    if persistence_enabled():
        async with async_session_for_current_database() as session:
            query = (
                select(PortalMutationRequest)
                .where(PortalMutationRequest.leg_id == BASADINGEN_LEG_ID)
                .order_by(
                    PortalMutationRequest.submitted_at,
                    PortalMutationRequest.id,
                )
            )
            if status is not None:
                query = query.where(PortalMutationRequest.status == status)

            result = await session.execute(query)
            records: list[AdminMutationRequestRead] = []
            for row in result.scalars().all():
                participant_row = await session.get(PortalParticipant, row.participant_id)
                if participant_row is None:
                    continue
                records.append(
                    _admin_mutation_request_read_with_participant(
                        _mutation_request_from_row(row),
                        _participant_from_row(participant_row),
                    ),
                )

            return records

    records: list[AdminMutationRequestRead] = []
    for participant_requests in MUTATION_REQUESTS.values():
        for mutation_request in participant_requests:
            if mutation_request.leg_id != BASADINGEN_LEG_ID:
                continue
            if status is not None and mutation_request.status != status:
                continue
            records.append(_admin_mutation_request_read(mutation_request))

    return records


@app.get(
    "/api/admin/participants/{participant_id}/identity-verification",
    response_model=IdentityVerificationRead,
)
async def admin_participant_identity_verification(
    participant_id: str,
    _user: CurrentUser = Depends(require_roles(Role.LEG_ADMIN, Role.PLATFORM_ADMIN)),
) -> IdentityVerificationRead:
    if persistence_enabled():
        async with async_session_for_current_database() as session:
            participant_row = await session.get(PortalParticipant, participant_id)
            if participant_row is None:
                raise HTTPException(status_code=404, detail="Participant not found")

            verification_row = await session.get(
                PortalIdentityVerification,
                participant_id,
            )
            if verification_row is not None:
                return _identity_verification_from_row(verification_row)

            participant = _participant_from_row(participant_row)
            verification = _record_identity_verification(
                participant,
                source="admin_invitation",
            )
            await _async_merge_rows(
                session,
                [_identity_verification_row(verification)],
            )
            await session.commit()
            return verification

    participant = PARTICIPANTS.get(participant_id)
    if participant is None:
        raise HTTPException(status_code=404, detail="Participant not found")

    verification = IDENTITY_VERIFICATIONS.get(participant.id)
    if verification is None:
        verification = _record_identity_verification(
            participant,
            source="admin_invitation",
        )

    return verification


@app.post(
    "/api/admin/participants/{participant_id}/eligibility-review",
    response_model=EligibilityReviewRead,
)
async def review_participant_eligibility(
    participant_id: str,
    review: EligibilityReviewDecision,
    _user: CurrentUser = Depends(require_roles(Role.LEG_ADMIN, Role.PLATFORM_ADMIN)),
) -> EligibilityReviewRead:
    if review.decision not in {"approved", "stopped"}:
        raise HTTPException(status_code=400, detail="Unsupported eligibility decision")
    reason = review.reason.strip()
    if not reason:
        raise HTTPException(status_code=400, detail="Eligibility review reason required")

    if persistence_enabled():
        async with async_session_for_current_database() as session:
            participant_row = await session.get(PortalParticipant, participant_id)
            if participant_row is None:
                raise HTTPException(status_code=404, detail="Participant not found")
            participant = _participant_from_row(participant_row)
            participant.eligibility_status = review.decision
            participant.eligibility_review_reason = reason
            await session.merge(_participant_row(participant))
            await session.commit()
            PARTICIPANTS[participant.id] = participant
            return EligibilityReviewRead(
                participant_id=participant.id,
                eligibility_status=participant.eligibility_status,
                eligibility_review_reason=participant.eligibility_review_reason,
            )

    participant = PARTICIPANTS.get(participant_id)
    if participant is None:
        raise HTTPException(status_code=404, detail="Participant not found")
    participant.eligibility_status = review.decision
    participant.eligibility_review_reason = reason
    PARTICIPANTS[participant.id] = participant
    return EligibilityReviewRead(
        participant_id=participant.id,
        eligibility_status=participant.eligibility_status,
        eligibility_review_reason=participant.eligibility_review_reason,
    )


@app.get(
    "/api/admin/participants/{participant_id}/consent-evidence",
    response_model=list[ConsentEvidenceRead],
)
async def admin_participant_consent_evidence(
    participant_id: str,
    _user: CurrentUser = Depends(require_roles(Role.LEG_ADMIN, Role.PLATFORM_ADMIN)),
) -> list[ConsentEvidenceRead]:
    if persistence_enabled():
        async with async_session_for_current_database() as session:
            participant_row = await session.get(PortalParticipant, participant_id)
            if participant_row is None:
                raise HTTPException(status_code=404, detail="Participant not found")
            result = await session.execute(
                select(PortalConsentEvidence)
                .where(PortalConsentEvidence.participant_id == participant_id)
                .order_by(
                    PortalConsentEvidence.accepted_at,
                    PortalConsentEvidence.document_key,
                    PortalConsentEvidence.document_version_id,
                ),
            )
            return [
                _consent_evidence_from_row(row)
                for row in result.scalars().all()
            ]

    if participant_id not in PARTICIPANTS:
        raise HTTPException(status_code=404, detail="Participant not found")

    return sorted(
        CONSENT_EVIDENCE.get(participant_id, []),
        key=lambda evidence: (
            evidence.accepted_at,
            evidence.document_key,
            evidence.document_version_id,
        ),
    )


@app.post(
    "/api/admin/mutation-requests/{mutation_request_id}/review-decision",
    response_model=AdminMutationRequestRead,
)
async def review_mutation_request(
    mutation_request_id: str,
    decision: MutationReviewDecision,
    user: CurrentUser = Depends(require_roles(Role.LEG_ADMIN)),
) -> AdminMutationRequestRead:
    if persistence_enabled():
        async with async_session_for_current_database() as session:
            row = await session.get(PortalMutationRequest, mutation_request_id)
            if row is None:
                raise HTTPException(
                    status_code=404,
                    detail="Mutation request not found",
                )
            participant_row = await session.get(PortalParticipant, row.participant_id)
            if participant_row is None:
                raise HTTPException(status_code=404, detail="Participant not found")

            mutation_request = _apply_mutation_review_decision(
                _mutation_request_from_row(row),
                decision,
                user,
            )
            await session.merge(_mutation_request_row(mutation_request))
            await session.commit()
            return _admin_mutation_request_read_with_participant(
                mutation_request,
                _participant_from_row(participant_row),
            )

    mutation_request = _apply_mutation_review_decision(
        _find_mutation_request(mutation_request_id),
        decision,
        user,
    )
    return _admin_mutation_request_read(mutation_request)


@app.post(
    "/api/admin/mutation-requests/{mutation_request_id}/package-readiness",
    response_model=AdminMutationRequestRead,
)
async def check_mutation_package_readiness(
    mutation_request_id: str,
    decision: MutationPackageReadinessDecision,
    user: CurrentUser = Depends(require_roles(Role.LEG_ADMIN)),
) -> AdminMutationRequestRead:
    if persistence_enabled():
        async with async_session_for_current_database() as session:
            row = await session.get(PortalMutationRequest, mutation_request_id)
            if row is None:
                raise HTTPException(
                    status_code=404,
                    detail="Mutation request not found",
                )
            participant_row = await session.get(PortalParticipant, row.participant_id)
            if participant_row is None:
                raise HTTPException(status_code=404, detail="Participant not found")

            mutation_request = _apply_mutation_package_readiness(
                _mutation_request_from_row(row),
                decision,
                user,
            )
            await session.merge(_mutation_request_row(mutation_request))
            await session.commit()
            return _admin_mutation_request_read_with_participant(
                mutation_request,
                _participant_from_row(participant_row),
            )

    mutation_request = _apply_mutation_package_readiness(
        _find_mutation_request(mutation_request_id),
        decision,
        user,
    )
    return _admin_mutation_request_read(mutation_request)


@app.post(
    "/api/admin/mutation-requests/{mutation_request_id}/file-evidence",
    response_model=FileEvidenceMetadataRead,
    status_code=201,
)
async def attach_mutation_request_file_evidence(
    mutation_request_id: str,
    evidence: FileEvidenceCreate,
    _user: CurrentUser = Depends(require_roles(Role.LEG_ADMIN)),
) -> FileEvidenceMetadataRead:
    evidence_config = FILE_EVIDENCE_PURPOSES.get(
        (evidence.document_type, evidence.purpose),
    )
    if evidence_config is None:
        raise HTTPException(
            status_code=400,
            detail="File evidence document type and purpose are not configured",
        )

    if persistence_enabled():
        async with async_session_for_current_database() as session:
            mutation_row = await session.get(PortalMutationRequest, mutation_request_id)
            if mutation_row is None:
                raise HTTPException(
                    status_code=404,
                    detail="Mutation request not found",
                )
            mutation_request = _mutation_request_from_row(mutation_row)
            content = b64decode(evidence.content_base64)
            record = FileEvidenceRecord(
                id=uuid4().hex,
                mutation_request_id=mutation_request.id,
                participant_id=mutation_request.participant_id,
                document_type=evidence.document_type,
                purpose=evidence.purpose,
                version=evidence.version,
                filename=evidence.filename,
                content_type=evidence.content_type,
                sha256_hash=sha256(content).hexdigest(),
                access_protection=evidence_config["access_protection"],
                retention_status=evidence_config["retention_status"],
                created_at=datetime.now(UTC).isoformat(),
                content_base64=evidence.content_base64,
            )
            session.add(_file_evidence_row(record))
            await session.commit()
            return FileEvidenceMetadataRead(**record.model_dump())

    mutation_request = _find_mutation_request(mutation_request_id)
    content = b64decode(evidence.content_base64)
    record = FileEvidenceRecord(
        id=uuid4().hex,
        mutation_request_id=mutation_request.id,
        participant_id=mutation_request.participant_id,
        document_type=evidence.document_type,
        purpose=evidence.purpose,
        version=evidence.version,
        filename=evidence.filename,
        content_type=evidence.content_type,
        sha256_hash=sha256(content).hexdigest(),
        access_protection=evidence_config["access_protection"],
        retention_status=evidence_config["retention_status"],
        created_at=datetime.now(UTC).isoformat(),
        content_base64=evidence.content_base64,
    )
    FILE_EVIDENCE.setdefault(mutation_request.id, []).append(record)

    return FileEvidenceMetadataRead(**record.model_dump())


@app.get(
    "/api/mutation-requests/{mutation_request_id}/file-evidence/{file_evidence_id}",
    response_model=FileEvidenceMetadataRead,
)
async def file_evidence_metadata(
    mutation_request_id: str,
    file_evidence_id: str,
    user: CurrentUser = Depends(current_user),
) -> FileEvidenceMetadataRead:
    if persistence_enabled():
        async with async_session_for_current_database() as session:
            row = await session.get(PortalFileEvidence, file_evidence_id)
            if row is None or row.mutation_request_id != mutation_request_id:
                raise HTTPException(
                    status_code=404,
                    detail="File evidence not found",
                )
            evidence = _file_evidence_from_row(row)
            await _async_authorize_file_evidence_access(session, evidence, user)
            return FileEvidenceMetadataRead(**evidence.model_dump())

    evidence = _find_file_evidence(mutation_request_id, file_evidence_id)
    _authorize_file_evidence_access(evidence, user)

    return FileEvidenceMetadataRead(**evidence.model_dump())


@app.get(
    "/api/mutation-requests/{mutation_request_id}/file-evidence/{file_evidence_id}/content",
    response_model=FileEvidenceContentRead,
)
async def file_evidence_content(
    mutation_request_id: str,
    file_evidence_id: str,
    user: CurrentUser = Depends(current_user),
) -> FileEvidenceContentRead:
    if persistence_enabled():
        async with async_session_for_current_database() as session:
            row = await session.get(PortalFileEvidence, file_evidence_id)
            if row is None or row.mutation_request_id != mutation_request_id:
                raise HTTPException(
                    status_code=404,
                    detail="File evidence not found",
                )
            evidence = _file_evidence_from_row(row)
            await _async_authorize_file_evidence_access(session, evidence, user)
            return FileEvidenceContentRead(**evidence.model_dump())

    evidence = _find_file_evidence(mutation_request_id, file_evidence_id)
    _authorize_file_evidence_access(evidence, user)

    return FileEvidenceContentRead(**evidence.model_dump())


@app.post(
    "/api/admin/mutation-packages",
    response_model=MutationPackageRead,
    status_code=201,
)
async def create_mutation_package(
    package: MutationPackageCreate,
    user: CurrentUser = Depends(require_roles(Role.LEG_ADMIN)),
) -> MutationPackageRead:
    _participant_deadline, _quarter_end, effective_date = (
        _regular_address_quarter_dates(package.quarter)
    )
    if persistence_enabled():
        async with async_session_for_current_database() as session:
            packaged_request_ids = {
                row.mutation_request_id
                for row in await _async_table_rows(
                    session,
                    PortalPackagedMutationRequest,
                )
            }
            result = await session.execute(
                select(PortalMutationRequest).where(
                    PortalMutationRequest.leg_id == BASADINGEN_LEG_ID,
                    PortalMutationRequest.status.in_(PACKAGE_READY_MUTATION_STATUSES),
                ),
            )
            approved_requests = sorted(
                [
                    mutation_request
                    for mutation_request in (
                        _mutation_request_from_row(row)
                        for row in result.scalars().all()
                    )
                    if mutation_request.quarter == package.quarter
                    and _mutation_request_is_package_ready(mutation_request)
                    and mutation_request.id not in packaged_request_ids
                ],
                key=lambda mutation_request: (
                    mutation_request.reviewed_at or "",
                    mutation_request.id,
                ),
            )
            if not approved_requests:
                raise HTTPException(
                    status_code=400,
                    detail=NO_PACKAGE_READY_MUTATIONS_DETAIL,
                )

            mutation_package = _build_mutation_package(
                quarter=package.quarter,
                effective_date=effective_date,
                approved_requests=approved_requests,
                user=user,
            )
            session.add(_mutation_package_row(mutation_package))
            session.add(
                _mutation_package_metadata_row(
                    _default_mutation_package_metadata(mutation_package),
                ),
            )
            for mutation_request in approved_requests:
                session.add(
                    PortalPackagedMutationRequest(
                        mutation_request_id=mutation_request.id,
                        package_id=mutation_package.package_id,
                    ),
                )
            try:
                await session.commit()
            except IntegrityError as error:
                await session.rollback()
                raise HTTPException(
                    status_code=400,
                    detail=NO_PACKAGE_READY_MUTATIONS_DETAIL,
                ) from error

            return mutation_package

    approved_requests = sorted(
        [
            mutation_request
            for participant_requests in MUTATION_REQUESTS.values()
            for mutation_request in participant_requests
            if mutation_request.leg_id == BASADINGEN_LEG_ID
            and mutation_request.status in PACKAGE_READY_MUTATION_STATUSES
            and _mutation_request_is_package_ready(mutation_request)
            and mutation_request.quarter == package.quarter
            and mutation_request.id not in PACKAGED_MUTATION_REQUEST_IDS
        ],
        key=lambda mutation_request: (
            mutation_request.reviewed_at or "",
            mutation_request.id,
        ),
    )
    if not approved_requests:
        raise HTTPException(
            status_code=400,
            detail=NO_PACKAGE_READY_MUTATIONS_DETAIL,
        )

    mutation_package = _build_mutation_package(
        quarter=package.quarter,
        effective_date=effective_date,
        approved_requests=approved_requests,
        user=user,
    )
    MUTATION_PACKAGES[mutation_package.package_id] = mutation_package
    PACKAGED_MUTATION_REQUEST_IDS.update(
        mutation_request.id for mutation_request in approved_requests
    )

    return mutation_package


@app.get(
    "/api/partner/mutation-packages",
    response_model=list[PartnerMutationPackageSummary],
)
async def partner_mutation_packages(
    _user: CurrentUser = Depends(require_roles(Role.PARTNER_ADMIN)),
) -> list[PartnerMutationPackageSummary]:
    if persistence_enabled():
        async with async_session_for_current_database() as session:
            summaries: list[PartnerMutationPackageSummary] = []
            for package in sorted(
                await _async_mutation_packages(session),
                key=lambda item: item.generated_at,
                reverse=True,
            ):
                metadata = await _async_mutation_package_metadata(session, package)
                summaries.append(
                    _partner_mutation_package_summary_with_metadata(package, metadata),
                )
            return summaries

    return [
        _partner_mutation_package_summary(package)
        for package in sorted(
            MUTATION_PACKAGES.values(),
            key=lambda item: item.generated_at,
            reverse=True,
        )
    ]


@app.get(
    "/api/partner/mutation-packages/{package_id}",
    response_model=PartnerMutationPackageDetail,
)
async def partner_mutation_package_detail(
    package_id: str,
    _user: CurrentUser = Depends(require_roles(Role.PARTNER_ADMIN)),
) -> PartnerMutationPackageDetail:
    if persistence_enabled():
        async with async_session_for_current_database() as session:
            package = await _async_find_mutation_package(session, package_id)
            metadata = await _async_mutation_package_metadata(session, package)
            return _partner_mutation_package_detail_with_metadata(package, metadata)

    package = _find_mutation_package(package_id)

    return _partner_mutation_package_detail(package)


@app.get(
    "/api/partner/member-register",
    response_model=PartnerMemberRegisterRead,
)
async def partner_member_register(
    _user: CurrentUser = Depends(require_roles(Role.PARTNER_ADMIN)),
) -> PartnerMemberRegisterRead:
    if persistence_enabled():
        async with async_session_for_current_database() as session:
            latest_member_records: dict[
                str,
                tuple[MutationPackageRead, MutationPackageRecord],
            ] = {}
            for package in sorted(
                await _async_mutation_packages(session),
                key=lambda item: (
                    item.effective_date,
                    item.generated_at,
                    item.package_id,
                ),
            ):
                if package.leg_id != BASADINGEN_LEG_ID:
                    continue

                for record in package.records:
                    latest_member_records[record.participant_id] = (package, record)

            members: list[tuple[str, PartnerMemberRead]] = []
            for package, record in latest_member_records.values():
                participant_row = await session.get(
                    PortalParticipant,
                    record.participant_id,
                )
                if participant_row is None:
                    continue
                participant = _participant_from_row(participant_row)
                metadata = await _async_mutation_package_metadata(session, package)
                membership_status = (
                    "active"
                    if participant.email_verified
                    else "pending_email_verification"
                )
                members.append(
                    (
                        participant.display_name,
                        PartnerMemberRead(
                            participant_id=participant.id,
                            display_name=participant.display_name,
                            membership_status=membership_status,
                            reporting_address=record.new_address,
                            latest_package_status=PartnerMemberLatestPackageStatus(
                                package_id=package.package_id,
                                quarter=package.quarter,
                                effective_date=record.effective_date,
                                status=metadata.current_status,
                            ),
                        ),
                    ),
                )

            return PartnerMemberRegisterRead(
                leg_id=BASADINGEN_LEG_ID,
                leg_name=BASADINGEN_LEG_NAME,
                members=[
                    member
                    for _display_name, member in sorted(
                        members,
                        key=lambda item: item[0],
                    )
                ],
            )

    latest_member_records: dict[str, tuple[MutationPackageRead, MutationPackageRecord]] = {}
    for package in sorted(
        MUTATION_PACKAGES.values(),
        key=lambda item: (item.effective_date, item.generated_at, item.package_id),
    ):
        if package.leg_id != BASADINGEN_LEG_ID:
            continue

        for record in package.records:
            latest_member_records[record.participant_id] = (package, record)

    return PartnerMemberRegisterRead(
        leg_id=BASADINGEN_LEG_ID,
        leg_name=BASADINGEN_LEG_NAME,
        members=[
            _partner_member_read(package, record)
            for package, record in sorted(
                latest_member_records.values(),
                key=lambda item: PARTICIPANTS[item[1].participant_id].display_name,
            )
        ],
    )


@app.get(
    "/api/admin/partner-tasks",
    response_model=list[AdminPartnerTaskRead],
)
async def admin_partner_tasks(
    _user: CurrentUser = Depends(require_roles(Role.LEG_ADMIN)),
) -> list[AdminPartnerTaskRead]:
    if persistence_enabled():
        async with async_session_for_current_database() as session:
            tasks: list[AdminPartnerTaskRead] = []
            for package in await _async_mutation_packages(session):
                if package.leg_id != BASADINGEN_LEG_ID:
                    continue

                metadata = await _async_mutation_package_metadata(session, package)
                latest_status_event = metadata.status_history[-1]
                if latest_status_event.status in {
                    "question",
                    "technically_not_possible",
                }:
                    tasks.append(_admin_partner_task_read(package, latest_status_event))

            return sorted(tasks, key=lambda task: task.created_at, reverse=True)

    tasks: list[AdminPartnerTaskRead] = []
    for package in MUTATION_PACKAGES.values():
        if package.leg_id != BASADINGEN_LEG_ID:
            continue

        latest_status_event = _mutation_package_metadata(package).status_history[-1]
        if latest_status_event.status in {"question", "technically_not_possible"}:
            tasks.append(_admin_partner_task_read(package, latest_status_event))

    return sorted(tasks, key=lambda task: task.created_at, reverse=True)


@app.get(
    "/api/partner/tasks",
    response_model=list[PartnerTaskRead],
)
async def partner_tasks(
    _user: CurrentUser = Depends(require_roles(Role.PARTNER_ADMIN)),
) -> list[PartnerTaskRead]:
    if persistence_enabled():
        async with async_session_for_current_database() as session:
            tasks: list[PartnerTaskRead] = []
            for package in await _async_mutation_packages(session):
                if package.leg_id != BASADINGEN_LEG_ID:
                    continue

                metadata = await _async_mutation_package_metadata(session, package)
                latest_status_event = metadata.status_history[-1]
                if latest_status_event.status in {
                    "question",
                    "technically_not_possible",
                }:
                    tasks.append(_partner_task_read(package, latest_status_event))

            return sorted(tasks, key=lambda task: task.created_at, reverse=True)

    tasks: list[PartnerTaskRead] = []
    for package in MUTATION_PACKAGES.values():
        if package.leg_id != BASADINGEN_LEG_ID:
            continue

        latest_status_event = _mutation_package_metadata(package).status_history[-1]
        if latest_status_event.status in {"question", "technically_not_possible"}:
            tasks.append(_partner_task_read(package, latest_status_event))

    return sorted(tasks, key=lambda task: task.created_at, reverse=True)


@app.post(
    "/api/partner/mutation-packages/{package_id}/status",
    response_model=PartnerMutationPackageStatusRead,
)
async def update_partner_mutation_package_status(
    package_id: str,
    status_update: MutationPackageStatusUpdate,
    user: CurrentUser = Depends(require_roles(Role.PARTNER_ADMIN)),
) -> PartnerMutationPackageStatusRead:
    if status_update.status not in SUPPORTED_PARTNER_PACKAGE_STATUSES:
        raise HTTPException(status_code=400, detail="Unsupported package status")

    reference = (status_update.reference or "").strip() or None
    reason = (status_update.reason or "").strip() or None
    if (
        status_update.status in {"question", "technically_not_possible"}
        and reference is None
        and reason is None
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Status question or technically_not_possible requires a "
                "reference or reason"
            ),
        )

    if persistence_enabled():
        async with async_session_for_current_database() as session:
            package = await _async_find_mutation_package(session, package_id)
            metadata = await _async_mutation_package_metadata(session, package)
            metadata.status_history.append(
                MutableMutationPackageStatusEvent(
                    status=status_update.status,
                    actor_id=user.id,
                    actor_role=user.role.value,
                    created_at=datetime.now(UTC).isoformat(),
                    reference=reference,
                    reason=reason,
                ),
            )
            metadata.current_status = status_update.status
            metadata_payload = _mutation_package_metadata_row(metadata)
            metadata_row = await session.get(
                PortalMutationPackageMetadata,
                package.package_id,
            )
            if metadata_row is None:
                session.add(metadata_payload)
            else:
                metadata_row.current_status = metadata_payload.current_status
                metadata_row.payload_json = metadata_payload.payload_json
                session.add(metadata_row)
            await session.commit()

            return _partner_status_read(metadata)

    package = _find_mutation_package(package_id)
    metadata = _mutation_package_metadata(package)
    metadata.status_history.append(
        MutableMutationPackageStatusEvent(
            status=status_update.status,
            actor_id=user.id,
            actor_role=user.role.value,
            created_at=datetime.now(UTC).isoformat(),
            reference=reference,
            reason=reason,
        ),
    )
    metadata.current_status = status_update.status

    return _partner_status_read(metadata)


@app.get(
    "/api/admin/mutation-packages/{package_id}",
    response_model=AdminMutationPackageMetadataRead,
)
async def admin_mutation_package_metadata(
    package_id: str,
    _user: CurrentUser = Depends(require_roles(Role.LEG_ADMIN)),
) -> AdminMutationPackageMetadataRead:
    if persistence_enabled():
        async with async_session_for_current_database() as session:
            package = await _async_find_mutation_package(session, package_id)
            return await _async_mutation_package_metadata(session, package)

    package = _find_mutation_package(package_id)

    return _mutation_package_metadata(package)


@app.get(
    "/api/admin/mutation-packages/{package_id}/json",
    response_model=MutationPackageRead,
)
async def mutation_package_json_artifact(
    package_id: str,
    _user: CurrentUser = Depends(require_roles(Role.LEG_ADMIN)),
) -> MutationPackageRead:
    if persistence_enabled():
        async with async_session_for_current_database() as session:
            return await _async_find_mutation_package(session, package_id)

    return _find_mutation_package(package_id)


@app.get("/api/admin/mutation-packages/{package_id}/csv")
async def mutation_package_csv_artifact(
    package_id: str,
    _user: CurrentUser = Depends(require_roles(Role.LEG_ADMIN)),
) -> Response:
    if persistence_enabled():
        async with async_session_for_current_database() as session:
            mutation_package = await _async_find_mutation_package(session, package_id)
            return Response(
                content=_mutation_package_csv(mutation_package),
                media_type="text/csv",
                headers={
                    "Content-Disposition": (
                        f'attachment; filename="mutation-package-{package_id}.csv"'
                    ),
                },
            )

    mutation_package = _find_mutation_package(package_id)
    return Response(
        content=_mutation_package_csv(mutation_package),
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                f'attachment; filename="mutation-package-{package_id}.csv"'
            ),
        },
    )


@app.get("/api/admin/mutation-packages/{package_id}/pdf")
async def mutation_package_pdf_artifact(
    package_id: str,
    _user: CurrentUser = Depends(require_roles(Role.LEG_ADMIN)),
) -> Response:
    if persistence_enabled():
        async with async_session_for_current_database() as session:
            mutation_package = await _async_find_mutation_package(session, package_id)
            return Response(
                content=_mutation_package_pdf(mutation_package),
                media_type="application/pdf",
                headers={
                    "Content-Disposition": (
                        f'attachment; filename="mutation-package-{package_id}.pdf"'
                    ),
                },
            )

    mutation_package = _find_mutation_package(package_id)
    return Response(
        content=_mutation_package_pdf(mutation_package),
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="mutation-package-{package_id}.pdf"'
            ),
        },
    )


@app.get("/api/documents/current", response_model=CurrentDocumentRead)
async def current_document_version(
    document_key: str,
    user: CurrentUser = Depends(current_user),
) -> CurrentDocumentRead:
    if persistence_enabled():
        async with async_session_for_current_database() as session:
            if user.role == Role.PARTICIPANT:
                await _async_verified_participant(session, user)

            result = await session.execute(
                select(PortalDocumentVersion)
                .where(
                    PortalDocumentVersion.document_key == document_key,
                    PortalDocumentVersion.context
                    == REQUIRED_PARTICIPANT_DOCUMENT_CONTEXT,
                )
                .order_by(
                    PortalDocumentVersion.published_at.desc(),
                    PortalDocumentVersion.id.desc(),
                )
                .limit(1),
            )
            row = result.scalars().first()
            if row is None:
                raise HTTPException(
                    status_code=404,
                    detail="Document version not found",
                )

            return CurrentDocumentRead(**_document_version_from_row(row).model_dump())

    if user.role == Role.PARTICIPANT:
        _verified_participant(user)

    document = _current_document_version(
        document_key,
        context=REQUIRED_PARTICIPANT_DOCUMENT_CONTEXT,
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Document version not found")

    return CurrentDocumentRead(**document.model_dump())


@app.post(
    "/api/participants/me/consent-evidence",
    response_model=ConsentEvidenceRead,
    status_code=201,
)
async def record_consent_evidence(
    consent: ConsentEvidenceCreate,
    user: CurrentUser = Depends(require_roles(Role.PARTICIPANT)),
) -> ConsentEvidenceRead:
    if not consent.accepted:
        raise HTTPException(status_code=400, detail="Consent must be accepted")

    if persistence_enabled():
        async with async_session_for_current_database() as session:
            participant = await _async_verified_participant(session, user)
            document_row = await session.get(
                PortalDocumentVersion,
                consent.document_version_id,
            )
            if document_row is None:
                raise HTTPException(
                    status_code=404,
                    detail="Document version not found",
                )
            document = _document_version_from_row(document_row)
            if document.context != consent.context:
                raise HTTPException(status_code=400, detail="Document context mismatch")

            evidence = ConsentEvidenceRead(
                participant_id=participant.id,
                document_version_id=document.id,
                document_key=document.document_key,
                version=document.version,
                document_hash=document.document_hash,
                context=consent.context,
                accepted_at=datetime.now(UTC).isoformat(),
            )
            session.add(_consent_evidence_row(evidence))
            await session.commit()
            CONSENT_EVIDENCE.setdefault(participant.id, []).append(evidence)
            return evidence

    participant = _verified_participant(user)

    document = DOCUMENT_VERSIONS.get(consent.document_version_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document version not found")
    if document.context != consent.context:
        raise HTTPException(status_code=400, detail="Document context mismatch")

    evidence = ConsentEvidenceRead(
        participant_id=participant.id,
        document_version_id=document.id,
        document_key=document.document_key,
        version=document.version,
        document_hash=document.document_hash,
        context=consent.context,
        accepted_at=datetime.now(UTC).isoformat(),
    )
    CONSENT_EVIDENCE.setdefault(participant.id, []).append(evidence)

    return evidence


@app.get(
    "/api/participants/me/consent-evidence",
    response_model=list[ConsentEvidenceRead],
)
async def participant_consent_history(
    user: CurrentUser = Depends(require_roles(Role.PARTICIPANT)),
) -> list[ConsentEvidenceRead]:
    if persistence_enabled():
        async with async_session_for_current_database() as session:
            participant = await _async_verified_participant(session, user)
            result = await session.execute(
                select(PortalConsentEvidence)
                .where(PortalConsentEvidence.participant_id == participant.id)
                .order_by(
                    PortalConsentEvidence.accepted_at,
                    PortalConsentEvidence.participant_id,
                    PortalConsentEvidence.document_version_id,
                ),
            )
            return [
                _consent_evidence_from_row(row)
                for row in result.scalars().all()
            ]

    participant = _verified_participant(user)

    return CONSENT_EVIDENCE.get(participant.id, [])


@app.get(
    "/api/participants/me/contact-channels",
    response_model=ParticipantContactChannelsRead,
)
async def participant_contact_channels(
    user: CurrentUser = Depends(require_roles(Role.PARTICIPANT)),
) -> ParticipantContactChannelsRead:
    if persistence_enabled():
        async with async_session_for_current_database() as session:
            participant = await _async_verified_participant(session, user)
            return await _async_participant_contact_channels_read(session, participant)

    participant = _verified_participant(user)

    return _participant_contact_channels_read(participant)


@app.patch(
    "/api/participants/me/contact-channels",
    response_model=ParticipantContactChannelsRead,
)
async def update_participant_contact_channels(
    contact_channels: ParticipantContactChannelsUpdate,
    user: CurrentUser = Depends(require_roles(Role.PARTICIPANT)),
) -> ParticipantContactChannelsRead:
    if persistence_enabled():
        async with async_session_for_current_database() as session:
            participant = await _async_verified_participant(session, user)
            participant.phone_number = contact_channels.phone_number
            participant.preferred_contact_channel = contact_channels.preferred_contact_channel
            audit_event = AuditEventRead(
                id=uuid4().hex,
                action="participant.contact_channels_updated",
                actor_role=user.role.value,
                created_at=datetime.now(UTC).isoformat(),
            )
            PARTICIPANTS[participant.id] = participant
            PARTICIPANT_AUDIT_EVENTS.setdefault(participant.id, []).append(audit_event)
            await _async_merge_rows(
                session,
                [
                    _participant_row(participant),
                    _participant_audit_event_row(participant.id, audit_event),
                ],
            )
            await session.commit()
            return await _async_participant_contact_channels_read(session, participant)

    participant = _verified_participant(user)
    participant.phone_number = contact_channels.phone_number
    participant.preferred_contact_channel = contact_channels.preferred_contact_channel
    PARTICIPANT_AUDIT_EVENTS.setdefault(participant.id, []).append(
        AuditEventRead(
            id=uuid4().hex,
            action="participant.contact_channels_updated",
            actor_role=user.role.value,
            created_at=datetime.now(UTC).isoformat(),
        ),
    )

    return _participant_contact_channels_read(participant)


@app.post(
    "/api/participants/me/mutation-requests",
    response_model=MutationRequestRead,
    status_code=201,
)
async def create_participant_mutation_request(
    mutation: MutationRequestCreate,
    user: CurrentUser = Depends(require_roles(Role.PARTICIPANT)),
) -> MutationRequestRead:
    if persistence_enabled():
        async with async_session_for_current_database() as session:
            participant = await _async_verified_participant(session, user)
            _require_eligibility_approved(participant)
            await _async_require_required_document_acceptance(session, participant)
            mutation_request = _build_mutation_request(participant, mutation)
            session.add(_mutation_request_row(mutation_request))
            await session.commit()
            return mutation_request

    participant = _verified_participant(user)
    _require_eligibility_approved(participant)
    _require_required_document_acceptance(participant)
    mutation_request = _build_mutation_request(participant, mutation)
    MUTATION_REQUESTS.setdefault(participant.id, []).append(mutation_request)

    return mutation_request


@app.get(
    "/api/participants/me/mutation-requests",
    response_model=list[ParticipantMutationRequestRead],
)
async def participant_mutation_requests(
    user: CurrentUser = Depends(require_roles(Role.PARTICIPANT)),
) -> list[ParticipantMutationRequestRead]:
    if persistence_enabled():
        async with async_session_for_current_database() as session:
            participant = await _async_verified_participant(session, user)
            result = await session.execute(
                select(PortalMutationRequest)
                .where(PortalMutationRequest.participant_id == participant.id)
                .order_by(
                    PortalMutationRequest.submitted_at,
                    PortalMutationRequest.id,
                ),
            )
            return [
                _mutation_request_from_row(row)
                for row in result.scalars().all()
            ]

    participant = _verified_participant(user)

    return MUTATION_REQUESTS.get(participant.id, [])


@app.get(
    "/api/auth/invitations/{token}/accept",
    response_model=InvitationAcceptResponse,
)
@app.post(
    "/api/auth/invitations/{token}/accept",
    response_model=InvitationAcceptResponse,
)
async def accept_participant_invitation(token: str) -> InvitationAcceptResponse:
    invitation = INVITATIONS.get(token)
    if persistence_enabled():
        async with async_session_for_current_database() as session:
            invitation_row = await session.get(PortalParticipantInvitation, token)
            if invitation_row is not None:
                invitation = _invitation_from_row(invitation_row)

    if invitation is None:
        raise HTTPException(status_code=404, detail="Invitation not found")

    _ensure_seed_user_accounts()
    participant_id = invitation.participant_id or uuid4().hex
    invitation.participant_id = participant_id
    invitation.status = "accepted_pending_email_verification"
    participant = ParticipantRecord(
        id=participant_id,
        email=invitation.email,
        display_name=invitation.display_name,
        leg_id=invitation.leg_id,
        email_verified=False,
    )
    INVITATIONS[invitation.token] = invitation
    PARTICIPANTS[participant_id] = participant
    _record_identity_verification(participant, source=invitation.source)
    register_dev_participant_user(
        participant_id=participant.id,
        email=participant.email,
        display_name=participant.display_name,
    )
    USER_ACCOUNTS.setdefault(
        participant.id,
        UserAccountRecord(
            id=participant.id,
            email=participant.email,
            display_name=participant.display_name,
            role=Role.PARTICIPANT,
            active=True,
        ),
    )
    account = USER_ACCOUNTS[participant.id]
    event = _queue_email_event(
        "email_verification",
        participant.email,
        verification_token=invitation.token,
    )

    if persistence_enabled():
        async with async_session_for_current_database() as session:
            await _async_merge_rows(
                session,
                [
                    _invitation_row(invitation),
                    _participant_row(participant),
                    _identity_verification_row(
                        IDENTITY_VERIFICATIONS[participant.id],
                    ),
                    _user_account_row(account),
                    _communication_event_row(event),
                ],
            )
            await session.commit()

    if event.status == "failed":
        raise HTTPException(
            status_code=503,
            detail="Email delivery failed",
        )

    user = CurrentUser(
        id=participant.id,
        email=participant.email,
        display_name=participant.display_name,
        role=Role.PARTICIPANT,
    )
    access_token = (
        f"dev:participant:{participant_id}"
        if development_auth_enabled()
        else create_access_token(user)
    )

    return InvitationAcceptResponse(
        access_token=access_token,
        token_type="bearer",
        participant_id=participant_id,
        email_verification_required=True,
    )


@app.get(
    "/api/auth/email-verifications/{token}/verify",
    response_model=EmailVerificationResponse,
)
@app.post(
    "/api/auth/email-verifications/{token}/verify",
    response_model=EmailVerificationResponse,
)
async def verify_participant_email(token: str) -> EmailVerificationResponse:
    invitation = INVITATIONS.get(token)
    if persistence_enabled():
        async with async_session_for_current_database() as session:
            invitation_row = await session.get(PortalParticipantInvitation, token)
            if invitation_row is not None:
                invitation = _invitation_from_row(invitation_row)

    if invitation is None or invitation.participant_id is None:
        raise HTTPException(status_code=404, detail="Email verification not found")

    participant = PARTICIPANTS.get(invitation.participant_id)
    if persistence_enabled():
        async with async_session_for_current_database() as session:
            participant_row = await session.get(
                PortalParticipant,
                invitation.participant_id,
            )
            if participant_row is not None:
                participant = _participant_from_row(participant_row)
    if participant is None:
        raise HTTPException(status_code=404, detail="Participant not found")

    participant.email_verified = True
    invitation.status = "active"
    verification = _record_identity_verification(
        participant,
        source=invitation.source,
        verified_at=datetime.now(UTC).isoformat(),
    )
    register_dev_participant_user(
        participant_id=participant.id,
        email=participant.email,
        display_name=participant.display_name,
    )
    account = USER_ACCOUNTS.get(participant.id)
    if account is not None:
        account.display_name = participant.display_name

    PARTICIPANTS[participant.id] = participant
    INVITATIONS[invitation.token] = invitation
    if persistence_enabled():
        async with async_session_for_current_database() as session:
            rows = [
                _invitation_row(invitation),
                _participant_row(participant),
                _identity_verification_row(verification),
            ]
            if account is not None:
                rows.append(_user_account_row(account))
            await _async_merge_rows(session, rows)
            await session.commit()

    return EmailVerificationResponse(
        participant_id=participant.id,
        email_verified=participant.email_verified,
    )


@app.post("/api/auth/participant-account-setup", response_model=AuthTokenResponse)
async def setup_participant_account(
    setup: ParticipantAccountSetup,
    user: CurrentUser = Depends(require_roles(Role.PARTICIPANT)),
) -> AuthTokenResponse:
    participant = PARTICIPANTS.get(user.id)
    if persistence_enabled():
        async with async_session_for_current_database() as session:
            participant_row = await session.get(PortalParticipant, user.id)
            if participant_row is not None:
                participant = _participant_from_row(participant_row)

    if participant is None:
        raise HTTPException(status_code=404, detail="Participant not found")
    if not participant.email_verified:
        raise HTTPException(status_code=403, detail="Email verification required")

    account = USER_ACCOUNTS.get(participant.id)
    if persistence_enabled():
        async with async_session_for_current_database() as session:
            account_row = await session.get(PortalUserAccount, participant.id)
            if account_row is not None:
                account = _user_account_from_row(account_row)

    if account is None:
        account = UserAccountRecord(
            id=participant.id,
            email=participant.email,
            display_name=setup.display_name,
            role=Role.PARTICIPANT,
            active=True,
        )
        USER_ACCOUNTS[account.id] = account

    participant.display_name = setup.display_name
    account.display_name = setup.display_name
    account.email = participant.email
    account.role = Role.PARTICIPANT
    account.active = True
    _set_account_password(account, setup.password)
    register_dev_participant_user(
        participant_id=participant.id,
        email=participant.email,
        display_name=participant.display_name,
    )
    PARTICIPANTS[participant.id] = participant
    USER_ACCOUNTS[account.id] = account
    if persistence_enabled():
        async with async_session_for_current_database() as session:
            await _async_merge_rows(
                session,
                [
                    _participant_row(participant),
                    _user_account_row(account),
                ],
            )
            await session.commit()
    current = CurrentUser(
        id=account.id,
        email=account.email,
        display_name=account.display_name,
        role=account.role,
    )

    return AuthTokenResponse(
        access_token=create_access_token(current),
        token_type="bearer",
        expires_in_seconds=JWT_ACCESS_TOKEN_SECONDS,
        user=current,
    )


@app.get(
    "/api/participants/me/membership",
    response_model=ParticipantMembershipRead,
)
async def participant_membership(
    user: CurrentUser = Depends(require_roles(Role.PARTICIPANT)),
) -> ParticipantMembershipRead:
    if persistence_enabled():
        async with async_session_for_current_database() as session:
            participant = await _async_verified_participant(session, user)
            missing_required_document_keys = (
                await _async_missing_required_document_keys(session, participant)
            )
            return _participant_membership_read(
                participant,
                missing_required_document_keys=missing_required_document_keys,
            )

    participant = _verified_participant(user)

    return _participant_membership_read(participant)


@app.get(
    "/api/participants/me/identity-checkpoint",
    response_model=ParticipantIdentityCheckpointRead,
)
async def participant_identity_checkpoint(
    action: str,
    user: CurrentUser = Depends(require_roles(Role.PARTICIPANT)),
) -> ParticipantIdentityCheckpointRead:
    if action != "membership_activation":
        raise HTTPException(status_code=400, detail="Unsupported checkpoint action")

    if persistence_enabled():
        async with async_session_for_current_database() as session:
            participant = await _async_verified_participant(session, user)
            checkpoint = await _async_identity_checkpoint(session, participant)
            return ParticipantIdentityCheckpointRead(
                action=action,
                **checkpoint.model_dump(),
            )

    participant = PARTICIPANTS.get(user.id)
    if participant is None:
        raise HTTPException(status_code=404, detail="Participant not found")

    checkpoint = _identity_checkpoint(participant)

    return ParticipantIdentityCheckpointRead(
        action=action,
        **checkpoint.model_dump(),
    )


@app.get(
    "/api/participants/{participant_id}/membership",
    response_model=ParticipantMembershipRead,
)
async def participant_membership_by_id(
    participant_id: str,
    user: CurrentUser = Depends(current_user),
) -> ParticipantMembershipRead:
    if user.role == Role.PARTICIPANT:
        if persistence_enabled():
            async with async_session_for_current_database() as session:
                participant = await _async_verified_participant(session, user)
                if participant.id != participant_id:
                    raise HTTPException(
                        status_code=403,
                        detail="Participant membership is not accessible",
                    )
                return _participant_membership_read(participant)

        participant = _verified_participant(user)
        if participant.id != participant_id:
            raise HTTPException(
                status_code=403,
                detail="Participant membership is not accessible",
            )
        return _participant_membership_read(participant)

    if user.role not in {Role.LEG_ADMIN, Role.PLATFORM_ADMIN}:
        raise HTTPException(
            status_code=403,
            detail="Role is not allowed",
        )

    if persistence_enabled():
        async with async_session_for_current_database() as session:
            participant_row = await session.get(PortalParticipant, participant_id)
            if participant_row is None:
                raise HTTPException(status_code=404, detail="Participant not found")
            return _participant_membership_read(_participant_from_row(participant_row))

    participant = PARTICIPANTS.get(participant_id)
    if participant is None:
        raise HTTPException(status_code=404, detail="Participant not found")

    return _participant_membership_read(participant)
