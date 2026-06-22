from enum import StrEnum
from collections.abc import Callable

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
    if not authorization or not authorization.startswith("Bearer dev:"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    role_name = authorization.removeprefix("Bearer dev:")
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
