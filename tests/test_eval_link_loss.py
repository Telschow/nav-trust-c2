"""Issue 75: the link_loss family is measured from ground truth, as counts and ranges, and the
committed table must match the recordings."""

from pathlib import Path
from typing import Any

from eval.link_loss import (
    SURVEY_MARGIN_M,
    authorities,
    last_trusted_time,
    measure_run,
    survey_excess_m,
    table,
    touchdown,
)
from navtrust.recording import load_recording
from navtrust.types import NavTrust, ReasonCode, TrustState

ROOT = Path(__file__).resolve().parent.parent
RECORDINGS = ROOT / "eval" / "lost_link" / "recordings"
TABLE = ROOT / "eval" / "lost_link" / "results.md"


def truth(t: float, alt: float, east: float = 0.0, north: float = 0.0) -> dict[str, Any]:
    return {"t_s": t, "event": "truth", "vehicle": "uav1", "east_m": east, "north_m": north,
            "alt_m": alt, "sim_s": t}  # fmt: skip


def report(t: float, state: TrustState) -> NavTrust:
    reason = None if state is TrustState.GREEN else ReasonCode.INCONSISTENT_INNOVATION
    return NavTrust("uav1", t, state, reason, 0.15, 1.0)


def test_touchdown_is_the_first_ground_sample_after_the_vehicle_was_airborne() -> None:
    samples = [truth(1, 0.0), truth(5, 30.0, 10), truth(20, 30.0, 50), truth(30, 0.3, 55, 2)]
    assert touchdown(samples) == (30.0, 55.0, 2.0)  # not the ground samples before takeoff


def test_a_vehicle_that_never_comes_down_has_no_touchdown() -> None:
    assert touchdown([truth(1, 0.0), truth(5, 30.0), truth(99, 28.0)]) is None


def test_the_last_trusted_time_is_the_last_green_report_before_trust_was_lost() -> None:
    reports = [report(t, TrustState.GREEN) for t in range(0, 10)]
    reports += [report(t, TrustState.RED) for t in range(10, 20)]
    reports += [report(t, TrustState.GREEN) for t in range(20, 25)]  # recovery is not trust before
    assert last_trusted_time(reports, fault_s=8.0) == 9.0


def test_if_trust_is_never_lost_the_last_trusted_position_is_the_one_at_the_fault() -> None:
    reports = [report(t, TrustState.GREEN) for t in range(0, 100)]
    assert last_trusted_time(reports, fault_s=40.0) == 40.0


def test_survey_excess_is_how_far_the_vehicle_got_outside_the_area_plus_the_margin() -> None:
    survey = {"width_m": 600.0, "height_m": 100.0}
    inside = [truth(1, 30, 10, 10), truth(2, 30, 600 + SURVEY_MARGIN_M, 100)]
    assert survey_excess_m(inside, survey) == 0.0
    out = [truth(1, 30, 600 + SURVEY_MARGIN_M + 120, 40), truth(2, 30, -SURVEY_MARGIN_M - 5, 40)]
    assert survey_excess_m(out, survey) == 120.0


def test_each_action_is_attributed_to_the_authority_it_ran_under() -> None:
    records: list[dict[str, Any]] = [
        {"t_s": 3.0, "event": "flight_mode", "mode": "HOLD"},  # before the fault: not an action
        {"t_s": 50.0, "event": "gnss_enter"},
        {"t_s": 60.0, "event": "flight_mode", "mode": "RETURN_TO_LAUNCH"},  # nobody asked
        {"t_s": 70.0, "event": "operator_action", "action": "land"},
        {"t_s": 70.5, "event": "flight_mode", "mode": "LAND"},
        {"t_s": 80.0, "event": "onboard_action", "action": "LAND"},
        {"t_s": 80.4, "event": "flight_mode", "mode": "LAND"},
        {"t_s": 90.0, "event": "flight_mode", "mode": "UNKNOWN"},
        {"t_s": 95.0, "event": "flight_mode", "mode": "MISSION"},
    ]
    assert authorities(records, fault_s=50.0) == [
        "PX4 failsafe: RETURN_TO_LAUNCH",
        "operator approval: LAND",
        "pre-authorised policy: LAND",
    ]


def test_no_action_after_the_fault_is_none() -> None:
    assert authorities([{"t_s": 1.0, "event": "flight_mode", "mode": "HOLD"}], fault_s=50.0) == []


def test_link_only_lands_under_px4s_failsafe_and_stays_inside_the_survey_area() -> None:
    row = measure_run(load_recording(RECORDINGS / "link_only-1.jsonl"))
    assert row.outcome == "landed"
    assert "PX4 failsafe: RETURN_TO_LAUNCH" in row.authority
    assert row.touchdown_speed_m_s is not None


def test_a_frozen_position_with_the_link_cut_does_not_end_in_a_controlled_stop() -> None:
    row = measure_run(load_recording(RECORDINGS / "link_and_frozen-1.jsonl"))
    assert row.stop_after_fault_s is None
    assert row.outside_survey_m > 0  # it left the survey area


def test_the_committed_table_matches_the_recordings() -> None:
    """CI fails if the committed table differs from what the recordings give."""
    assert TABLE.read_text(encoding="utf-8") == table(RECORDINGS)
