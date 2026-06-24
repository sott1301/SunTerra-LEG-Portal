from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from enum import StrEnum
import base64
import hmac
import json
import os
from hashlib import sha256

from fastapi import Depends, Header, HTTPException, status
from pydantic import BaseModel


class Role(StrEnum):
    PARTICIPANT = "participant"
    LEG_ADMIN = "leg_admin"
    PARTNER_ADMIN = "partner_admin"
    PLATFORM_ADMIN = "platform_admin"


class CurrentUser(BaseModel):
    id: str
    email: str
    display_name: str
    role: Role


DEV_USERS: dict[Role, CurrentUser] = {
    Role.PARTICIPANT: CurrentUser(
        id="dev-participant",
        email="participant@example.test",
        display_name="Teilnehmer Demo",
        role=Role.PARTICIPANT,
    ),
    Role.LEG_ADMIN: CurrentUser(
        id="dev-leg-admin",
        email="leg-admin@example.test",
        display_name="LEG Admin Demo",
        role=Role.LEG_ADMIN,
    ),
    Role.PARTNER_ADMIN: CurrentUser(
        id="dev-partner-admin",
        email="partner-admin@example.test",
        display_name="Partner Admin Demo",
        role=Role.PARTNER_ADMIN,
    ),
    Role.PLATFORM_ADMIN: CurrentUser(
        id="dev-platform-admin",
        email="platform-admin@example.test",
        display_name="Plattform Admin Demo",
        role=Role.PLATFORM_ADMIN,
    ),
}
DEV_PARTICIPANT_USERS: dict[str, CurrentUser] = {}
JWT_ACCESS_TOKEN_SECONDS = 8 * 60 * 60
_jwt_user_resolver: Callable[[str], CurrentUser | None] | None = None


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _jwt_secret() -> str:
    return os.environ.get("SUNTERRA_SECRET_KEY", "local-development-secret")


def _jwt_signature(signing_input: str) -> str:
    digest = hmac.new(
        _jwt_secret().encode("utf-8"),
        signing_input.encode("ascii"),
        sha256,
    ).digest()
    return _base64url_encode(digest)


def set_jwt_user_resolver(
    resolver: Callable[[str], CurrentUser | None],
) -> None:
    global _jwt_user_resolver

    _jwt_user_resolver = resolver


def create_access_token(user: CurrentUser) -> str:
    now = datetime.now(UTC)
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role.value,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=JWT_ACCESS_TOKEN_SECONDS)).timestamp()),
    }
    header_part = _base64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_part = _base64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_part}.{payload_part}"

    return f"{signing_input}.{_jwt_signature(signing_input)}"


def _current_user_from_jwt(token: str) -> CurrentUser:
    try:
        header_part, payload_part, signature = token.split(".", maxsplit=2)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token",
        ) from exc

    signing_input = f"{header_part}.{payload_part}"
    if not hmac.compare_digest(signature, _jwt_signature(signing_input)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token",
        )

    try:
        payload = json.loads(_base64url_decode(payload_part))
        expires_at = int(payload["exp"])
        user_id = str(payload["sub"])
        role = Role(str(payload["role"]))
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token",
        ) from exc

    if expires_at < int(datetime.now(UTC).timestamp()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token expired",
        )

    if _jwt_user_resolver is not None:
        user = _jwt_user_resolver(user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unknown or inactive user",
            )

        return user

    return CurrentUser(
        id=user_id,
        email=str(payload.get("email", "")),
        display_name=str(payload.get("display_name", "")),
        role=role,
    )


def register_dev_participant_user(
    *,
    participant_id: str,
    email: str,
    display_name: str,
) -> None:
    DEV_PARTICIPANT_USERS[participant_id] = CurrentUser(
        id=participant_id,
        email=email,
        display_name=display_name,
        role=Role.PARTICIPANT,
    )


def current_user(authorization: str | None = Header(default=None)) -> CurrentUser:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    token = authorization.removeprefix("Bearer ")
    if not token.startswith("dev:"):
        return _current_user_from_jwt(token)

    role_name = token.removeprefix("dev:")
    participant_prefix = f"{Role.PARTICIPANT.value}:"
    if role_name.startswith(participant_prefix):
        participant_id = role_name.removeprefix(participant_prefix)
        user = DEV_PARTICIPANT_USERS.get(participant_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unknown development user",
            )

        return user

    try:
        role = Role(role_name)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unknown development user",
        ) from exc

    return DEV_USERS[role]


def require_roles(*allowed_roles: Role) -> Callable[[CurrentUser], CurrentUser]:
    def dependency(user: CurrentUser = Depends(current_user)) -> CurrentUser:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Role is not allowed",
            )

        return user

    return dependency
