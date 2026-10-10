"""Evidence for ADR 0003: what each operator action does to a vehicle whose GPS position is
frozen. One run per action in PX4 SITL (Gazebo), ground truth from Gazebo, the fault latched
(it does not clear when the vehicle moves). Single runs: they show what is possible, they are
not statistics.
"""

import math
from pathlib import Path

import pytest

from navtrust.recording import Recording, load_recording

DATA = Path(__file__).parent / "data" / "experiments"


def load(action: str) -> Recording:
    return load_recording(DATA / f"stuck-action-{action}.jsonl")


def truth(rec: Recording) -> list[tuple[float, float, float, float]]:
    return [(t["t_s"], t["east_m"], t["north_m"], t["alt_m"]) for t in rec.of("truth")]


def farthest_from_start(rec: Recording) -> float:
    return max(math.hypot(e, n) for _, e, n, _ in truth(rec))


def speed_at(rec: Recording, t_s: float) -> float:
    pts = truth(rec)
    a = min(pts, key=lambda p: abs(p[0] - (t_s - 1)))
    b = min(pts, key=lambda p: abs(p[0] - (t_s + 1)))
    return math.hypot(b[1] - a[1], b[2] - a[2]) / max(b[0] - a[0], 1e-6)


@pytest.mark.parametrize("action", ["none", "hold", "rtl", "land"])
def test_runs_are_comparable(action: str) -> None:
    rec = load(action)
    assert rec.header["failure_mode"] == "stuck" and rec.header["latch_fault"] is True
    assert rec.header["ground_truth"] is True
    assert len(rec.of("gnss_enter")) == 1 and rec.of("gnss_exit") == []  # the fault never cleared
    action_event = rec.first("operator_action")
    expected = None if action == "none" else action
    assert (action_event["action"] if action_event else None) == expected
    if action_event:
        assert action_event["t_s"] - rec.of("gnss_enter")[0]["t_s"] == pytest.approx(15, abs=1.5)


def test_without_action_the_vehicle_flies_away_and_keeps_accelerating() -> None:
    rec = load("none")
    fault = rec.of("gnss_enter")[0]["t_s"]
    assert farthest_from_start(rec) > 4000  # the survey route is 600 m long
    assert speed_at(rec, fault + 120) > 30  # nominal survey speed is 10 m/s
    last = truth(rec)[-1]
    assert last[3] > 20  # still airborne


def test_land_ends_the_flight_quickly_and_the_vehicle_stops() -> None:
    rec = load("land")
    event = rec.first("operator_action")
    assert event is not None
    action = event["t_s"]
    on_ground = next(t for t, _, _, alt in truth(rec) if t > action and alt < 0.5)
    assert on_ground - action < 25  # measured about 15 s
    assert farthest_from_start(rec) < 600
    assert speed_at(rec, on_ground + 30) < 0.5


@pytest.mark.parametrize("action", ["hold", "rtl"])
def test_hold_and_rtl_do_not_end_in_a_controlled_stop(action: str) -> None:
    """They stopped the runaway but ended in a fast, uncontrolled descent far from where the
    vehicle believed it was. This is the observed behaviour, not a statement about PX4 in
    general."""
    rec = load(action)
    pts = truth(rec)
    event = rec.first("operator_action")
    assert event is not None
    descent = next(i for i, p in enumerate(pts) if p[3] < 3.0 and p[0] > event["t_s"])
    assert speed_at(rec, pts[descent][0]) > 5  # still moving fast when it reached the ground
    assert farthest_from_start(rec) > 400
    assert farthest_from_start(rec) < 1000  # the runaway itself was contained
