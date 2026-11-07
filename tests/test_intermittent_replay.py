"""The link_intermittent recordings against the backend: no duplicate or stale command (issue 77).

The recordings are vehicle-side: three 6 s link cuts and no backend, no operator, no command. What
is replayed here is their recorded link timing. The trust reports and the recommendation are
synthetic, and the replay says so. This needs no simulator.
"""

from pathlib import Path

import pytest

from eval.intermittent_replay import Situation, replay_flaps

RECORDINGS = Path(__file__).resolve().parents[1] / "eval" / "lost_link" / "recordings"
PATHS = [RECORDINGS / f"link_intermittent-{n}.jsonl" for n in (1, 2)]


@pytest.mark.parametrize("path", PATHS, ids=lambda p: p.stem)
def test_every_flap_is_one_outage_and_the_recording_has_the_three_cuts(path: Path) -> None:
    result = replay_flaps(path, Situation.UNCHANGED)
    assert result.cuts == 3
    assert result.outages == result.cuts


@pytest.mark.parametrize("path", PATHS, ids=lambda p: p.stem)
def test_an_unchanged_situation_is_commanded_once_however_often_it_is_approved(path: Path) -> None:
    result = replay_flaps(path, Situation.UNCHANGED)
    assert result.superseded == []
    assert result.commands_sent == {"r1": 1}
    assert result.last_attempt == "already_decided"


@pytest.mark.parametrize("path", PATHS, ids=lambda p: p.stem)
def test_a_situation_that_changed_in_an_outage_is_never_commanded(path: Path) -> None:
    result = replay_flaps(path, Situation.CHANGED)
    assert result.superseded == ["r1"]
    assert result.commands_sent == {}
    assert result.last_attempt == "superseded"
