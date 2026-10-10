import pytest

pytest.importorskip("httpx")
pytest.importorskip("mavsdk_grpc")

from navtrust.engine import TrustEngine  # noqa: E402
from navtrust.recording import load_recording  # noqa: E402
from navtrust.replay import replay_engine  # noqa: E402
from navtrust.types import TrustState  # noqa: E402
from sim.demo_feed import (  # noqa: E402
    DATA,  # noqa: E402
    TRUST_SOURCE,
    RouteWalker,
    trust_at,
)
from sim.survey import LocalPoint  # noqa: E402


def test_walker_follows_the_route_and_stops_at_the_end() -> None:
    w = RouteWalker(LocalPoint(0, 0), [LocalPoint(10, 0), LocalPoint(10, 10)])
    p = w.advance(5)
    assert (p.east_m, p.north_m) == (5, 0) and not w.finished
    p = w.advance(10)  # 5 m to the corner, then 5 m up
    assert (p.east_m, p.north_m) == (10, 5)
    w.advance(100)
    assert w.finished and (w.position.east_m, w.position.north_m) == (10, 10)


def test_frozen_walker_does_not_move_and_can_be_extended() -> None:
    w = RouteWalker(LocalPoint(0, 0), [LocalPoint(10, 0)])
    w.frozen = True
    assert w.advance(5) == LocalPoint(0, 0)
    w.frozen = False
    w.extend([LocalPoint(10, 10)])
    w.advance(100)
    assert (w.position.east_m, w.position.north_m) == (10, 10)


def test_trust_source_has_the_stuck_run_turn_red_and_the_others_stay_green() -> None:
    final = {}
    for vehicle, name in TRUST_SOURCE.items():
        reports = replay_engine(load_recording(DATA / f"{name}.jsonl"), TrustEngine(vehicle))
        final[vehicle] = trust_at(reports, 1e9).state
        assert trust_at(reports, 0.0) is reports[0]
    assert final == {"uav1": TrustState.GREEN, "uav2": TrustState.RED, "uav3": TrustState.GREEN}
