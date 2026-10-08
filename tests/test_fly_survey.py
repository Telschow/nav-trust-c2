import math

import pytest

pytest.importorskip("mavsdk_grpc")

from sim.fly_survey import build_mission_plan, parse_args  # noqa: E402
from sim.survey import GeoPoint  # noqa: E402


def test_plan_has_one_item_per_waypoint_with_set_altitude_and_speed() -> None:
    plan = build_mission_plan(GeoPoint(48.0, 11.0), 1000, 1000, 100, altitude_m=30, speed_m_s=10)
    assert len(plan.mission_items) == 22
    assert {i.relative_altitude_m for i in plan.mission_items} == {30}
    assert {i.speed_m_s for i in plan.mission_items} == {10}
    assert all(i.is_fly_through for i in plan.mission_items)


def test_first_waypoint_is_home() -> None:
    plan = build_mission_plan(GeoPoint(48.0, 11.0), 1000, 1000, 100, 30, 10)
    first = plan.mission_items[0]
    assert (first.latitude_deg, first.longitude_deg) == (48.0, 11.0)


def test_unused_optional_fields_are_nan_so_px4_ignores_them() -> None:
    item = build_mission_plan(GeoPoint(48.0, 11.0), 100, 100, 50, 30, 10).mission_items[0]
    assert math.isnan(item.yaw_deg)
    assert math.isnan(item.acceptance_radius_m)


def test_defaults_describe_the_1km_survey() -> None:
    args = parse_args([])
    assert (args.width, args.height) == (1000.0, 1000.0)
    assert args.system_address.startswith("udpin://")
