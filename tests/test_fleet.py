import pytest

pytest.importorskip("mavsdk_grpc")

from c2.allocator import assign, split_area  # noqa: E402
from sim.fly_fleet import parse_args, sector_route, vehicle_ids  # noqa: E402
from sim.fly_survey import plan_from_route  # noqa: E402
from sim.survey import GeoPoint  # noqa: E402


def test_each_vehicle_route_stays_inside_its_own_sector() -> None:
    sectors = split_area(1000, 1000, 3)
    assignment = assign(sectors, vehicle_ids(3))
    for secs in assignment.values():
        for s in secs:
            route = sector_route(s, 100)
            assert all(
                s.west <= p.east_m <= s.east and s.south <= p.north_m <= s.north + 1e-9
                for p in route
            )
            assert min(p.north_m for p in route) == pytest.approx(s.south)
            assert max(p.north_m for p in route) == pytest.approx(s.north)


def test_routes_of_different_vehicles_do_not_overlap() -> None:
    sectors = split_area(1000, 1000, 3)
    ranges = [
        (min(p.north_m for p in sector_route(s, 100)), max(p.north_m for p in sector_route(s, 100)))
        for s in sectors
    ]
    assert all(a[1] <= b[0] + 1e-9 for a, b in zip(ranges, ranges[1:], strict=False))


def test_plan_from_route_has_one_item_per_point() -> None:
    route = sector_route(split_area(1000, 1000, 3)[1], 100)
    plan = plan_from_route(GeoPoint(47.0, 8.0), route, 35.0, 10.0)
    assert len(plan.mission_items) == len(route) == 10
    assert {i.relative_altitude_m for i in plan.mission_items} == {35.0}


def test_defaults() -> None:
    args = parse_args([])
    assert (args.vehicles, args.width, args.height) == (3, 1000.0, 1000.0)
    assert vehicle_ids(3) == ["uav1", "uav2", "uav3"]
