"""Things that must never be tracked in git.

A `git add -A` on a branch whose .gitignore was out of date once committed 4,073 files of
console/node_modules; CI passed regardless, so nothing noticed."""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FORBIDDEN = ("node_modules/", "console/dist/", ".venv/", "__pycache__/", ".mypy_cache/",
             ".ruff_cache/", ".pytest_cache/", "logs/")  # fmt: skip
MAX_TRACKED_FILE_BYTES = 5_000_000


def tracked() -> list[str]:
    if shutil.which("git") is None or not (ROOT / ".git").exists():
        pytest.skip("not a git checkout")
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True)
    return out.stdout.splitlines()


def test_no_dependencies_or_build_output_are_tracked() -> None:
    bad = [f for f in tracked() if any(part in f for part in FORBIDDEN) or f.endswith(".sqlite")]
    assert bad == [], f"tracked but should be ignored (first 5): {bad[:5]}"


def test_no_large_files_are_tracked() -> None:
    big = [
        f
        for f in tracked()
        if (ROOT / f).is_file() and (ROOT / f).stat().st_size > MAX_TRACKED_FILE_BYTES
    ]
    assert big == [], f"files over {MAX_TRACKED_FILE_BYTES:,} bytes: {big}"
