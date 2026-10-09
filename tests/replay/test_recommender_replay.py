"""C2-02 on the recordings: recorded trust -> recommender, with the other vehicles GREEN.

The 2 s bound is the requirement's proposed figure. Here the recommender runs on the same
report that turns RED, so the delay it adds is zero by construction; what this checks is that
the right recommendation appears once, at the right time, for the right reason.
"""

from pathlib import Path

from c2.allocator import assign, split_area
from c2.fleet import FleetState
from c2.messages import Command, Recommendation
from c2.recommender import Recommender
from navtrust.engine import TrustEngine
from navtrust.recording import load_recording
from navtrust.replay import replay_engine
from navtrust.types import NavTrust, ReasonCode, TrustState

DATA = Path(__file__).parent / "data"
POS = {"uav1": (0.0, 0.0), "uav2": (0.0, 5.0), "uav3": (0.0, 10.0)}


def recommendations_for(name: str) -> tuple[list[tuple[float, Recommendation]], list[NavTrust]]:
    now = [0.0]
    recommender = Recommender(lambda: now[0])
    fleet = FleetState(
        assign(split_area(1000, 900, 3), ["uav1", "uav2", "uav3"]), positions=dict(POS)
    )
    for v in ("uav2", "uav3"):
        recommender.observe(NavTrust(v, 0.0, TrustState.GREEN, None, 0.15, 1.0), fleet)
    reports = replay_engine(load_recording(DATA / f"{name}.jsonl"), TrustEngine("uav1"))
    out: list[tuple[float, Recommendation]] = []
    for report in reports:
        now[0] = report.stamp_s
        out.extend((report.stamp_s, r) for r in recommender.observe(report, fleet))
    return out, reports


def test_stuck_position_gives_one_hold_and_retask_right_after_it_turns_red() -> None:
    recs, reports = recommendations_for("stuck_zone-1")
    assert len(recs) == 1
    t, rec = recs[0]
    assert rec.command is Command.HOLD and rec.reason is ReasonCode.INCONSISTENT_INNOVATION
    assert [m.sector_id for m in rec.sector_moves] == ["S1"]
    first_red = next(r.stamp_s for r in reports if r.state is TrustState.RED)
    assert t == first_red == rec.created_s


def test_long_outage_gives_one_retask_and_short_outages_give_none() -> None:
    recs, reports = recommendations_for("jamming_zone-1")
    assert len(recs) == 1  # three 4 s crossings stay AMBER, the 8.8 s one goes RED
    t, rec = recs[0]
    assert rec.command is None and rec.reason is ReasonCode.GNSS_LOSS
    assert t == next(r.stamp_s for r in reports if r.state is TrustState.RED)


def test_amber_only_runs_give_nothing() -> None:
    for name in ("nominal-1", "nominal-2", "nominal-3", "nominal-4", "wrong_zone-1"):
        recs, _ = recommendations_for(name)
        assert recs == [], name
