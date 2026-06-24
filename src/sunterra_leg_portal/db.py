from __future__ import annotations

import os
from contextlib import asynccontextmanager, contextmanager
from functools import lru_cache
from typing import AsyncIterator, Iterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import Field, Session, SQLModel, create_engine


metadata = SQLModel.metadata


class PortalStateSnapshot(SQLModel, table=True):
    __tablename__ = "portal_state_snapshots"

    id: str = Field(primary_key=True)
    payload_json: str


class PortalParticipant(SQLModel, table=True):
    __tablename__ = "portal_participants"

    id: str = Field(primary_key=True)
    email: str
    display_name: str
    leg_id: str
    email_verified: bool
    phone_number: str | None = None
    preferred_contact_channel: str = "email"


class PortalParticipantInvitation(SQLModel, table=True):
    __tablename__ = "portal_participant_invitations"

    token: str = Field(primary_key=True)
    email: str
    display_name: str
    leg_id: str
    status: str
    participant_id: str | None = None
    source: str = "admin_invitation"


class PortalIdentityVerification(SQLModel, table=True):
    __tablename__ = "portal_identity_verifications"

    participant_id: str = Field(primary_key=True)
    email: str
    display_name: str
    leg_id: str
    source: str
    required_level: str
    current_level: str
    satisfied: bool
    verified_at: str | None = None


class PortalDocumentVersion(SQLModel, table=True):
    __tablename__ = "portal_document_versions"

    id: str = Field(primary_key=True)
    document_key: str
    title: str
    version: str
    document_hash: str
    context: str
    published_at: str
    content: str


class PortalConsentEvidence(SQLModel, table=True):
    __tablename__ = "portal_consent_evidence"

    participant_id: str = Field(primary_key=True)
    document_version_id: str = Field(primary_key=True)
    accepted_at: str = Field(primary_key=True)
    document_key: str
    version: str
    document_hash: str
    context: str


class PortalMutationRequest(SQLModel, table=True):
    __tablename__ = "portal_mutation_requests"

    id: str = Field(primary_key=True)
    participant_id: str
    leg_id: str
    status: str
    submitted_at: str
    payload_json: str


class PortalParticipantAuditEvent(SQLModel, table=True):
    __tablename__ = "portal_participant_audit_events"

    participant_id: str = Field(primary_key=True)
    id: str = Field(primary_key=True)
    created_at: str
    payload_json: str


class PortalMutationPackage(SQLModel, table=True):
    __tablename__ = "portal_mutation_packages"

    package_id: str = Field(primary_key=True)
    leg_id: str
    quarter: str
    generated_at: str
    payload_json: str


class PortalFileEvidence(SQLModel, table=True):
    __tablename__ = "portal_file_evidence"

    id: str = Field(primary_key=True)
    mutation_request_id: str
    participant_id: str
    created_at: str
    payload_json: str


class PortalMutationPackageMetadata(SQLModel, table=True):
    __tablename__ = "portal_mutation_package_metadata"

    package_id: str = Field(primary_key=True)
    current_status: str
    payload_json: str


class PortalPackagedMutationRequest(SQLModel, table=True):
    __tablename__ = "portal_packaged_mutation_requests"

    mutation_request_id: str = Field(primary_key=True)
    package_id: str


class PortalUserAccount(SQLModel, table=True):
    __tablename__ = "portal_user_accounts"

    id: str = Field(primary_key=True)
    email: str
    display_name: str
    role: str
    active: bool
    organization: str | None = None
    password_hash: str | None = None
    password_salt: str | None = None


class PortalCommunicationEvent(SQLModel, table=True):
    __tablename__ = "portal_communication_events"

    id: str = Field(primary_key=True)
    channel: str
    event_type: str
    recipient_email: str
    status: str
    created_at: str


def database_url() -> str | None:
    return os.environ.get("SUNTERRA_DATABASE_URL")


def persistence_enabled() -> bool:
    return (
        database_url() is not None
        or os.environ.get("SUNTERRA_ASYNC_DATABASE_URL") is not None
    )


def async_database_url_for(url: str) -> str:
    if url.startswith(("postgresql+asyncpg://", "sqlite+aiosqlite://")):
        return url
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url.removeprefix("postgresql://")
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url.removeprefix("postgres://")
    if url.startswith("postgresql+"):
        _scheme, rest = url.split("://", maxsplit=1)
        return f"postgresql+asyncpg://{rest}"
    if url.startswith("sqlite+pysqlite://"):
        return "sqlite+aiosqlite://" + url.removeprefix("sqlite+pysqlite://")
    if url.startswith("sqlite://"):
        return "sqlite+aiosqlite://" + url.removeprefix("sqlite://")
    return url


def async_database_url() -> str | None:
    configured_url = os.environ.get("SUNTERRA_ASYNC_DATABASE_URL")
    if configured_url:
        return configured_url

    url = database_url()
    if url is None:
        return None

    return async_database_url_for(url)


@lru_cache(maxsize=8)
def engine_for_url(url: str):
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args)


@lru_cache(maxsize=8)
def async_engine_for_url(url: str):
    return create_async_engine(url, pool_pre_ping=True)


@lru_cache(maxsize=8)
def async_sessionmaker_for_url(url: str) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        async_engine_for_url(url),
        expire_on_commit=False,
    )


def get_session() -> Iterator[Session]:
    url = database_url()
    if url is None:
        raise RuntimeError("SUNTERRA_DATABASE_URL is not configured")

    with Session(engine_for_url(url)) as session:
        yield session


@asynccontextmanager
async def async_session_for_current_database() -> AsyncIterator[AsyncSession]:
    url = async_database_url()
    if url is None:
        raise RuntimeError("SUNTERRA_DATABASE_URL is not configured")

    session_factory = async_sessionmaker_for_url(url)
    async with session_factory() as session:
        yield session


async def async_database_runtime_check() -> int:
    async with async_session_for_current_database() as session:
        result = await session.execute(text("select 1"))
        return int(result.scalar_one())


@contextmanager
def session_for_current_database() -> Iterator[Session]:
    url = database_url()
    if url is None:
        raise RuntimeError("SUNTERRA_DATABASE_URL is not configured")

    with Session(engine_for_url(url)) as session:
        yield session


def reset_engine_cache_for_tests() -> None:
    engine_for_url.cache_clear()
    async_engine_for_url.cache_clear()
    async_sessionmaker_for_url.cache_clear()
