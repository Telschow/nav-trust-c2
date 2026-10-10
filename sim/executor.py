"""Executor that sends approved commands to simulated vehicles over MAVSDK.

Only c2.gate.CommandGate may call it (tests enforce that nothing else in c2/ does).
Attaches to the mavsdk_servers that fly_fleet started: vehicle i is grpc port 50050+i.

retask replaces each listed vehicle's mission with its unfinished sectors and restarts it.
It is not exercised in the simulator yet, and it does not know which waypoints a vehicle
already flew: sector completion is not tracked in live operation, so the new mission starts
from the first waypoint of every assigned sector.
"""

from __future__ import annotations

from mavsdk_grpc import System

from c2.allocator import Assignment
from sim.fly_fleet import sector_route
from sim.fly_survey import plan_from_route
from sim.survey import GeoPoint


class MavsdkExecutor:
    def __init__(self, origin: GeoPoint, spacing_m: float, altitude_m: float, speed_m_s: float):
        self._origin = origin
        self._spacing = spacing_m
        self._altitude = altitude_m
        self._speed = speed_m_s
        self._drones: dict[str, System] = {}

    async def _drone(self, vehicle_id: str) -> System:
        if vehicle_id not in self._drones:
            index = int(vehicle_id.removeprefix("uav"))
            drone = System(mavsdk_server_address="localhost", port=50050 + index)
            await drone.connect()
            self._drones[vehicle_id] = drone
        return self._drones[vehicle_id]

    async def hold(self, vehicle_id: str) -> None:
        await (await self._drone(vehicle_id)).action.hold()

    async def return_to_launch(self, vehicle_id: str) -> None:
        await (await self._drone(vehicle_id)).action.return_to_launch()

    async def land(self, vehicle_id: str) -> None:
        await (await self._drone(vehicle_id)).action.land()

    async def retask(self, assignment: Assignment, vehicles: list[str]) -> None:
        for vehicle_id in vehicles:
            sectors = assignment.get(vehicle_id, [])
            if not sectors:
                continue  # nothing to fly; leave the vehicle as it is
            index = int(vehicle_id.removeprefix("uav"))
            route = [p for s in sectors for p in sector_route(s, self._spacing)]
            plan = plan_from_route(
                self._origin, route, self._altitude + 5 * (index - 1), self._speed
            )
            drone = await self._drone(vehicle_id)
            await drone.mission.upload_mission(plan)
            await drone.mission.start_mission()
