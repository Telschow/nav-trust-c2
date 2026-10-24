"""Log PX4's flight mode whenever it changes.

A recording that shows only positions cannot say which failsafe acted. The mode stream
(HOLD, RETURN_TO_LAUNCH, LAND, ...) makes the link-loss and the GNSS-loss reactions visible.
Needs only a duck-typed drone, so it is testable without the simulator stack.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from mavsdk_grpc import System


class EventLog(Protocol):
    def write(self, event: str, **fields: Any) -> None: ...


async def log_flight_mode(drone: System, log: EventLog) -> None:
    last: str | None = None
    async for mode in drone.telemetry.flight_mode():
        if mode.name != last:
            last = mode.name
            log.write("flight_mode", mode=last)
