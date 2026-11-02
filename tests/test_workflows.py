"""CI hardening (issue 163): workflows run with the least access they need, and every action is
pinned to a commit, so a moved tag cannot change what CI runs."""

import re
from pathlib import Path

import pytest
import yaml

WORKFLOW_DIR = Path(__file__).resolve().parent.parent / ".github" / "workflows"
WORKFLOWS = sorted(WORKFLOW_DIR.glob("*.yml"))


def test_there_are_workflows_to_check() -> None:
    assert WORKFLOWS


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_every_action_is_pinned_to_a_commit_with_a_version_comment(path: Path) -> None:
    for line in path.read_text(encoding="utf-8").splitlines():
        if "uses:" not in line or "uses: ./" in line:
            continue
        assert re.search(r"uses: \S+@[0-9a-f]{40} +# v\d", line), f"{path.name}: {line.strip()}"


def test_the_ci_workflow_can_only_read_the_repository() -> None:
    ci = yaml.safe_load((WORKFLOW_DIR / "ci.yml").read_text(encoding="utf-8"))
    assert ci["permissions"] == {"contents": "read"}
