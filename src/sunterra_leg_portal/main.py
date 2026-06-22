import csv
import json
from base64 import b64decode
from datetime import UTC, date, datetime, timedelta
from hashlib import sha256
from io import StringIO
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

from sunterra_leg_portal.auth import (
    CurrentUser,
    Role,
    current_user,
    register_dev_participant_user,
    require_roles,
)
from sunterra_leg_portal.config import production_lifespan


LOCAL_DEV_ORIGINS = [
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "http://localhost:5173",
    "http://localhost:5174",
]
BASADINGEN_LEG_ID = "basadingen"
BASADINGEN_LEG_NAME = "SunTerra LEG Basadingen"
PARTICIPANT_BILLING_NOTICE = "Abrechnung und Inkasso bleiben bei Gemeinde/EW."


class HealthStatus(BaseModel):
    status: str
    service: str
    version: str


class ParticipantList(BaseModel):
    participants: list[dict[str, str]]


class ParticipantInvitationCreate(BaseModel):
    email: str
    display_name: str


class SelfServiceOnboardingCreate(BaseModel):
    email: str
    display_name: str


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
    dev_email_verification_token: str


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
    billing_notice: str


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
    requested_quarter: str
    submitted_on: date | None = None
    new_address: AddressRead


class MutationRequestRead(BaseModel):
    id: str
    participant_id: str
    leg_id: str
    mutation_type: str
    mode: str
    status: str
    quarter: str
    quarter_end: str
    participant_deadline: str
    effective_date: str
    submitted_at: str
    new_address: AddressRead


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
    new_address: AddressRead


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


INVITATIONS: dict[str, ParticipantInvitationRecord] = {}
COMMUNICATION_EVENTS: list[CommunicationEventRead] = []
PARTICIPANTS: dict[str, ParticipantRecord] = {}
IDENTITY_VERIFICATIONS: dict[str, IdentityVerificationRead] = {}
DOCUMENT_VERSIONS: dict[str, DocumentVersionRecord] = {}
CONSENT_EVIDENCE: dict[str, list[ConsentEvidenceRead]] = {}
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
SUPPORTED_PARTNER_PACKAGE_STATUSES = {
    "received",
    "in_review",
    "processed",
    "question",
    "technically_not_possible",
}


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


def _current_document_version(document_key: str) -> DocumentVersionRecord | None:
    for document in reversed(DOCUMENT_VERSIONS.values()):
        if document.document_key == document_key:
            return document

    return None


def _verified_participant(user: CurrentUser) -> ParticipantRecord:
    participant = PARTICIPANTS.get(user.id)
    if participant is None or not participant.email_verified:
        raise HTTPException(status_code=403, detail="Email verification required")

    return participant


def _identity_checkpoint(participant: ParticipantRecord) -> IdentityCheckpointRead:
    current_level = "email_verified" if participant.email_verified else "unverified"

    return IdentityCheckpointRead(
        required_level="email_verified",
        current_level=current_level,
        satisfied=participant.email_verified,
    )


def _record_identity_verification(
    participant: ParticipantRecord,
    *,
    source: str,
    verified_at: str | None = None,
) -> IdentityVerificationRead:
    checkpoint = _identity_checkpoint(participant)
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


def _queue_email_event(event_type: str, recipient_email: str) -> CommunicationEventRead:
    event = CommunicationEventRead(
        id=uuid4().hex,
        channel="email",
        event_type=event_type,
        recipient_email=recipient_email,
        status="queued",
        created_at=datetime.now(UTC).isoformat(),
    )
    COMMUNICATION_EVENTS.append(event)

    return event


def _participant_membership_read(
    participant: ParticipantRecord,
) -> ParticipantMembershipRead:
    membership_status = (
        "active" if participant.email_verified else "pending_email_verification"
    )

    return ParticipantMembershipRead(
        participant_id=participant.id,
        display_name=participant.display_name,
        email=participant.email,
        leg_id=participant.leg_id,
        leg_name=BASADINGEN_LEG_NAME,
        membership_status=membership_status,
        billing_notice=PARTICIPANT_BILLING_NOTICE,
    )


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


def _admin_mutation_request_read(
    mutation_request: MutationRequestRecord,
) -> AdminMutationRequestRead:
    participant = PARTICIPANTS[mutation_request.participant_id]
    return AdminMutationRequestRead(
        **mutation_request.model_dump(),
        participant=AdminMutationParticipantRead(
            participant_id=participant.id,
            display_name=participant.display_name,
            email=participant.email,
        ),
    )


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
    MUTATION_PACKAGE_METADATA[package.package_id] = metadata

    return metadata


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


def _partner_mutation_package_detail(
    package: MutationPackageRead,
) -> PartnerMutationPackageDetail:
    metadata = _mutation_package_metadata(package)
    return PartnerMutationPackageDetail(
        **_partner_mutation_package_summary(package).model_dump(),
        records=package.records,
        status_history=_partner_status_read(metadata).status_history,
    )


def _mutation_package_hash(package_data: dict) -> str:
    canonical = json.dumps(
        package_data,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(canonical.encode("utf-8")).hexdigest()


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
                record.new_address.street,
                record.new_address.postal_code,
                record.new_address.city,
                record.new_address.country,
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
    lines.extend(
        (
            f"record {index}: {record.mutation_request_id} {record.participant_id} "
            f"{record.mutation_type} {record.mode} {record.effective_date} "
            f"{record.new_address.street}, {record.new_address.postal_code} "
            f"{record.new_address.city}, {record.new_address.country}"
        )
        for index, record in enumerate(package.records, start=1)
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
    allow_origins=LOCAL_DEV_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthStatus)
def health() -> HealthStatus:
    return HealthStatus(
        status="ok",
        service="sunterra-leg-portal",
        version="0.1.0",
    )


@app.get("/api/me", response_model=CurrentUser)
def me(user: CurrentUser = Depends(current_user)) -> CurrentUser:
    return user


@app.get("/api/admin/participants", response_model=ParticipantList)
def admin_participants(
    _user: CurrentUser = Depends(require_roles(Role.LEG_ADMIN, Role.PLATFORM_ADMIN)),
) -> ParticipantList:
    return ParticipantList(participants=[])


@app.get(
    "/api/admin/communication-events",
    response_model=list[CommunicationEventRead],
)
def admin_communication_events(
    recipient_email: str | None = None,
    event_type: str | None = None,
    _user: CurrentUser = Depends(require_roles(Role.LEG_ADMIN, Role.PLATFORM_ADMIN)),
) -> list[CommunicationEventRead]:
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


@app.post(
    "/api/admin/participant-invitations",
    response_model=ParticipantInvitationRead,
    status_code=201,
)
def create_participant_invitation(
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
    _queue_email_event("participant_invitation", record.email)

    return ParticipantInvitationRead(
        token=record.token,
        email=record.email,
        display_name=record.display_name,
        leg_id=record.leg_id,
        status=record.status,
    )


@app.post(
    "/api/auth/self-service-onboarding-requests",
    response_model=SelfServiceOnboardingResponse,
    status_code=201,
)
def create_self_service_onboarding_request(
    onboarding_request: SelfServiceOnboardingCreate,
) -> SelfServiceOnboardingResponse:
    participant_id = uuid4().hex
    verification_token = uuid4().hex
    participant = ParticipantRecord(
        id=participant_id,
        email=onboarding_request.email,
        display_name=onboarding_request.display_name,
        leg_id=BASADINGEN_LEG_ID,
        email_verified=False,
    )
    PARTICIPANTS[participant.id] = participant
    INVITATIONS[verification_token] = ParticipantInvitationRecord(
        token=verification_token,
        email=participant.email,
        display_name=participant.display_name,
        leg_id=participant.leg_id,
        status="pending_email_verification",
        participant_id=participant.id,
        source="self_service_onboarding",
    )
    register_dev_participant_user(
        participant_id=participant.id,
        email=participant.email,
        display_name=participant.display_name,
    )
    _record_identity_verification(participant, source="self_service_onboarding")
    _queue_email_event("email_verification", participant.email)

    return SelfServiceOnboardingResponse(
        access_token=f"dev:participant:{participant.id}",
        token_type="bearer",
        participant_id=participant.id,
        participant_status="pending_email_verification",
        identity_checkpoint=_identity_checkpoint(participant),
        dev_email_verification_token=verification_token,
    )


@app.post(
    "/api/admin/document-versions",
    response_model=DocumentVersionRead,
    status_code=201,
)
def publish_document_version(
    document: DocumentVersionCreate,
    _user: CurrentUser = Depends(require_roles(Role.PLATFORM_ADMIN)),
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
    DOCUMENT_VERSIONS[record.id] = record

    return DocumentVersionRead(**record.model_dump())


@app.get(
    "/api/admin/mutation-requests",
    response_model=list[AdminMutationRequestRead],
)
def admin_mutation_requests(
    status: str | None = None,
    _user: CurrentUser = Depends(require_roles(Role.LEG_ADMIN, Role.PLATFORM_ADMIN)),
) -> list[AdminMutationRequestRead]:
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
def admin_participant_identity_verification(
    participant_id: str,
    _user: CurrentUser = Depends(require_roles(Role.LEG_ADMIN, Role.PLATFORM_ADMIN)),
) -> IdentityVerificationRead:
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
    "/api/admin/mutation-requests/{mutation_request_id}/review-decision",
    response_model=AdminMutationRequestRead,
)
def review_mutation_request(
    mutation_request_id: str,
    decision: MutationReviewDecision,
    user: CurrentUser = Depends(require_roles(Role.LEG_ADMIN)),
) -> AdminMutationRequestRead:
    if decision.decision not in {"approved", "rejected"}:
        raise HTTPException(status_code=400, detail="Unsupported review decision")

    mutation_request = _find_mutation_request(mutation_request_id)
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

    return _admin_mutation_request_read(mutation_request)


@app.post(
    "/api/admin/mutation-requests/{mutation_request_id}/file-evidence",
    response_model=FileEvidenceMetadataRead,
    status_code=201,
)
def attach_mutation_request_file_evidence(
    mutation_request_id: str,
    evidence: FileEvidenceCreate,
    _user: CurrentUser = Depends(require_roles(Role.LEG_ADMIN)),
) -> FileEvidenceMetadataRead:
    mutation_request = _find_mutation_request(mutation_request_id)
    evidence_config = FILE_EVIDENCE_PURPOSES.get(
        (evidence.document_type, evidence.purpose),
    )
    if evidence_config is None:
        raise HTTPException(
            status_code=400,
            detail="File evidence document type and purpose are not configured",
        )

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
def file_evidence_metadata(
    mutation_request_id: str,
    file_evidence_id: str,
    user: CurrentUser = Depends(current_user),
) -> FileEvidenceMetadataRead:
    evidence = _find_file_evidence(mutation_request_id, file_evidence_id)
    _authorize_file_evidence_access(evidence, user)

    return FileEvidenceMetadataRead(**evidence.model_dump())


@app.get(
    "/api/mutation-requests/{mutation_request_id}/file-evidence/{file_evidence_id}/content",
    response_model=FileEvidenceContentRead,
)
def file_evidence_content(
    mutation_request_id: str,
    file_evidence_id: str,
    user: CurrentUser = Depends(current_user),
) -> FileEvidenceContentRead:
    evidence = _find_file_evidence(mutation_request_id, file_evidence_id)
    _authorize_file_evidence_access(evidence, user)

    return FileEvidenceContentRead(**evidence.model_dump())


@app.post(
    "/api/admin/mutation-packages",
    response_model=MutationPackageRead,
    status_code=201,
)
def create_mutation_package(
    package: MutationPackageCreate,
    user: CurrentUser = Depends(require_roles(Role.LEG_ADMIN)),
) -> MutationPackageRead:
    _participant_deadline, _quarter_end, effective_date = (
        _regular_address_quarter_dates(package.quarter)
    )
    approved_requests = sorted(
        [
            mutation_request
            for participant_requests in MUTATION_REQUESTS.values()
            for mutation_request in participant_requests
            if mutation_request.leg_id == BASADINGEN_LEG_ID
            and mutation_request.status == "approved"
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
            detail="No approved un-packaged mutation requests for quarter",
        )

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
        "quarter": package.quarter,
        "effective_date": effective_date,
        "records": [record.model_dump() for record in records],
        "generated_at": generated_at,
        "status_history": [event.model_dump() for event in status_history],
    }
    mutation_package = MutationPackageRead(
        **package_data,
        hash=_mutation_package_hash(package_data),
    )
    MUTATION_PACKAGES[package_id] = mutation_package
    PACKAGED_MUTATION_REQUEST_IDS.update(
        mutation_request.id for mutation_request in approved_requests
    )

    return mutation_package


@app.get(
    "/api/partner/mutation-packages",
    response_model=list[PartnerMutationPackageSummary],
)
def partner_mutation_packages(
    _user: CurrentUser = Depends(require_roles(Role.PARTNER_ADMIN)),
) -> list[PartnerMutationPackageSummary]:
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
def partner_mutation_package_detail(
    package_id: str,
    _user: CurrentUser = Depends(require_roles(Role.PARTNER_ADMIN)),
) -> PartnerMutationPackageDetail:
    package = _find_mutation_package(package_id)

    return _partner_mutation_package_detail(package)


@app.post(
    "/api/partner/mutation-packages/{package_id}/status",
    response_model=PartnerMutationPackageStatusRead,
)
def update_partner_mutation_package_status(
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
def admin_mutation_package_metadata(
    package_id: str,
    _user: CurrentUser = Depends(require_roles(Role.LEG_ADMIN)),
) -> AdminMutationPackageMetadataRead:
    package = _find_mutation_package(package_id)

    return _mutation_package_metadata(package)


@app.get(
    "/api/admin/mutation-packages/{package_id}/json",
    response_model=MutationPackageRead,
)
def mutation_package_json_artifact(
    package_id: str,
    _user: CurrentUser = Depends(require_roles(Role.LEG_ADMIN)),
) -> MutationPackageRead:
    return _find_mutation_package(package_id)


@app.get("/api/admin/mutation-packages/{package_id}/csv")
def mutation_package_csv_artifact(
    package_id: str,
    _user: CurrentUser = Depends(require_roles(Role.LEG_ADMIN)),
) -> Response:
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
def mutation_package_pdf_artifact(
    package_id: str,
    _user: CurrentUser = Depends(require_roles(Role.LEG_ADMIN)),
) -> Response:
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
def current_document_version(
    document_key: str,
    user: CurrentUser = Depends(current_user),
) -> CurrentDocumentRead:
    if user.role == Role.PARTICIPANT:
        _verified_participant(user)

    document = _current_document_version(document_key)
    if document is None:
        raise HTTPException(status_code=404, detail="Document version not found")

    return CurrentDocumentRead(**document.model_dump())


@app.post(
    "/api/participants/me/consent-evidence",
    response_model=ConsentEvidenceRead,
    status_code=201,
)
def record_consent_evidence(
    consent: ConsentEvidenceCreate,
    user: CurrentUser = Depends(require_roles(Role.PARTICIPANT)),
) -> ConsentEvidenceRead:
    participant = _verified_participant(user)
    if not consent.accepted:
        raise HTTPException(status_code=400, detail="Consent must be accepted")

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
def participant_consent_history(
    user: CurrentUser = Depends(require_roles(Role.PARTICIPANT)),
) -> list[ConsentEvidenceRead]:
    participant = _verified_participant(user)

    return CONSENT_EVIDENCE.get(participant.id, [])


@app.get(
    "/api/participants/me/contact-channels",
    response_model=ParticipantContactChannelsRead,
)
def participant_contact_channels(
    user: CurrentUser = Depends(require_roles(Role.PARTICIPANT)),
) -> ParticipantContactChannelsRead:
    participant = _verified_participant(user)

    return _participant_contact_channels_read(participant)


@app.patch(
    "/api/participants/me/contact-channels",
    response_model=ParticipantContactChannelsRead,
)
def update_participant_contact_channels(
    contact_channels: ParticipantContactChannelsUpdate,
    user: CurrentUser = Depends(require_roles(Role.PARTICIPANT)),
) -> ParticipantContactChannelsRead:
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
def create_participant_mutation_request(
    mutation: MutationRequestCreate,
    user: CurrentUser = Depends(require_roles(Role.PARTICIPANT)),
) -> MutationRequestRead:
    participant = _verified_participant(user)
    if mutation.mutation_type != "address" or mutation.mode != "regular":
        raise HTTPException(
            status_code=400,
            detail="Only regular address mutations are supported",
        )

    participant_deadline, quarter_end, effective_date = (
        _regular_address_quarter_dates(mutation.requested_quarter)
    )
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

    mutation_request = MutationRequestRecord(
        id=uuid4().hex,
        participant_id=participant.id,
        leg_id=participant.leg_id,
        mutation_type=mutation.mutation_type,
        mode=mutation.mode,
        status="submitted",
        quarter=mutation.requested_quarter,
        quarter_end=quarter_end,
        participant_deadline=participant_deadline,
        effective_date=effective_date,
        submitted_at=datetime.now(UTC).isoformat(),
        new_address=mutation.new_address,
    )
    MUTATION_REQUESTS.setdefault(participant.id, []).append(mutation_request)

    return mutation_request


@app.get(
    "/api/participants/me/mutation-requests",
    response_model=list[ParticipantMutationRequestRead],
)
def participant_mutation_requests(
    user: CurrentUser = Depends(require_roles(Role.PARTICIPANT)),
) -> list[ParticipantMutationRequestRead]:
    participant = _verified_participant(user)

    return MUTATION_REQUESTS.get(participant.id, [])


@app.post(
    "/api/auth/invitations/{token}/accept",
    response_model=InvitationAcceptResponse,
)
def accept_participant_invitation(token: str) -> InvitationAcceptResponse:
    invitation = INVITATIONS.get(token)
    if invitation is None:
        raise HTTPException(status_code=404, detail="Invitation not found")

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
    PARTICIPANTS[participant_id] = participant
    _record_identity_verification(participant, source=invitation.source)
    register_dev_participant_user(
        participant_id=participant.id,
        email=participant.email,
        display_name=participant.display_name,
    )
    _queue_email_event("email_verification", participant.email)

    return InvitationAcceptResponse(
        access_token=f"dev:participant:{participant_id}",
        token_type="bearer",
        participant_id=participant_id,
        email_verification_required=True,
    )


@app.post(
    "/api/auth/email-verifications/{token}/verify",
    response_model=EmailVerificationResponse,
)
def verify_participant_email(token: str) -> EmailVerificationResponse:
    invitation = INVITATIONS.get(token)
    if invitation is None or invitation.participant_id is None:
        raise HTTPException(status_code=404, detail="Email verification not found")

    participant = PARTICIPANTS[invitation.participant_id]
    participant.email_verified = True
    invitation.status = "active"
    _record_identity_verification(
        participant,
        source=invitation.source,
        verified_at=datetime.now(UTC).isoformat(),
    )
    register_dev_participant_user(
        participant_id=participant.id,
        email=participant.email,
        display_name=participant.display_name,
    )

    return EmailVerificationResponse(
        participant_id=participant.id,
        email_verified=participant.email_verified,
    )


@app.get(
    "/api/participants/me/membership",
    response_model=ParticipantMembershipRead,
)
def participant_membership(
    user: CurrentUser = Depends(require_roles(Role.PARTICIPANT)),
) -> ParticipantMembershipRead:
    participant = PARTICIPANTS.get(user.id)
    if participant is None:
        raise HTTPException(status_code=404, detail="Participant not found")
    if not participant.email_verified:
        raise HTTPException(status_code=403, detail="Email verification required")

    return _participant_membership_read(participant)


@app.get(
    "/api/participants/me/identity-checkpoint",
    response_model=ParticipantIdentityCheckpointRead,
)
def participant_identity_checkpoint(
    action: str,
    user: CurrentUser = Depends(require_roles(Role.PARTICIPANT)),
) -> ParticipantIdentityCheckpointRead:
    participant = PARTICIPANTS.get(user.id)
    if participant is None:
        raise HTTPException(status_code=404, detail="Participant not found")
    if action != "membership_activation":
        raise HTTPException(status_code=400, detail="Unsupported checkpoint action")

    checkpoint = _identity_checkpoint(participant)

    return ParticipantIdentityCheckpointRead(
        action=action,
        **checkpoint.model_dump(),
    )


@app.get(
    "/api/participants/{participant_id}/membership",
    response_model=ParticipantMembershipRead,
)
def participant_membership_by_id(
    participant_id: str,
    user: CurrentUser = Depends(current_user),
) -> ParticipantMembershipRead:
    if user.role == Role.PARTICIPANT and user.id != participant_id:
        raise HTTPException(
            status_code=403,
            detail="Participant membership is not accessible",
        )
    if user.role not in {Role.PARTICIPANT, Role.LEG_ADMIN, Role.PLATFORM_ADMIN}:
        raise HTTPException(status_code=403, detail="Role is not allowed")

    participant = PARTICIPANTS.get(participant_id)
    if participant is None:
        raise HTTPException(status_code=404, detail="Participant not found")
    if user.role == Role.PARTICIPANT and not participant.email_verified:
        raise HTTPException(status_code=403, detail="Email verification required")

    return _participant_membership_read(participant)
