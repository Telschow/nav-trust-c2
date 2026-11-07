"""Regression check: the hub and gate against the link timing of the link_intermittent recordings.

The recordings are vehicle-side: three 6 s link cuts and no backend, operator or command. Only
their recorded link timing is used. The recommendation, the trust reports and the operator are
synthetic (issue 77). This is not evidence about real reconnects or PX4, and it needs no simulator.
"""

from pathlib import Path

import pytest

from eval.intermittent_replay import Situation, Vehicle, replay_outages

RECORDINGS = Path(__file__).resolve().parents[1] / "eval" / "lost_link" / "recordings"
PATHS = [RECORDINGS / f"link_intermittent-{n}.jsonl" for n in (1, 2)]
every = pytest.mark.parametrize("path", PATHS, ids=lambda p: p.stem)


@every
def test_each_recorded_cut_is_one_outage_in_the_hub(path: Path) -> None:
    result = replay_outages(path, Situation.UNCHANGED)
    assert result.cuts == 3
    assert result.outages == result.cuts


@every
def test_an_approval_after_a_restore_commands_once_and_later_tries_are_refused(path: Path) -> None:
    result = replay_outages(path, Situation.UNCHANGED)
    assert result.superseded == []
    assert result.commands_sent == {"r1": 1}
    assert result.attempts == ["executed", "already_decided", "already_decided"]
    assert result.gate_repeat == "already_executed"  # the gate's own guard, not only the hub's


@every
def test_a_trust_change_in_an_outage_supersedes_the_recommendation_before_any_approval(
    path: Path,
) -> None:
    result = replay_outages(path, Situation.CHANGED)
    assert result.superseded == ["r1"]
    assert result.commands_sent == {}
    assert result.attempts == ["superseded"] * 3


@every
def test_an_approval_during_an_outage_commands_once_and_the_restore_does_not_resend(
    path: Path,
) -> None:
    """The hub lets the operator approve a recommendation raised before the outage while the
    vehicle is not heard (ADR 0004 and the audit say so). What it must not do is send twice."""
    for situation in Situation:
        result = replay_outages(path, situation, also_try_during_first_outage=True)
        assert result.commands_sent == {"r1": 1}
        assert result.attempts == [
            "executed",
            "already_decided",
            "already_decided",
            "already_decided",
        ]
        assert result.superseded == []  # decided before the vehicle could be heard again


@every
def test_a_command_the_vehicle_never_answers_is_audited_and_not_sent_again(path: Path) -> None:
    result = replay_outages(path, Situation.UNCHANGED, Vehicle.SILENT)
    assert result.commands_sent == {"r1": 1}
    assert result.not_acknowledged == 1
    assert result.attempts[0].startswith("not_acknowledged")
    assert result.attempts[1:] == ["already_decided", "already_decided"]
