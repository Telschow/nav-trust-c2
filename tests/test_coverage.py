from eval.coverage import area_coverage
from navtrust.recording import Recording


def rec(
    points: list[tuple[float, float, float]], width: float = 200.0, height: float = 100.0
) -> Recording:
    header = {"survey": {"width_m": width, "height_m": height, "spacing_m": 100.0}}
    truth = [
        {"event": "truth", "t_s": i * 0.5, "east_m": e, "north_m": n, "alt_m": a}
        for i, (e, n, a) in enumerate(points)
    ]
    return Recording(header, truth)


def line(
    east_to: float, north: float = 50.0, step: float = 5.0
) -> list[tuple[float, float, float]]:
    n = int(east_to / step)
    return [(i * step, north, 30.0) for i in range(n + 1)]


def test_full_pass_covers_everything() -> None:
    assert area_coverage(rec(line(200.0))) == 1.0


def test_half_a_pass_covers_about_half() -> None:
    covered = area_coverage(rec(line(100.0)))
    assert covered is not None and 0.5 <= covered <= 0.8  # the swath reaches past the last point


def test_ground_samples_do_not_count() -> None:
    assert area_coverage(rec([(0.0, 50.0, 0.0), (200.0, 50.0, 1.0)])) is None


def test_far_away_flight_covers_nothing() -> None:
    assert area_coverage(rec(line(200.0, north=1000.0))) == 0.0


def test_no_truth_means_none() -> None:
    assert (
        area_coverage(Recording({"survey": {"width_m": 1, "height_m": 1, "spacing_m": 1}}, []))
        is None
    )
