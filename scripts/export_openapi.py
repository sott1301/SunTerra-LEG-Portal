from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sunterra_leg_portal.main import app  # noqa: E402


def openapi_schema() -> dict[str, Any]:
    return app.openapi()


def write_openapi_schema(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(openapi_schema(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export the SunTerra LEG Portal OpenAPI schema.",
    )
    parser.add_argument(
        "output",
        nargs="?",
        default=PROJECT_ROOT / "frontend" / "src" / "generated" / "openapi.json",
        type=Path,
    )
    args = parser.parse_args()

    write_openapi_schema(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
