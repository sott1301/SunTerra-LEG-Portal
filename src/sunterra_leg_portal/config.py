from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
import os

from fastapi import FastAPI


REQUIRED_PRODUCTION_CONFIG = (
    "SUNTERRA_SECRET_KEY",
    "SUNTERRA_DATABASE_URL",
    "SUNTERRA_ALLOWED_ORIGINS",
    "SUNTERRA_SMTP_HOST",
    "SUNTERRA_SMTP_PORT",
    "SUNTERRA_SMTP_FROM_EMAIL",
    "SUNTERRA_PUBLIC_BASE_URL",
)


class ProductionConfigurationError(RuntimeError):
    pass


def production_config_errors(environ: Mapping[str, str] = os.environ) -> list[str]:
    if environ.get("SUNTERRA_ENV") != "production":
        return []

    return [
        name
        for name in REQUIRED_PRODUCTION_CONFIG
        if not environ.get(name)
    ]


def assert_production_configured(environ: Mapping[str, str] = os.environ) -> None:
    missing = production_config_errors(environ)
    if missing:
        joined = ", ".join(missing)
        raise ProductionConfigurationError(
            f"Missing required production configuration: {joined}",
        )


@asynccontextmanager
async def production_lifespan(_app: FastAPI) -> AsyncIterator[None]:
    assert_production_configured()
    yield
