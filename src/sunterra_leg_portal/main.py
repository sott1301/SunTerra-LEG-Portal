from datetime import UTC, datetime
from hashlib import sha256
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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


class ParticipantInvitationRead(BaseModel):
    token: str
    email: str
    display_name: str
    leg_id: str
    status: str


class ParticipantInvitationRecord(ParticipantInvitationRead):
    participant_id: str | None = None


class ParticipantRecord(BaseModel):
    id: str
    email: str
    display_name: str
    leg_id: str
    email_verified: bool


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


INVITATIONS: dict[str, ParticipantInvitationRecord] = {}
PARTICIPANTS: dict[str, ParticipantRecord] = {}
DOCUMENT_VERSIONS: dict[str, DocumentVersionRecord] = {}
CONSENT_EVIDENCE: dict[str, list[ConsentEvidenceRead]] = {}


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

    return ParticipantInvitationRead(
        token=record.token,
        email=record.email,
        display_name=record.display_name,
        leg_id=record.leg_id,
        status=record.status,
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
    register_dev_participant_user(
        participant_id=participant.id,
        email=participant.email,
        display_name=participant.display_name,
    )

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
