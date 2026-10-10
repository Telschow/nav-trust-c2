"""Executor that only records what it was asked to do. For running the backend without a
simulator. It implements the Executor protocol; nothing here touches a vehicle."""

from __future__ import annotations

from c2.allocator import Assignment


class DryRunExecutor:
    def __init__(self) -> None:
        self.log: list[str] = []

    async def hold(self, vehicle_id: str) -> None:
        self.log.append(f"hold {vehicle_id}")

    async def return_to_launch(self, vehicle_id: str) -> None:
        self.log.append(f"rtl {vehicle_id}")

    async def land(self, vehicle_id: str) -> None:
        self.log.append(f"land {vehicle_id}")

    async def retask(self, assignment: Assignment, vehicles: list[str]) -> None:
        self.log.append(f"retask {vehicles}")
