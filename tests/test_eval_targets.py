"""One command refreshes every committed eval table, and a stale table says which (issue 173).

Editing a file the engine fingerprint covers makes the committed tables stale. `make eval` alone
refreshed only the development set, and nothing named `make eval-heldout`."""

import shutil
import subprocess
from pathlib import Path

import pytest

from eval.freeze import PATTERNS, stale_hint

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.skipif(shutil.which("make") is None, reason="make is not installed")
def test_one_target_refreshes_the_development_and_the_held_out_tables() -> None:
    plan = subprocess.run(
        ["make", "-n", "eval-all"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout
    steps = sorted(line.strip() for line in plan.splitlines() if "eval.evaluate" in line)
    assert steps == ["python -m eval.evaluate", "python -m eval.evaluate --heldout"]


def test_a_stale_table_names_the_command_and_the_files_that_make_it_stale() -> None:
    hint = stale_hint()
    assert "make eval-all" in hint
    for pattern in PATTERNS:
        assert pattern in hint
