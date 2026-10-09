import pytest

from navtrust.availability import (
    Availability,
    AvailabilityConfig,
    AvailabilityDetector,
    classify_fix,
)

CFG = AvailabilityConfig(stale_after_s=3.0, recover_after_s=2.0)


def make() -> AvailabilityDetector:
    return AvailabilityDetector(CFG)


def test_no_input_is_stale() -> None:
    assert make().report(0.0).status is Availability.STALE


@pytest.mark.parametrize(
    ("fix", "expected"),
    [
        ("FIX_3D", Availability.OK),
        ("RTK_FIXED", Availability.OK),
        ("FIX_2D", Availability.DEGRADED),
        ("NO_FIX", Availability.LOST),
        ("NO_GPS", Availability.LOST),
    ],
)
def test_fix_classification(fix: str, expected: Availability) -> None:
    assert classify_fix(fix) is expected


def test_unknown_fix_type_is_an_error() -> None:
    with pytest.raises(ValueError):
        classify_fix("FIX_4D")


def test_loss_is_reported_immediately() -> None:
    d = make()
    d.update_fix(0.0, "FIX_3D")
    d.update_estimator(0.0, 0.15)
    for t in (0.0, 1.0, 2.0, 3.0):
        d.report(t)
    d.update_fix(4.0, "NO_GPS")
    d.update_estimator(4.0, 0.2)
    assert d.report(4.0).status is Availability.LOST


def test_recovery_needs_the_fix_to_look_good_for_recover_after_s() -> None:
    d = make()
    d.update_fix(0.0, "NO_GPS")
    d.update_estimator(0.0, 0.5)
    assert d.report(0.0).status is Availability.LOST
    d.update_fix(10.0, "FIX_3D")
    d.update_estimator(10.0, 0.2)
    assert d.report(10.0).status is Availability.LOST
    d.update_estimator(11.0, 0.2)
    assert d.report(11.0).status is Availability.LOST
    d.update_estimator(12.0, 0.2)
    assert d.report(12.0).status is Availability.OK


def test_a_relapse_during_recovery_restarts_the_hold() -> None:
    d = make()
    d.update_fix(0.0, "NO_GPS")
    d.report(0.0)
    d.update_fix(10.0, "FIX_3D")
    d.report(10.0)
    d.update_fix(11.0, "NO_GPS")
    assert d.report(11.0).status is Availability.LOST
    d.update_fix(12.0, "FIX_3D")
    assert d.report(12.0).status is Availability.LOST
    d.update_estimator(13.5, 0.2)
    assert d.report(13.5).status is Availability.LOST
    d.update_estimator(14.0, 0.2)
    assert d.report(14.0).status is Availability.OK


def test_silence_becomes_stale_and_then_recovers_with_the_same_hold() -> None:
    d = make()
    d.update_fix(0.0, "FIX_3D")
    d.report(0.0)
    d.report(2.0)
    d.report(2.0 + CFG.recover_after_s)
    assert d.report(10.0).status is Availability.STALE
    d.update_estimator(10.5, 0.2)
    assert d.report(10.5).status is Availability.STALE


def test_since_s_counts_time_in_the_reported_status() -> None:
    d = make()
    d.update_fix(0.0, "NO_GPS")
    d.update_estimator(0.0, 0.5)
    assert d.report(0.0).since_s == 0.0
    d.update_estimator(1.0, 0.5)
    d.update_estimator(2.0, 0.5)
    assert d.report(2.5).since_s == pytest.approx(2.5)


def test_bound_is_the_last_estimator_accuracy() -> None:
    d = make()
    d.update_fix(0.0, "FIX_3D")
    assert d.report(0.0).horizontal_bound_m is None
    d.update_estimator(1.0, 0.15)
    d.update_estimator(2.0, None)  # missing field keeps the previous value
    assert d.report(2.0).horizontal_bound_m == 0.15


def test_inputs_must_be_in_time_order() -> None:
    d = make()
    d.update_fix(5.0, "FIX_3D")
    with pytest.raises(ValueError):
        d.update_fix(4.0, "FIX_3D")


def test_config_is_validated() -> None:
    with pytest.raises(ValueError):
        AvailabilityConfig(stale_after_s=0)


def test_recovering_flag_marks_the_hold_after_the_fix_returns() -> None:
    d = make()
    d.update_fix(0.0, "NO_GPS")
    d.update_estimator(0.0, 0.5)
    assert not d.report(0.0).recovering
    d.update_fix(10.0, "FIX_3D")
    d.update_estimator(10.0, 0.2)
    assert d.report(10.0).recovering and d.report(10.0).status is Availability.LOST
    d.update_estimator(12.0, 0.2)
    out = d.report(12.0)
    assert out.status is Availability.OK and not out.recovering
