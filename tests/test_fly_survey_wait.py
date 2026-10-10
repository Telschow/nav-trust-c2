import asyncio
from collections.abc import AsyncIterator
from typing import Any

import pytest

pytest.importorskip("mavsdk_grpc")

from sim.fly_survey import VehicleDisarmed, _wait_for_finish  # noqa: E402


class FakeDrone:
    """Just enough of mavsdk_grpc.System for _wait_for_finish."""

    def __init__(self, finished_after: int | None, armed: bool) -> None:
        self.calls = 0
        self._finished_after = finished_after
        self._armed = armed
        outer = self

        class Mission:
            async def is_mission_finished(self) -> bool:
                outer.calls += 1
                return outer._finished_after is not None and outer.calls > outer._finished_after

        class Telemetry:
            def armed(self) -> AsyncIterator[bool]:
                async def gen() -> AsyncIterator[bool]:
                    yield outer._armed

                return gen()

        self.mission: Any = Mission()
        self.telemetry: Any = Telemetry()


def test_returns_when_the_mission_finishes(monkeypatch: pytest.MonkeyPatch) -> None:
    async def no_sleep(_: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", no_sleep)
    drone = FakeDrone(finished_after=2, armed=True)
    asyncio.run(_wait_for_finish(drone))
    assert drone.calls == 3


def test_raises_a_specific_error_when_the_vehicle_disarms_first() -> None:
    with pytest.raises(VehicleDisarmed):
        asyncio.run(_wait_for_finish(FakeDrone(finished_after=None, armed=False)))
