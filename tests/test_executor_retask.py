import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

pytest.importorskip("mavsdk_grpc")

from c2.allocator import Sector  # noqa: E402
from sim.executor import MavsdkExecutor  # noqa: E402
from sim.fly_survey import plan_from_route  # noqa: E402
from sim.survey import GeoPoint, LocalPoint  # noqa: E402

ORIGIN = GeoPoint(47.0, 8.0)
S1 = Sector("S1", 0.0, 0.0, 600.0, 100.0)
S2 = Sector("S2", 0.0, 100.0, 600.0, 200.0)


class FakeMission:
    def __init__(self, items: list[Any], current: int) -> None:
        self.items, self._current, self.started = items, current, False

    async def mission_progress(self) -> Any:
        yield SimpleNamespace(current=self._current, total=len(self.items))

    async def download_mission(self) -> Any:
        return SimpleNamespace(mission_items=self.items)

    async def upload_mission(self, plan: Any) -> None:
        self.items = list(plan.mission_items)

    async def start_mission(self) -> None:
        self.started = True


class Fake(MavsdkExecutor):
    def __init__(self, mission: FakeMission, **kw: Any) -> None:
        super().__init__(ORIGIN, 100.0, 30.0, 10.0, **kw)
        self.mission = mission

    async def _drone(self, vehicle_id: str) -> Any:
        return SimpleNamespace(mission=self.mission)


def mission_of(*points: tuple[float, float]) -> list[Any]:
    plan = plan_from_route(ORIGIN, [LocalPoint(e, n) for e, n in points], 35.0, 10.0)
    return list(plan.mission_items)


def test_taker_keeps_the_rest_of_its_own_sector_and_gets_the_new_one() -> None:
    own = mission_of((0.0, 0.0), (600.0, 0.0), (600.0, 100.0), (0.0, 100.0))  # S1's four waypoints
    fake = Fake(FakeMission(own, current=2), initial={"uav1": [S1]})
    asyncio.run(fake.retask({"uav1": [S1, S2]}, ["uav1"]))
    items = fake.mission.items
    assert len(items) == 2 + 4  # two unflown of S1, then all four of S2
    assert items[:2] == own[2:]
    assert fake.mission.started


def test_vehicle_with_nothing_new_is_left_alone() -> None:
    fake = Fake(FakeMission(mission_of((0.0, 0.0)), current=0), initial={"uav1": [S1]})
    asyncio.run(fake.retask({"uav1": [S1]}, ["uav1"]))
    assert not fake.mission.started


def test_a_second_retask_adds_only_what_is_new() -> None:
    fake = Fake(FakeMission(mission_of((0.0, 0.0)) * 4, current=0), initial={"uav1": [S1]})
    asyncio.run(fake.retask({"uav1": [S1, S2]}, ["uav1"]))
    first = len(fake.mission.items)
    asyncio.run(fake.retask({"uav1": [S1, S2]}, ["uav1"]))
    assert len(fake.mission.items) == first
