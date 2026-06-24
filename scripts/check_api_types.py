from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GENERATED_DIR = PROJECT_ROOT / "frontend" / "src" / "generated"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.generate_api_types import generate_contracts  # noqa: E402


def compare_generated_file(expected: Path, actual: Path) -> str | None:
    if not expected.exists():
        return f"Missing generated file: {expected.relative_to(PROJECT_ROOT)}"

    expected_text = expected.read_text(encoding="utf-8")
    actual_text = actual.read_text(encoding="utf-8")
    if expected_text != actual_text:
        return (
            "Generated API types are stale: "
            f"{expected.relative_to(PROJECT_ROOT)} differs. "
            "Run python scripts/generate_api_types.py."
        )

    return None


def schema_ref_names(schema: Any) -> set[str]:
    if not isinstance(schema, dict):
        return set()

    ref = schema.get("$ref")
    prefix = "#/components/schemas/"
    if isinstance(ref, str) and ref.startswith(prefix):
        return {ref.removeprefix(prefix)}

    names: set[str] = set()
    for key in ("anyOf", "oneOf", "allOf"):
        value = schema.get(key)
        if isinstance(value, list):
            for option in value:
                names.update(schema_ref_names(option))

    names.update(schema_ref_names(schema.get("items")))
    return names


def frontend_uses_openapi_path(app_source: str, api_path: str) -> bool:
    static_parts = [
        part for part in re.split(r"\{[^}]+\}", api_path) if part
    ]
    return all(part in app_source for part in static_parts)


def request_body_schema_names(
    openapi_schema: dict[str, Any],
    app_source: str,
) -> set[str]:
    names: set[str] = set()
    paths = openapi_schema.get("paths", {})
    if not isinstance(paths, dict):
        return names

    for api_path, path_item in paths.items():
        if not isinstance(api_path, str) or not frontend_uses_openapi_path(
            app_source,
            api_path,
        ):
            continue
        if not isinstance(path_item, dict):
            continue
        for operation in path_item.values():
            if not isinstance(operation, dict):
                continue
            request_body = operation.get("requestBody")
            if not isinstance(request_body, dict):
                continue
            content = request_body.get("content")
            if not isinstance(content, dict):
                continue
            json_content = content.get("application/json")
            if not isinstance(json_content, dict):
                continue
            names.update(schema_ref_names(json_content.get("schema")))

    return names


def compare_frontend_request_schema_usage(
    app_path: Path,
    openapi_schema: dict[str, Any],
) -> str | None:
    if not app_path.exists():
        return f"Missing frontend app file: {app_path.relative_to(PROJECT_ROOT)}"

    app_source = app_path.read_text(encoding="utf-8")
    missing = [
        name
        for name in sorted(request_body_schema_names(openapi_schema, app_source))
        if f'ApiSchemas["{name}"]' not in app_source
        and f'components["schemas"]["{name}"]' not in app_source
    ]
    if missing:
        return (
            "Frontend API request payloads are not typed from generated OpenAPI "
            f"schemas: {', '.join(missing)}. "
            "Import them from frontend/src/generated/api-types.ts."
        )

    return None


def main() -> int:
    with TemporaryDirectory() as temporary_directory:
        temporary_output = Path(temporary_directory)
        generate_contracts(temporary_output)
        openapi_schema = json.loads(
            (temporary_output / "openapi.json").read_text(encoding="utf-8"),
        )
        errors = [
            error
            for error in [
                compare_generated_file(
                    GENERATED_DIR / "openapi.json",
                    temporary_output / "openapi.json",
                ),
                compare_generated_file(
                    GENERATED_DIR / "api-types.ts",
                    temporary_output / "api-types.ts",
                ),
                compare_frontend_request_schema_usage(
                    PROJECT_ROOT / "frontend" / "src" / "App.tsx",
                    openapi_schema,
                ),
            ]
            if error is not None
        ]

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
