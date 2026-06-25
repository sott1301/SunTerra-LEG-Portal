from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import os
import secrets
import sys
from hashlib import pbkdf2_hmac
from pathlib import Path
from uuid import uuid4

from sqlmodel import Session, select
from sqlalchemy.exc import IntegrityError


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sunterra_leg_portal.auth import Role  # noqa: E402
from sunterra_leg_portal.db import (  # noqa: E402
    PortalCommunicationEvent,
    PortalUserAccount,
    engine_for_url,
)


BOOTSTRAP_ROLES = {Role.PLATFORM_ADMIN.value, Role.LEG_ADMIN.value}
BOOTSTRAP_AUDIT_EVENT_ID = "bootstrap-admin-created"


def password_hash(password: str, salt: str) -> str:
    return pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("ascii"),
        120_000,
    ).hex()


def create_bootstrap_admin(
    *,
    database_url: str,
    email: str,
    display_name: str,
    password: str,
    role: str,
) -> dict[str, str]:
    if role not in BOOTSTRAP_ROLES:
        raise ValueError("Bootstrap role must be platform_admin or leg_admin")

    engine = engine_for_url(database_url)
    with Session(engine) as session:
        internal_admin = session.exec(
            select(PortalUserAccount)
            .where(PortalUserAccount.role.in_(sorted(BOOTSTRAP_ROLES)))
            .limit(1),
        ).first()
        if internal_admin is not None:
            raise ValueError("Bootstrap admin already exists")

        existing = session.exec(
            select(PortalUserAccount)
            .where(PortalUserAccount.email == email)
            .limit(1),
        ).first()
        if existing is not None:
            raise ValueError("User account already exists")

        salt = secrets.token_hex(16)
        account = PortalUserAccount(
            id=uuid4().hex,
            email=email,
            display_name=display_name,
            role=role,
            active=True,
            password_hash=password_hash(password, salt),
            password_salt=salt,
        )
        audit_event = PortalCommunicationEvent(
            id=BOOTSTRAP_AUDIT_EVENT_ID,
            channel="admin_bootstrap",
            event_type="bootstrap_admin_created",
            recipient_email=email,
            status="created",
            created_at=datetime.now(UTC).isoformat(),
        )
        payload = {
            "status": "created",
            "id": account.id,
            "email": account.email,
            "display_name": account.display_name,
            "role": account.role,
            "audit_event_id": audit_event.id,
            "created_at": audit_event.created_at,
        }
        session.add(account)
        session.add(audit_event)
        try:
            session.commit()
        except IntegrityError as error:
            session.rollback()
            raise ValueError("Bootstrap admin already exists") from error

    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bootstrap the first production SunTerra LEG admin account.",
    )
    parser.add_argument("--database-url", default=os.environ.get("SUNTERRA_DATABASE_URL"))
    parser.add_argument("--email", required=True)
    parser.add_argument("--display-name", required=True)
    parser.add_argument("--role", choices=sorted(BOOTSTRAP_ROLES), required=True)
    args = parser.parse_args()

    if not args.database_url:
        print("SUNTERRA_DATABASE_URL or --database-url is required", file=sys.stderr)
        return 2
    password = os.environ.get("SUNTERRA_BOOTSTRAP_ADMIN_PASSWORD")
    if not password:
        print("SUNTERRA_BOOTSTRAP_ADMIN_PASSWORD is required", file=sys.stderr)
        return 2

    try:
        payload = create_bootstrap_admin(
            database_url=args.database_url,
            email=args.email,
            display_name=args.display_name,
            password=password,
            role=args.role,
        )
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 1

    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
