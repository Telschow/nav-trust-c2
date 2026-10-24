"""The recorder logs PX4's flight mode when it changes, so a recording shows what acted."""

import asyncio
from collections.abc import AsyncIterator

from sim.flight_mode_log import log_flight_mode


class Mode:
    def __init__(self, name: str) -> None:
        self.name = name


class FakeTelemetry:
    def __init__(self, modes: list[str]) -> None:
        self._modes = modes

    async def flight_mode(self) -> AsyncIterator[Mode]:
        for name in self._modes:
            yield Mode(name)


class FakeDrone:
    def __init__(self, modes: list[str]) -> None:
        self.telemetry = FakeTelemetry(modes)


class FakeLog:
    def __init__(self) -> None:
        self.rows: list[tuple[str, dict[str, object]]] = []

    def write(self, event: str, **fields: object) -> None:
        self.rows.append((event, fields))


def test_only_changes_of_flight_mode_are_logged() -> None:
    log = FakeLog()
    modes = ["HOLD", "MISSION", "MISSION", "MISSION", "RETURN_TO_LAUNCH", "LAND", "LAND"]
    asyncio.run(log_flight_mode(FakeDrone(modes), log))
    assert log.rows == [
        ("flight_mode", {"mode": "HOLD"}),
        ("flight_mode", {"mode": "MISSION"}),
        ("flight_mode", {"mode": "RETURN_TO_LAUNCH"}),
        ("flight_mode", {"mode": "LAND"}),
    ]
