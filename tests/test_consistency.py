import pytest

from navtrust.consistency import (
    Consistency,
    ConsistencyConfig,
    ConsistencyDetector,
)


def feed(d: ConsistencyDetector, samples: list[tuple[float, float | None, float | None]]) -> None:
    for t, pos, vel in samples:
        d.update(t, pos, vel)


def test_too_few_samples_is_unknown() -> None:
    d = ConsistencyDetector()
    feed(d, [(0.0, 0.1, 0.1), (1.0, 0.1, 0.1)])
    r = d.report(1.0)
    assert r.status is Consistency.UNKNOWN and r.fraction_above is None and r.samples == 2


def test_low_ratios_are_consistent() -> None:
    d = ConsistencyDetector()
    feed(d, [(float(t), 0.05, 0.1) for t in range(6)])
    r = d.report(5.0)
    assert r.status is Consistency.CONSISTENT and r.max_ratio == 0.1 and r.fraction_above == 0.0


def test_statistic_is_the_larger_of_the_two_ratios() -> None:
    d = ConsistencyDetector()
    feed(d, [(float(t), 0.1, 1.5) for t in range(4)])
    assert d.report(3.0).status is Consistency.INCONSISTENT


def test_missing_ratio_is_ignored_and_a_sample_with_neither_is_skipped() -> None:
    d = ConsistencyDetector()
    feed(d, [(0.0, 1.5, None), (1.0, None, 1.5), (2.0, None, None), (3.0, 1.5, None)])
    r = d.report(3.0)
    assert r.samples == 3 and r.status is Consistency.INCONSISTENT


def test_a_single_spike_does_not_flag() -> None:
    d = ConsistencyDetector()
    feed(d, [(0.0, 0.1, 0.1), (1.0, 2.0, 0.1), (2.0, 0.1, 0.1), (3.0, 0.1, 0.1), (4.0, 0.1, 0.1)])
    assert d.report(4.0).status is Consistency.CONSISTENT


def test_hysteresis_holds_the_flag_until_the_share_falls_to_clear_fraction() -> None:
    cfg = ConsistencyConfig(window_s=10.0, enter_fraction=0.5, clear_fraction=0.2)
    d = ConsistencyDetector(cfg)
    # 4 high of 8 -> flag; then good samples dilute: 4 of 10 = 0.4 still flagged, 4 of 20 clears
    for t in range(4):
        d.update(float(t), 0.1, 0.1)
    for t in range(4, 8):
        d.update(float(t), 2.0, 0.1)
    assert d.report(7.0).status is Consistency.INCONSISTENT
    for t in range(8, 10):
        d.update(float(t), 0.1, 0.1)
    assert d.report(9.0).fraction_above == pytest.approx(0.4)
    assert d.report(9.0).status is Consistency.INCONSISTENT
    # the high samples age out of the 10 s window
    for t in range(10, 17):
        d.update(float(t), 0.1, 0.1)
    assert d.report(16.0).status is Consistency.CONSISTENT


def test_old_samples_leave_the_window() -> None:
    d = ConsistencyDetector(ConsistencyConfig(window_s=5.0))
    feed(d, [(float(t), 2.0, 2.0) for t in range(4)])
    assert d.report(3.0).status is Consistency.INCONSISTENT
    assert d.report(30.0).status is Consistency.UNKNOWN


def test_validation() -> None:
    with pytest.raises(ValueError):
        ConsistencyConfig(enter_fraction=0.2, clear_fraction=0.5)
    with pytest.raises(ValueError):
        ConsistencyConfig(window_s=0)
    d = ConsistencyDetector()
    with pytest.raises(ValueError):
        d.update(0.0, -0.1, None)
    d.update(5.0, 0.1, 0.1)
    with pytest.raises(ValueError):
        d.update(4.0, 0.1, 0.1)
