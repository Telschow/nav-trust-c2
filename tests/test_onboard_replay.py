"""Issue 76 acceptance, offline: replay recorded runs through the onboard monitor.

The link signal is the recording's own `link_cut` and `link_restore` events, so this says when
the monitor's rule fires given a cut, not that PX4 treats the cut as a lost link. The trust
inputs are PX4's own figures through the trust engine (ADR 0005); the rule is not calibrated.
"""

from pathlib import Path

import pytest

from eval.onboard_replay import POLICY_DOC, ReplayResult, replay

ROOT = Path(__file__).resolve().parent.parent
LOST_LINK = ROOT / "eval" / "lost_link" / "recordings"
MAIN = ROOT / "eval" / "recordings"
HELDOUT = ROOT / "eval" / "heldout" / "recordings"


def test_the_replay_policy_is_the_adr_0004_contingency() -> None:
    assert POLICY_DOC["entries"] == [
        {"reason": "INCONSISTENT_INNOVATION", "link": "NO_LINK", "action": "LAND"}
    ]
    assert 0 < POLICY_DOC["wait_s"] < 10


@pytest.mark.parametrize("name", ["link_and_frozen-1", "link_and_frozen-2"])
def test_a_frozen_position_with_the_link_cut_makes_the_monitor_land(name: str) -> None:
    result = replay(LOST_LINK / f"{name}.jsonl")
    assert isinstance(result, ReplayResult)
    assert result.cut_s is not None and result.action_s is not None
    # the cut, then the wait, then the next report: no earlier than the wait after the cut
    assert result.action_s - result.cut_s > POLICY_DOC["wait_s"]
    assert result.action_s - result.cut_s < 12.0  # below the first PX4 failsafe window


@pytest.mark.parametrize(
    "path",
    sorted(LOST_LINK.glob("link_only-*.jsonl"))
    + sorted(MAIN.glob("*.jsonl"))
    + sorted(HELDOUT.glob("*.jsonl")),
    ids=lambda p: p.stem,
)
def test_no_onboard_action_in_the_nominal_jamming_stuck_wrong_fix_and_link_only_recordings(
    path: Path,
) -> None:
    result = replay(path)
    assert result.action_s is None, f"{path.stem} would have landed at {result.action_s}"
