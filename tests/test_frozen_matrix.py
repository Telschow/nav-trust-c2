"""Issue 81: the frozen-position matrix is summarised from ground truth, as counts and ranges."""

from typing import Any

from eval.frozen_matrix import CONTROLLED_SPEED_M_S, Cell, measure_run, summarise
from navtrust.recording import Recording


def truth(t: float, alt: float, east: float = 0.0) -> dict[str, Any]:
    return {"t_s": t, "event": "truth", "vehicle": "uav1", "east_m": east, "north_m": 0.0,
            "alt_m": alt, "sim_s": t}  # fmt: skip


def recording(
    action: str,
    speed: float,
    delay: float,
    samples: list[tuple[float, float, float]],
    fault_s: float = 10.0,
) -> Recording:
    """samples: (t_s, alt_m, east_m). The operator acts `delay` s after the fault."""
    header: dict[str, Any] = {
        "t_s": 0.0, "event": "header", "schema": 1, "survey": {"speed_m_s": speed},
        "operator_action": None if action == "none" else {"action": action, "delay_s": delay},
    }  # fmt: skip
    records: list[dict[str, Any]] = [
        {"t_s": fault_s, "event": "gnss_enter", "east_m": 0.0, "north_m": 0.0}
    ]
    if action != "none":
        records.append({"t_s": fault_s + delay, "event": "operator_action", "action": action})
    records += [truth(t, alt, east) for t, alt, east in samples]
    records.sort(key=lambda r: r["t_s"])
    return Recording(header=header, records=records)


# climbs, cruises at 30 m, then comes down: slowly (controlled) or fast and far (not)
GENTLE: list[tuple[float, float, float]] = [
    (1, 0, 0),
    (5, 30, 10),
    (20, 30, 50),
    (30, 3, 55),
    (32, 0.2, 57),
]
HARD: list[tuple[float, float, float]] = [
    (1, 0, 0),
    (5, 30, 10),
    (20, 30, 50),
    (40, 3, 400),
    (41, 0.2, 430),
]
FLYING: list[tuple[float, float, float]] = [(1, 0, 0), (5, 30, 10), (60, 30, 900), (200, 28, 5000)]


def test_a_gentle_landing_is_controlled_and_timed_from_the_command() -> None:
    run = measure_run(recording("land", 5, 5, GENTLE))
    assert (run.action, run.speed, run.delay) == ("land", 5.0, 5.0)
    assert run.landed and run.touchdown_speed_m_s is not None
    assert run.touchdown_speed_m_s <= CONTROLLED_SPEED_M_S and run.controlled
    assert run.command_to_touchdown_s == 17.0  # command at 15 s, down at 32 s
    assert run.farthest_m == 57.0


def test_a_fast_touchdown_is_not_controlled() -> None:
    run = measure_run(recording("hold", 12, 30, HARD, fault_s=0.5))
    assert run.landed and not run.controlled
    assert run.touchdown_speed_m_s is not None and run.touchdown_speed_m_s > CONTROLLED_SPEED_M_S


def test_a_vehicle_still_flying_at_the_end_has_not_landed() -> None:
    run = measure_run(recording("none", 5, 5, FLYING))
    assert not run.landed and not run.controlled
    assert run.command_to_touchdown_s is None and run.touchdown_speed_m_s is None
    assert run.farthest_m == 5000.0


def test_cells_report_counts_and_ranges_never_rates() -> None:
    runs = [
        measure_run(recording("land", 5, 5, GENTLE)),
        measure_run(recording("land", 5, 5, GENTLE)),
        measure_run(recording("land", 5, 5, HARD, fault_s=0.5)),
        measure_run(recording("none", 5, 5, FLYING)),
    ]
    cells = summarise(runs)
    land = next(c for c in cells if c.action == "land")
    assert isinstance(land, Cell)
    assert (land.n, land.landed, land.controlled) == (3, 3, 2)
    assert land.farthest_m == (57.0, 430.0)
    none = next(c for c in cells if c.action == "none")
    assert (none.n, none.landed, none.controlled) == (1, 0, 0)


def test_the_results_note_shows_the_numbers_the_recordings_give() -> None:
    """Metrics are measured, never typed: the committed note must carry the generated tables."""
    from pathlib import Path

    from eval.frozen_matrix import table

    root = Path(__file__).resolve().parent.parent
    note = (root / "docs" / "validation" / "frozen-position-matrix.md").read_text(encoding="utf-8")
    generated = table(root / "tests" / "replay" / "data" / "experiments" / "matrix")
    for block in generated.split("\n\n"):
        assert block.strip() in note
