import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_generated_frontend_api_types_match_current_openapi_schema() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/check_api_types.py"],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
