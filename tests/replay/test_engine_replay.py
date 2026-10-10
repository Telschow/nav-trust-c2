"""The trust engine over the committed recordings: NT-01 and NT-02.

Thresholds are the engine's default proposals. The numbers in the comments were measured on
these recordings (4 nominal runs, and one run each of off / wrong / stuck), so they describe
this data and are not guarantees. Startup (before the first GREEN) is excluded: the engine
starts STALE and needs the first fix plus the recovery hold.
"""

from collections.abc import Callable
from pathlib import Path

import pytest

from navtrust.calibration import GREEN_BOUND
from navtrust.engine import TrustEngine
from navtrust.recording import Recording, load_recording
from navtrust.replay import replay_engine
from navtrust.types import NavTrust, ReasonCode, TrustState

DATA = Path(__file__).parent / "data"


def run(name: str) -> tuple[Recording, list[NavTrust]]:
    rec = load_recording(DATA / f"{name}.jsonl")
    return rec, replay_engine(rec, TrustEngine("uav1"))


def first_after(out: list[NavTrust], t_s: float, pred: Callable[[NavTrust], bool]) -> float | None:
    return next((o.stamp_s for o in out if o.stamp_s >= t_s and pred(o)), None)


@pytest.mark.parametrize("name", ["nominal-1", "nominal-2", "nominal-3", "nominal-4"])
def test_nt02_nominal_never_leaves_green_after_startup(name: str) -> None:
    _, out = run(name)
    started = next(o.stamp_s for o in out if o.state is TrustState.GREEN)
    assert started <= 8.0  # measured 5.0 to 6.5 s
    assert [o for o in out if o.stamp_s > started and o.state is not TrustState.GREEN] == []


def test_nt01_total_gnss_loss_is_amber_with_a_loss_reason_within_two_seconds() -> None:
    rec, out = run("jamming_zone-1")
    crossings = list(zip(rec.of("gnss_enter"), rec.of("gnss_exit"), strict=True))
    assert len(crossings) == 4
    for enter, _ in crossings:
        t = first_after(out, enter["t_s"], lambda o: o.state is not TrustState.GREEN)
        assert t is not None and t - enter["t_s"] <= 2.0  # measured 1.02 to 1.24 s
        at = next(o for o in out if o.stamp_s == t)
        assert (at.state, at.reason) == (TrustState.AMBER, ReasonCode.GNSS_LOSS)
        assert at.confidence == 0.0 and at.headroom == 0.0  # no claim outside GREEN


def test_long_loss_escalates_to_red_and_short_loss_does_not() -> None:
    rec, out = run("jamming_zone-1")
    crossings = list(zip(rec.of("gnss_enter"), rec.of("gnss_exit"), strict=True))
    for enter, leave in crossings:
        outage = leave["t_s"] - enter["t_s"]
        red = first_after(out, enter["t_s"], lambda o: o.state is TrustState.RED)
        if outage < 5.0:
            assert red is None or red > leave["t_s"] + 1
        else:
            assert red is not None and 5.0 <= red - enter["t_s"] <= 7.0  # measured 6.24 s


def test_green_returns_after_gnss_comes_back() -> None:
    rec, out = run("jamming_zone-1")
    for leave in rec.of("gnss_exit"):
        t = first_after(out, leave["t_s"], lambda o: o.state is TrustState.GREEN)
        assert t is not None and 2.0 <= t - leave["t_s"] <= 3.0  # measured 2.03 to 2.40 s


def test_wrong_fix_is_amber_never_red() -> None:
    rec, out = run("wrong_zone-1")
    for enter in rec.of("gnss_enter"):
        t = first_after(out, enter["t_s"], lambda o: o.state is not TrustState.GREEN)
        assert t is not None and t - enter["t_s"] <= 2.0  # measured 0.20 to 0.35 s
    assert TrustState.RED not in {o.state for o in out}


def test_stuck_position_is_red_with_the_consistency_reason() -> None:
    rec, out = run("stuck_zone-1")
    fault = rec.first("gnss_enter")
    assert fault is not None
    t = first_after(out, fault["t_s"], lambda o: o.state is TrustState.RED)
    assert t is not None and 0 < t - fault["t_s"] <= 5.0  # measured 3.31 s
    after = [o for o in out if o.stamp_s >= t]
    assert {(o.state, o.reason) for o in after} == {
        (TrustState.RED, ReasonCode.INCONSISTENT_INNOVATION)
    }


def test_bound_is_only_given_in_green() -> None:
    for name in ("nominal-1", "jamming_zone-1", "stuck_zone-1"):
        _, out = run(name)
        for o in out:
            if o.state is TrustState.GREEN:
                assert o.horizontal_bound_m == GREEN_BOUND.bound_m
                assert o.confidence == GREEN_BOUND.coverage
            else:
                assert o.horizontal_bound_m == float("inf")
                assert o.confidence == 0.0 and o.headroom == 0.0
