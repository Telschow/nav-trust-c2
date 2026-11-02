"""A hanging test fails with a timeout instead of stalling the run (issue 172).

The real case was a WebSocket test waiting for an event that never came; it stalled a whole run.
Every test has a per-test limit (pyproject.toml); here a sleeping test is run in a separate pytest
process under the project's own configuration, with the limit shortened to one second."""

import subprocess
import sys
import textwrap
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_a_hanging_test_is_reported_as_a_timeout_not_a_hang(tmp_path: Path) -> None:
    test = tmp_path / "test_hangs.py"
    test.write_text(
        textwrap.dedent(
            """
            import time

            def test_hangs():
                time.sleep(30)
            """
        ),
        encoding="utf-8",
    )
    command = [
        sys.executable, "-m", "pytest", "-c", str(ROOT / "pyproject.toml"),
        "--rootdir", str(tmp_path), "-o", "timeout=1", "-p", "no:cacheprovider", str(test),
    ]  # fmt: skip
    done = subprocess.run(command, capture_output=True, text=True, timeout=25, check=False)
    assert done.returncode != 0
    assert "Timeout" in done.stdout + done.stderr


def test_the_project_sets_a_limit_for_every_test() -> None:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert config["tool"]["pytest"]["ini_options"]["timeout"] == 60  # a proposal, seconds
