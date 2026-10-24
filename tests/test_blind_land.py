"""Time from GNSS loss to a controlled descent, on small recordings built by hand."""

from pathlib import Path

from eval.blind_land import measure_outages
from navtrust.recording import Recording, load_recording

ROOT = Path(__file__).resolve().parent.parent

CRUISE_M = 30.0
DESCENT_M_S = 0.75


def rec(
    outage: tuple[float, float | None],
    descent_from_s: float | None,
    end_s: float = 100.0,
) -> Recording:
    """Level flight at 30 m; a GNSS outage; a steady descent from `descent_from_s` if given."""
    records: list[dict[str, object]] = [{"event": "gnss_enter", "t_s": outage[0]}]
    if outage[1] is not None:
        records.append({"event": "gnss_exit", "t_s": outage[1]})
    t = 0.0
    while t <= end_s:
        alt = CRUISE_M
        if descent_from_s is not None and t > descent_from_s:
            alt = max(-0.013, CRUISE_M - DESCENT_M_S * (t - descent_from_s))
        records.append({"event": "truth", "t_s": t, "alt_m": alt})
        t = round(t + 0.5, 3)
    records.sort(key=lambda r: float(str(r["t_s"])))
    return Recording({"survey": {"altitude_m": CRUISE_M}}, records)


def test_a_descent_after_gnss_loss_gives_onset_and_touchdown() -> None:
    # GNSS lost at 10 s, descent starts 6 s later and takes 30 / 0.75 = 40 s
    [outage] = measure_outages(rec(outage=(10.0, None), descent_from_s=16.0))
    assert outage.descended is True
    assert outage.duration_s is None  # never cleared
    assert outage.descent_onset_s is not None and 5.5 <= outage.descent_onset_s <= 6.5
    assert outage.touchdown_s is not None and 45.5 <= outage.touchdown_s <= 46.5


def test_a_recording_that_ends_mid_descent_has_no_touchdown() -> None:
    [outage] = measure_outages(rec(outage=(10.0, None), descent_from_s=16.0, end_s=30.0))
    assert outage.descended is True
    assert outage.touchdown_s is None


def test_the_normal_landing_long_after_a_short_outage_is_not_a_reaction() -> None:
    # GNSS back after 4 s; the mission-end landing starts a minute later
    [outage] = measure_outages(rec(outage=(10.0, 14.0), descent_from_s=70.0))
    assert outage.descended is False
    assert outage.descent_onset_s is None and outage.touchdown_s is None
    assert outage.duration_s == 4.0


def test_a_descent_that_outlasts_a_short_outage_by_a_few_seconds_counts() -> None:
    # PX4 can react after GNSS has already returned
    [outage] = measure_outages(rec(outage=(10.0, 14.0), descent_from_s=18.0))
    assert outage.descended is True
    assert outage.descent_onset_s is not None and 7.5 <= outage.descent_onset_s <= 8.5


def test_a_run_without_an_outage_has_nothing_to_measure() -> None:
    records = [{"event": "truth", "t_s": 0.0, "alt_m": CRUISE_M}]
    assert measure_outages(Recording({"survey": {"altitude_m": CRUISE_M}}, records)) == []


def committed(prefix: str) -> list[Recording]:
    paths = sorted((ROOT / "eval" / "recordings").glob(f"{prefix}-*.jsonl"))
    assert paths, f"no committed {prefix} recordings"
    return [load_recording(p) for p in paths]


def test_both_long_gnss_outages_end_in_a_controlled_descent() -> None:
    # read off the ground-truth altitude by hand: level until about +5 s, then about 0.75 m/s down
    for recording in committed("long_outage"):
        [outage] = measure_outages(recording)
        assert outage.descended is True and outage.duration_s is None
        assert outage.descent_onset_s is not None and 4.5 <= outage.descent_onset_s <= 7.5
        assert outage.touchdown_s is not None and 43.0 <= outage.touchdown_s <= 49.0


def test_none_of_the_six_four_second_gnss_outages_made_the_vehicle_descend() -> None:
    outages = [o for recording in committed("short_outage") for o in measure_outages(recording)]
    assert len(outages) == 6
    for outage in outages:
        assert outage.duration_s is not None and 3.9 <= outage.duration_s <= 4.1
        assert outage.descended is False


def test_a_nominal_run_has_no_outage() -> None:
    assert all(measure_outages(recording) == [] for recording in committed("nominal"))
