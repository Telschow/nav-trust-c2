"""Executor that sends approved commands to simulated vehicles over MAVSDK.

Only c2.gate.CommandGate may call it (tests enforce that nothing else in c2/ does).
Attaches to the mavsdk_servers that fly_fleet started: vehicle i is grpc port 50050+i.

retask gives each listed vehicle the sectors it was not already flying, behind whatever it has
not flown yet of its current mission (read back from PX4, so a vehicle never restarts a sector
it is part way through). The executor is told what each vehicle was flying at the start.
"""

from __future__ import annotations

from mavsdk_grpc import System
from mavsdk_grpc.mission import MissionPlan

from c2.allocator import Assignment
from sim.fly_fleet import sector_route
from sim.fly_survey import plan_from_route
from sim.survey import GeoPoint


class MavsdkExecutor:
    def __init__(
        self,
        origin: GeoPoint,
        spacing_m: float,
        altitude_m: float,
        speed_m_s: float,
        initial: Assignment | None = None,
    ):
        self._origin = origin
        self._spacing = spacing_m
        self._altitude = altitude_m
        self._speed = speed_m_s
        self._drones: dict[str, System] = {}
        # sectors each vehicle already has in its mission
        self._known: dict[str, set[str]] = {
            v: {s.id for s in secs} for v, secs in (initial or {}).items()
        }

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
            known = self._known.get(vehicle_id, set())
            fresh = [s for s in sectors if s.id not in known]
            if not fresh:
                continue
            index = int(vehicle_id.removeprefix("uav"))
            route = [p for s in fresh for p in sector_route(s, self._spacing)]
            added = plan_from_route(
                self._origin, route, self._altitude + 5 * (index - 1), self._speed
            ).mission_items
            drone = await self._drone(vehicle_id)
            kept = []
            if known:
                progress = await anext(aiter(drone.mission.mission_progress()))
                current = (await drone.mission.download_mission()).mission_items
                kept = list(current[progress.current :])
            await drone.mission.upload_mission(MissionPlan(kept + list(added)))
            await drone.mission.start_mission()
            self._known[vehicle_id] = {s.id for s in sectors}
