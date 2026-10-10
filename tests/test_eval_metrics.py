"""Metric definitions on small recordings built by hand, so every expected value is known."""

from typing import Any

import pytest

from eval.metrics import EvalConfig, episodes, error_at, fault_windows, position_errors, run_metrics
from navtrust.recording import Recording
from navtrust.types import NavTrust, TrustState

CFG = EvalConfig()
LAT0, LON0 = 47.0, 8.0
M_PER_DEG_LAT = 111_194.9  # 6_371_008.8 m * pi / 180


def north(m: float) -> float:
    return LAT0 + m / M_PER_DEG_LAT


def build(
    *,
    fix_changes: list[tuple[float, str]] | None = None,
    end_s: float = 60.0,
    ratio: float = 0.05,
    fault: tuple[float, float | None] | None = None,
    truth_offset_m: dict[float, float] | None = None,
    est_north: dict[float, float] | None = None,
    finished: bool = True,
) -> Recording:
    """A vehicle that starts healthy: fix OK from t = 0, estimator status each second."""
    rec: list[dict[str, Any]] = [{"t_s": 0.0, "event": "home", "lat_deg": LAT0, "lon_deg": LON0}]
    rec.append({"t_s": 0.0, "event": "gps_info", "fix_type": "FIX_3D", "num_satellites": 10})
    for t, fix in fix_changes or []:
        rec.append({"t_s": t, "event": "gps_info", "fix_type": fix, "num_satellites": 10})
    for i in range(int(end_s) + 1):
        rec.append(
            {"t_s": float(i), "event": "estimator_status", "pos_horiz_accuracy": 0.15,
             "pos_horiz_ratio": ratio, "vel_ratio": ratio}
        )  # fmt: skip
    if fault:
        rec.append({"t_s": fault[0], "event": "gnss_enter", "east_m": 0, "north_m": 0})
        if fault[1] is not None:
            rec.append({"t_s": fault[1], "event": "gnss_exit", "east_m": 0, "north_m": 0})
    for i in range(int(end_s) + 1):
        t = float(i)
        n_est = (est_north or {}).get(t, 0.0)
        offset = (truth_offset_m or {}).get(t, 0.0)
        rec.append(
            {
                "t_s": t,
                "event": "position",
                "lat_deg": north(n_est),
                "lon_deg": LON0,
                "rel_alt_m": 30,
            }
        )
        truth = {"vehicle": "uav1", "east_m": 0.0, "north_m": n_est + offset, "alt_m": 30}
        rec.append({"t_s": t, "event": "truth", **truth})
    rec.append({"t_s": end_s - 1, "event": "mission_progress", "current": 4, "total": 4})
    if finished:
        rec.append({"t_s": end_s - 0.5, "event": "mission_finished"})
    rec.append({"t_s": end_s, "event": "landed"})
    rec.sort(key=lambda r: r["t_s"])
    return Recording(header={"scenario": "x", "schema": 1}, records=rec)


def test_a_clean_run_has_no_alerts_and_no_misleading_time() -> None:
    m = run_metrics("r", build(), CFG)
    assert m.fault_start_s is None and m.detected is None and m.ttd_s is None
    assert m.false_alert_episodes == 0 and m.false_alert_s == 0
    assert m.misleading_s == 0 and m.max_error_green_m == pytest.approx(0, abs=0.01)
    assert m.mission_finished and m.waypoints_reached == 1.0 and m.landed
    assert m.interruptions == 0
    assert m.started_s == pytest.approx(2.0, abs=0.5)  # fix from t = 0 plus the 2 s recovery hold


def test_ttd_is_the_time_from_the_fault_to_the_first_alert() -> None:
    rec = build(fix_changes=[(21.0, "NO_GPS"), (26.0, "FIX_3D")], fault=(20.0, 26.0))
    m = run_metrics("r", rec, CFG)
    assert m.fault_start_s == 20.0 and m.detected is True
    assert m.ttd_s == pytest.approx(1.0, abs=0.5)  # the fix changed 1 s after the injection
    assert m.false_alert_episodes == 0  # the whole episode is inside the fault window


def test_an_alert_with_no_fault_is_a_false_alert() -> None:
    rec = build(fix_changes=[(30.0, "NO_GPS"), (33.0, "FIX_3D")])
    m = run_metrics("r", rec, CFG)
    assert m.false_alert_episodes == 1
    assert 3.0 <= m.false_alert_s <= 7.0  # outage plus the recovery hold


def test_an_alert_long_after_the_fault_window_is_false_but_one_shortly_after_is_not() -> None:
    soon = run_metrics(
        "r", build(fix_changes=[(24.0, "NO_GPS"), (27.0, "FIX_3D")], fault=(10.0, 20.0)), CFG
    )
    late = run_metrics(
        "r", build(fix_changes=[(40.0, "NO_GPS"), (43.0, "FIX_3D")], fault=(10.0, 20.0)), CFG
    )
    assert (
        soon.false_alert_episodes == 0
    )  # starts 4 s after the window ended: inside the 5 s margin
    assert late.false_alert_episodes == 1


def test_a_fault_that_is_never_noticed_is_not_detected() -> None:
    m = run_metrics("r", build(fault=(20.0, 26.0)), CFG)
    assert m.detected is False and m.ttd_s is None and m.error_at_detection_m is None


def test_misleading_time_counts_green_seconds_with_a_large_true_error() -> None:
    off = {float(t): 25.0 for t in range(30, 36)}  # 6 samples, true position 25 m from the estimate
    m = run_metrics("r", build(truth_offset_m=off), CFG)
    assert m.misleading_s == pytest.approx(6 * 2 * 0.5, abs=1.0)  # 1 Hz samples, 0.5 s report steps
    assert m.max_error_green_m == pytest.approx(25.0, abs=0.5)


def test_error_at_detection_is_the_true_error_when_the_alert_fires() -> None:
    rec = build(
        fix_changes=[(21.0, "NO_GPS")],
        fault=(20.0, None),
        truth_offset_m={20.0: 12.0, 21.0: 33.0, 22.0: 40.0},
    )
    m = run_metrics("r", rec, CFG)
    assert m.error_at_detection_m == pytest.approx(33.0, abs=8.0)  # error at about 21 s


def test_no_ground_truth_gives_none_not_zero() -> None:
    rec = build()
    rec = Recording(rec.header, [r for r in rec.records if r["event"] != "truth"])
    m = run_metrics("r", rec, CFG)
    assert m.misleading_s is None and m.max_error_green_m is None and m.error_at_detection_m is None


def test_unfinished_missions_are_reported_as_such() -> None:
    m = run_metrics("r", build(finished=False), CFG)
    assert m.mission_finished is False


def test_helpers() -> None:
    rec = build(fault=(5.0, 9.0))
    assert fault_windows(rec, 60.0, 5.0) == [(5.0, 14.0)]
    assert fault_windows(build(fault=(5.0, None)), 60.0, 5.0) == [(5.0, 60.0)]
    errs = position_errors(build(truth_offset_m={3.0: 7.0}))
    assert error_at(errs, 3.0) == pytest.approx(7.0, abs=0.05) and error_at([], 3.0) is None
    reports = [
        NavTrust("u", float(t), TrustState.RED if 3 <= t < 5 else TrustState.GREEN, None, 0.0, 0.0)
        for t in range(10)
    ]
    assert episodes(reports, 0.0, 1.0) == [(3.0, 2.0)]
    assert episodes(reports, 5.0, 1.0) == []  # everything before the start time is ignored


def test_truth_is_interpolated_to_the_estimate_time_not_matched_to_the_nearest_sample() -> None:
    """A vehicle at 10 m/s with truth every 1 s and estimates half a second later is exactly
    right; nearest-sample matching would report up to 5 m of error."""
    records: list[dict[str, Any]] = [
        {"t_s": 0.0, "event": "home", "lat_deg": LAT0, "lon_deg": LON0}
    ]
    for i in range(6):
        records.append({"t_s": float(i), "event": "truth", "vehicle": "uav1",
                        "east_m": 0.0, "north_m": 10.0 * i, "alt_m": 30})  # fmt: skip
        records.append({"t_s": i + 0.5, "event": "position", "lat_deg": north(10.0 * (i + 0.5)),
                        "lon_deg": LON0, "rel_alt_m": 30})  # fmt: skip
    errs = position_errors(Recording({"schema": 1}, sorted(records, key=lambda r: r["t_s"])))
    assert errs and max(e for _, e in errs) < 0.1


def test_a_gap_in_the_truth_is_not_bridged() -> None:
    records: list[dict[str, Any]] = [
        {"t_s": 0.0, "event": "home", "lat_deg": LAT0, "lon_deg": LON0}
    ]
    for t in (0.0, 1.0, 10.0):
        records.append(
            {
                "t_s": t,
                "event": "truth",
                "vehicle": "uav1",
                "east_m": 0.0,
                "north_m": 0.0,
                "alt_m": 30,
            }
        )
    records.append(
        {"t_s": 5.0, "event": "position", "lat_deg": LAT0, "lon_deg": LON0, "rel_alt_m": 30}
    )
    assert position_errors(Recording({"schema": 1}, sorted(records, key=lambda r: r["t_s"]))) == []
