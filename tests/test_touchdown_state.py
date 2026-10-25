"""Touchdown position and speed, on recordings built by hand."""

from collections.abc import Sequence
from pathlib import Path

import pytest

from eval.touchdown_state import main, measure_touchdown, table
from navtrust.recording import Recording


def truth(samples: Sequence[tuple[float, float, float, float]]) -> list[dict[str, object]]:
    return [
        {"t_s": t, "event": "truth", "east_m": e, "north_m": n, "alt_m": a}
        for t, e, n, a in samples
    ]


def rec(
    samples: Sequence[tuple[float, float, float, float]], cut_s: float | None = None
) -> Recording:
    records = truth(samples)
    if cut_s is not None:
        records.append({"t_s": cut_s, "event": "link_cut"})
    records.sort(key=lambda r: float(str(r["t_s"])))
    return Recording({}, records)


# Flies east at 10 m/s at 30 m, descends from t=10 to the ground at t=14 while moving 30 m/s east.
FLIGHT = [
    (0.0, 0.0, 0.0, 30.0),
    (5.0, 50.0, 0.0, 30.0),
    (10.0, 100.0, 0.0, 30.0),
    (12.0, 160.0, 0.0, 2.0),
    (13.0, 190.0, 0.0, 1.0),
    (14.0, 220.0, 0.0, 0.0),
]


def test_distances_are_from_the_first_truth_sample() -> None:
    state = measure_touchdown(rec(FLIGHT))
    assert state is not None
    assert state.farthest_m == pytest.approx(220.0)
    assert state.touchdown_from_start_m == pytest.approx(220.0)


def test_speed_is_the_mean_horizontal_speed_from_the_first_sample_below_3_m() -> None:
    state = measure_touchdown(rec(FLIGHT))
    assert state is not None
    assert state.window_s == pytest.approx(2.0)
    assert state.speed_m_s == pytest.approx(30.0)


def test_a_vehicle_that_stops_before_touchdown_has_no_speed_to_report_as_fast() -> None:
    stopped = [(0.0, 0.0, 0.0, 30.0), (5.0, 10.0, 0.0, 2.0), (8.0, 10.0, 0.0, 0.0)]
    state = measure_touchdown(rec(stopped))
    assert state is not None and state.speed_m_s == pytest.approx(0.0)


def test_a_single_sample_at_the_ground_gives_a_window_of_zero_and_no_speed() -> None:
    state = measure_touchdown(rec([(0.0, 0.0, 0.0, 30.0), (5.0, 40.0, 0.0, 0.0)]))
    assert state is not None and state.window_s == 0.0 and state.speed_m_s is None


def test_touchdown_is_looked_for_after_the_link_cut() -> None:
    on_ground_first = [(0.0, 0.0, 0.0, 0.0), *FLIGHT[1:]]
    state = measure_touchdown(rec(on_ground_first, cut_s=1.0))
    assert state is not None and state.touchdown_from_start_m == pytest.approx(220.0)


def test_a_run_that_never_lands_has_no_touchdown() -> None:
    assert measure_touchdown(rec(FLIGHT[:3])) is None


def test_a_recording_without_ground_truth_has_nothing_to_measure() -> None:
    assert measure_touchdown(Recording({}, [{"t_s": 1.0, "event": "position"}])) is None


def test_the_table_lists_each_recording_and_says_when_there_is_no_touchdown(tmp_path: Path) -> None:
    import json

    for name, samples in (("a-1", FLIGHT), ("b-1", FLIGHT[:3])):
        lines = [
            json.dumps({"t_s": 0.0, "event": "header", "schema": 1}),
            *(json.dumps(r) for r in truth(samples)),
        ]
        (tmp_path / f"{name}.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    out = table(tmp_path)
    assert "| a-1 | 220 | 220 | 30.0 | 2.0 |" in out
    assert "| b-1 | no touchdown |" in out


def test_main_prints_the_table(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main([str(tmp_path)]) == 0
    assert "| Recording |" in capsys.readouterr().out
