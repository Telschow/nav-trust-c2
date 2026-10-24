"""Time from a link cut to PX4's reaction and to touchdown, on recordings built by hand."""

from collections.abc import Mapping, Sequence

from eval.link_cut_timing import measure_link_cut
from navtrust.recording import Recording


def rec(
    events: Sequence[tuple[float, str, Mapping[str, object]]], touchdown_s: float | None
) -> Recording:
    records: list[dict[str, object]] = [{"t_s": t, "event": e, **f} for t, e, f in events]
    for i in range(0, 200):
        t = i * 1.0
        landed = touchdown_s is not None and t >= touchdown_s
        records.append({"t_s": t, "event": "truth", "alt_m": 0.0 if landed else 30.0})
    records.sort(key=lambda r: float(str(r["t_s"])))
    return Recording({}, records)


MODES = [
    (5.0, "flight_mode", {"mode": "MISSION"}),
    (40.0, "link_cut", {}),
    (50.0, "flight_mode", {"mode": "HOLD"}),
    (55.0, "flight_mode", {"mode": "RETURN_TO_LAUNCH"}),
]


def test_it_lists_each_mode_change_after_the_cut_and_the_touchdown() -> None:
    timing = measure_link_cut(rec(MODES, touchdown_s=120.0))
    assert timing is not None
    assert timing.cut_s == 40.0
    assert timing.mode_changes == [("HOLD", 10.0), ("RETURN_TO_LAUNCH", 15.0)]
    assert timing.touchdown_after_s == 80.0


def test_a_run_that_never_lands_has_no_touchdown() -> None:
    timing = measure_link_cut(rec(MODES, touchdown_s=None))
    assert timing is not None and timing.touchdown_after_s is None


def test_modes_before_the_cut_are_not_a_reaction() -> None:
    events = [(5.0, "flight_mode", {"mode": "HOLD"}), (40.0, "link_cut", {})]
    timing = measure_link_cut(rec(events, touchdown_s=None))
    assert timing is not None and timing.mode_changes == []


def test_a_recording_without_a_cut_has_nothing_to_measure() -> None:
    assert measure_link_cut(rec([(5.0, "flight_mode", {"mode": "MISSION"})], None)) is None
