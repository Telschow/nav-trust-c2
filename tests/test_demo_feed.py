import pytest

pytest.importorskip("httpx")
pytest.importorskip("mavsdk_grpc")

from c2.allocator import assign, split_area  # noqa: E402
from c2.fleet import FleetState  # noqa: E402
from c2.recommender import Recommender  # noqa: E402
from navtrust.engine import TrustEngine  # noqa: E402
from navtrust.recording import load_recording  # noqa: E402
from navtrust.replay import replay_engine  # noqa: E402
from navtrust.types import NavTrust, ReasonCode, TrustState  # noqa: E402
from sim.demo_feed import RouteWalker, scenario_plan, stop_time, trust_at  # noqa: E402
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


def final_trust(vehicle: str, path: object) -> NavTrust:
    reports = replay_engine(load_recording(path), TrustEngine(vehicle))  # type: ignore[arg-type]
    assert trust_at(reports, 0.0) is reports[0]
    return trust_at(reports, 1e9)


STUCK = {"uav2": ReasonCode.INCONSISTENT_INNOVATION}
OUTAGE = {"uav3": ReasonCode.GNSS_LOSS}


@pytest.mark.parametrize(
    ("scenario", "faulted"),
    [("stuck", STUCK), ("outage", OUTAGE), ("both", {**STUCK, **OUTAGE})],
)
def test_each_scenario_faults_exactly_the_vehicles_it_names(
    scenario: str, faulted: dict[str, ReasonCode]
) -> None:
    plan = scenario_plan(scenario)
    assert set(plan) == {"uav1", "uav2", "uav3"}
    for vehicle, script in plan.items():
        last = final_trust(vehicle, script.recording)
        if vehicle in faulted:
            assert (last.state, last.reason) == (TrustState.RED, faulted[vehicle])
            assert script.stops_at_s is not None and script.stops_at_s > 0
        else:
            assert last.state is TrustState.GREEN and script.stops_at_s is None


def test_a_vehicle_stops_when_its_position_freezes_or_when_it_lands() -> None:
    plan = scenario_plan("both")
    stuck = load_recording(plan["uav2"].recording)
    outage = load_recording(plan["uav3"].recording)
    fault_stuck = stuck.first("gnss_enter")
    fault_outage = outage.first("gnss_enter")
    assert fault_stuck is not None and fault_outage is not None
    assert plan["uav2"].stops_at_s == fault_stuck["t_s"]  # frozen at once
    landed = plan["uav3"].stops_at_s
    assert landed is not None and landed > fault_outage["t_s"] + 20  # PX4 flies on, then lands
    assert stop_time(outage, "land") == landed


def test_stop_time_needs_a_fault_and_a_known_kind() -> None:
    nominal = load_recording(scenario_plan("stuck")["uav1"].recording)
    with pytest.raises(ValueError, match="no fault"):
        stop_time(nominal, "freeze")
    with pytest.raises(ValueError, match="unknown stop kind"):
        stop_time(load_recording(scenario_plan("stuck")["uav2"].recording), "float")
    with pytest.raises(ValueError, match="unknown scenario"):
        scenario_plan("nope")


def test_the_outage_scenario_recommends_a_re_task_only_and_the_stuck_one_a_landing() -> None:
    def first_recommendation(scenario: str, vehicle: str):  # type: ignore[no-untyped-def]
        now = [0.0]
        recommender = Recommender(lambda: now[0])
        fleet = FleetState(
            assign(split_area(900, 900, 3), ["uav1", "uav2", "uav3"]),
            positions={"uav1": (0.0, 0.0), "uav2": (0.0, 5.0), "uav3": (0.0, 10.0)},
        )
        for v in ("uav1", "uav2", "uav3"):
            if v != vehicle:
                recommender.observe(NavTrust(v, 0.0, TrustState.GREEN, None, 0.15, 1.0), fleet)
        reports = replay_engine(
            load_recording(scenario_plan(scenario)[vehicle].recording), TrustEngine(vehicle)
        )
        for r in reports:
            now[0] = r.stamp_s
            if recs := recommender.observe(r, fleet):
                return recs[0]
        return None

    outage = first_recommendation("outage", "uav3")
    assert outage is not None and outage.command is None and outage.reason is ReasonCode.GNSS_LOSS
    assert [m.sector_id for m in outage.sector_moves] == ["S3"]
    stuck = first_recommendation("stuck", "uav2")
    assert stuck is not None and stuck.command is not None and stuck.command.value == "LAND"
