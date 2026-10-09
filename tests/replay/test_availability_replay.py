"""The availability detector over the committed recordings.

Thresholds are the detector's default proposals. The numbers asserted here were measured on
these recordings and are bounds on this data, not guarantees.
"""

from pathlib import Path

import pytest

from navtrust.availability import Availability, AvailabilityDetector, AvailabilityReport
from navtrust.recording import Recording, load_recording
from navtrust.replay import replay_availability

DATA = Path(__file__).parent / "data"


def run(name: str) -> tuple[Recording, list[AvailabilityReport]]:
    rec = load_recording(DATA / f"{name}.jsonl")
    return rec, replay_availability(rec, AvailabilityDetector())


def status_at(reports: list[AvailabilityReport], t_s: float) -> Availability:
    return min(reports, key=lambda r: abs(r.stamp_s - t_s)).status


def first_time(
    reports: list[AvailabilityReport], status: Availability, after_s: float
) -> float | None:
    return next((r.stamp_s for r in reports if r.stamp_s >= after_s and r.status is status), None)


@pytest.mark.parametrize("name", ["nominal-1", "nominal-2", "nominal-3", "nominal-4"])
def test_nominal_runs_are_ok_once_started(name: str) -> None:
    rec, reports = run(name)
    first_gps = rec.first("gps_info")
    assert first_gps is not None
    started = first_gps["t_s"] + 3.0  # fix seen + recover_after_s, with margin
    bad = [r for r in reports if r.stamp_s >= started and r.status is not Availability.OK]
    assert bad == []


def test_jamming_is_detected_quickly_and_cleared_after_each_crossing() -> None:
    rec, reports = run("jamming_zone-1")
    enters, exits = rec.of("gnss_enter"), rec.of("gnss_exit")
    assert len(enters) == len(exits) == 4
    for enter, leave in zip(enters, exits, strict=True):
        lost_at = first_time(reports, Availability.LOST, enter["t_s"])
        assert lost_at is not None
        assert lost_at - enter["t_s"] <= 2.0  # measured 1.02 to 1.24 s on these 4 crossings
        ok_at = first_time(reports, Availability.OK, leave["t_s"])
        assert ok_at is not None
        assert 2.0 <= ok_at - leave["t_s"] <= 3.0  # recover_after_s plus the 0.5 s step


def test_wrong_mode_shows_as_degraded_not_lost() -> None:
    rec, reports = run("wrong_zone-1")
    for enter in rec.of("gnss_enter"):
        degraded_at = first_time(reports, Availability.DEGRADED, enter["t_s"])
        assert degraded_at is not None and degraded_at - enter["t_s"] <= 2.0
    assert Availability.LOST not in {r.status for r in reports}


def test_stuck_position_is_invisible_to_the_availability_detector() -> None:
    """Documents a limit, not a feature: the receiver keeps a good fix while the position
    is frozen, so only the consistency detector can see this fault (ADR 0001)."""
    rec, reports = run("stuck_zone-1")
    enter = rec.first("gnss_enter")
    assert enter is not None
    after = [r for r in reports if r.stamp_s >= enter["t_s"] + 3.0]
    assert {r.status for r in after} == {Availability.OK}


def test_bound_grows_during_a_gnss_outage() -> None:
    rec, reports = run("jamming_zone-1")
    enter = rec.of("gnss_enter")[0]
    before = next(r for r in reports if r.stamp_s >= enter["t_s"] - 1).horizontal_bound_m
    during = max(
        r.horizontal_bound_m or 0.0
        for r in reports
        if enter["t_s"] <= r.stamp_s <= enter["t_s"] + 3
    )
    assert before is not None and during > 2 * before
