"""Issue 141: what the vehicle was doing when LAND was commanded, and what PX4 did next."""

from typing import Any

import pytest

from eval.land_diagnosis import RunState, measure, summarise
from navtrust.recording import Recording


def truth(t: float, alt: float, east: float, north: float = 0.0) -> dict[str, Any]:
    return {"t_s": t, "event": "truth", "vehicle": "uav1", "east_m": east, "north_m": north,
            "alt_m": alt, "sim_s": t}  # fmt: skip


def recording(
    samples: list[tuple[float, float, float]],
    modes: list[tuple[float, str]] | None,
    command_s: float = 20.0,
    speed: float = 12.0,
    delay: float = 5.0,
) -> Recording:
    header: dict[str, Any] = {
        "t_s": 0.0, "event": "header", "schema": 1, "survey": {"speed_m_s": speed},
        "operator_action": {"action": "land", "delay_s": delay},
    }  # fmt: skip
    records: list[dict[str, Any]] = [
        {"t_s": command_s - delay, "event": "gnss_enter", "east_m": 0.0, "north_m": 0.0},
        {"t_s": command_s, "event": "operator_action", "action": "land"},
    ]
    records += [truth(t, alt, east) for t, alt, east in samples]
    for t, mode in modes or []:
        records.append({"t_s": t, "event": "flight_mode", "mode": mode})
    records.sort(key=lambda r: r["t_s"])
    return Recording(header=header, records=records)


# cruises east at 12 m/s, LAND at 20 s, comes down by 32 s while still moving east at 9 m/s
FAST: list[tuple[float, float, float]] = [
    (1, 0, 0), (5, 30, 20), (19, 30, 200), (20, 30, 212), (21, 30, 224),
    (25, 15, 262), (30, 3, 305), (32, 0.2, 323),
]  # fmt: skip
MODES = [(5.0, "MISSION"), (20.4, "LAND")]


def test_it_reports_when_px4_entered_land_and_how_fast_the_vehicle_was_moving() -> None:
    run = measure(recording(FAST, MODES))
    assert isinstance(run, RunState)
    assert run.command_to_land_mode_s == pytest.approx(0.4)
    assert run.mode_at_command == "MISSION"
    assert run.speed_at_command_m_s == pytest.approx(12.0)  # 12 m east in the second around it
    assert run.touchdown_speed_m_s is not None and run.touchdown_speed_m_s > 5.0
    assert (run.action, run.speed, run.delay) == ("land", 12.0, 5.0)


def test_without_flight_mode_events_the_mode_questions_are_unanswered_not_guessed() -> None:
    run = measure(recording(FAST, None))
    assert run.command_to_land_mode_s is None and run.mode_at_command is None
    assert run.speed_at_command_m_s == pytest.approx(12.0)  # the speed still comes from truth


def test_a_vehicle_that_never_entered_land_has_no_time_to_land_mode() -> None:
    run = measure(recording(FAST, [(5.0, "MISSION")]))
    assert run.command_to_land_mode_s is None and run.mode_at_command == "MISSION"


def test_the_mode_a_vehicle_was_in_is_the_last_one_entered_before_the_command() -> None:
    run = measure(recording(FAST, [(5.0, "MISSION"), (15.0, "HOLD"), (20.4, "LAND")]))
    assert run.mode_at_command == "HOLD"


def test_cells_report_counts_and_ranges_never_rates() -> None:
    runs = [measure(recording(FAST, MODES)), measure(recording(FAST, MODES))]
    [cell] = summarise(runs)
    assert cell.n == 2 and cell.with_mode_events == 2
    assert cell.command_to_land_mode_s is not None
    lo, hi = cell.command_to_land_mode_s
    assert lo == pytest.approx(0.4) and hi == pytest.approx(0.4)


def test_a_cell_says_how_many_runs_had_flight_mode_events() -> None:
    runs = [measure(recording(FAST, MODES)), measure(recording(FAST, None))]
    [cell] = summarise(runs)
    assert (cell.n, cell.with_mode_events) == (2, 1)
