import math

import pytest

from navtrust.calibration import GREEN_BOUND
from navtrust.engine import EngineConfig, TrustEngine
from navtrust.types import ReasonCode, TrustState


def good(e: TrustEngine, t: float, pos: float = 0.05, vel: float = 0.05) -> None:
    e.update_estimator(t, 0.15, pos, vel)


def start_green(e: TrustEngine) -> float:
    """Feed a healthy vehicle until it reports GREEN; returns the time reached."""
    e.update_fix(0.0, "FIX_3D")
    t = 0.0
    while e.report(t).state is not TrustState.GREEN:
        t += 1.0
        good(e, t)
        assert t < 20
    return t


def test_silent_input_is_stale_and_unknown_bound() -> None:
    out = TrustEngine("uav1").report(0.0)
    assert (out.state, out.reason) == (TrustState.AMBER, ReasonCode.STALE)
    assert math.isinf(out.horizontal_bound_m) and out.vehicle_id == "uav1"


def test_healthy_vehicle_is_green_with_a_bound_and_no_reason() -> None:
    e = TrustEngine("uav1")
    t = start_green(e)
    out = e.report(t)
    cal = GREEN_BOUND
    assert (out.state, out.reason) == (TrustState.GREEN, None)
    assert (out.horizontal_bound_m, out.confidence) == (cal.bound_m, cal.coverage)
    assert 0.0 < out.headroom <= 1.0


def test_loss_is_amber_then_red_after_red_after_s() -> None:
    e = TrustEngine("uav1", EngineConfig(red_after_s=5.0))
    t = start_green(e)
    e.update_fix(t + 1, "NO_GPS")
    good(e, t + 1)
    assert e.report(t + 1).state is TrustState.AMBER
    for dt in range(2, 6):
        good(e, t + dt)
        assert e.report(t + dt).state is TrustState.AMBER
    good(e, t + 6)
    out = e.report(t + 6)
    assert (out.state, out.reason) == (TrustState.RED, ReasonCode.GNSS_LOSS)


def test_degraded_fix_stays_amber_and_never_escalates() -> None:
    e = TrustEngine("uav1", EngineConfig(red_after_s=5.0))
    t = start_green(e)
    e.update_fix(t + 1, "FIX_2D")
    for dt in range(1, 30):
        good(e, t + dt)
    out = e.report(t + 29)
    assert (out.state, out.reason) == (TrustState.AMBER, ReasonCode.GNSS_LOSS)


def test_inconsistency_is_red_at_once_with_its_own_reason() -> None:
    e = TrustEngine("uav1")
    t = start_green(e)
    for dt in range(1, 5):
        good(e, t + dt, pos=2.0, vel=0.1)
    out = e.report(t + 4)
    assert (out.state, out.reason) == (TrustState.RED, ReasonCode.INCONSISTENT_INNOVATION)
    assert math.isinf(out.horizontal_bound_m) and out.confidence == 0.0


def test_loss_wins_the_reason_code_over_inconsistency_and_state_is_the_worst() -> None:
    e = TrustEngine("uav1")
    t = start_green(e)
    e.update_fix(t + 1, "NO_GPS")
    for dt in range(1, 5):
        good(e, t + dt, pos=2.0, vel=0.1)
    out = e.report(t + 4)
    assert out.reason is ReasonCode.GNSS_LOSS  # loss precedence (ADR 0001)
    assert out.state is TrustState.RED  # inconsistency alone already makes it RED


def test_recovery_goes_back_to_green_only_after_the_detector_holds() -> None:
    e = TrustEngine("uav1")
    t = start_green(e)
    e.update_fix(t + 1, "NO_GPS")
    good(e, t + 1)
    e.report(t + 1)
    e.update_fix(t + 3, "FIX_3D")
    good(e, t + 3)
    assert e.report(t + 3).state is TrustState.AMBER
    good(e, t + 5)
    assert e.report(t + 5).state is TrustState.GREEN


def test_every_state_produces_a_valid_navtrust() -> None:
    e = TrustEngine("uav1")
    t = start_green(e)
    e.update_fix(t + 1, "NO_GPS")
    for dt in range(1, 12):
        good(e, t + dt)
        out = e.report(t + dt)
        assert out.horizontal_bound_m >= 0 and 0.0 <= out.confidence <= 1.0


def test_config_validation() -> None:
    with pytest.raises(ValueError):
        EngineConfig(red_after_s=-1)


def test_recovery_hold_is_not_counted_as_outage_time() -> None:
    """Regression: a 4 s outage plus the 2 s recovery hold used to reach red_after_s = 5 s
    and show RED after the fix was already back."""
    e = TrustEngine("uav1", EngineConfig(red_after_s=5.0))
    t = start_green(e)
    e.update_fix(t + 1, "NO_GPS")
    for dt in range(1, 5):
        good(e, t + dt)
        e.report(t + dt)
    e.update_fix(t + 5, "FIX_3D")  # outage lasted 4 s
    states = []
    for tenth in range(50, 80, 5):
        good(e, t + tenth / 10)
        states.append(e.report(t + tenth / 10).state)
    assert TrustState.RED not in states
    assert states[-1] is TrustState.GREEN


def test_a_long_stale_start_still_escalates_but_data_arriving_does_not() -> None:
    e = TrustEngine("uav1", EngineConfig(red_after_s=5.0))
    e.report(0.0)
    assert e.report(6.0).state is TrustState.RED  # nothing ever arrived
    e2 = TrustEngine("uav1", EngineConfig(red_after_s=5.0))
    e2.report(0.0)
    e2.update_fix(3.8, "FIX_3D")
    good(e2, 3.8)
    e2.report(3.8)
    good(e2, 5.0)
    assert e2.report(5.0).state is TrustState.AMBER  # data is flowing, only the hold remains


def test_headroom_shrinks_as_the_test_ratio_nears_the_estimators_gate() -> None:
    def headroom(ratio: float) -> float:
        e = TrustEngine("uav1")
        t = start_green(e)
        for dt in range(1, 4):
            good(e, t + dt, pos=ratio, vel=ratio)
        out = e.report(t + 3)
        assert out.state is TrustState.GREEN
        return out.headroom

    assert headroom(0.05) == pytest.approx(0.95, abs=0.01)
    assert headroom(0.5) == pytest.approx(0.5, abs=0.01)
    assert headroom(0.9) == pytest.approx(0.1, abs=0.01)
    assert headroom(0.05) > headroom(0.5) > headroom(0.9)


def test_headroom_shrinks_when_inputs_go_quiet_but_not_at_the_normal_one_second_cadence() -> None:
    e = TrustEngine("uav1", EngineConfig())
    t = start_green(e)
    for dt in range(1, 4):
        good(e, t + dt)
    assert e.report(t + 3.9).headroom == pytest.approx(0.95, abs=0.01)  # 0.9 s since the last input
    quiet = e.report(
        t + 3 + 2.25
    )  # 2.25 s of silence: halfway between the grace and the stale limit
    assert quiet.state is TrustState.GREEN
    assert quiet.headroom == pytest.approx(0.5, abs=0.05)


def test_headroom_and_confidence_are_zero_and_the_bound_unknown_outside_green() -> None:
    e = TrustEngine("uav1")
    t = start_green(e)
    e.update_fix(t + 1, "NO_GPS")
    good(e, t + 1)
    out = e.report(t + 1)
    assert out.state is TrustState.AMBER
    assert (out.headroom, out.confidence) == (0.0, 0.0) and math.isinf(out.horizontal_bound_m)


def test_headroom_must_be_a_fraction() -> None:
    from navtrust.types import NavTrust

    with pytest.raises(ValueError):
        NavTrust("u", 0.0, TrustState.GREEN, None, 3.0, 0.99, headroom=1.5)
