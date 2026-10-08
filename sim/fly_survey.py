"""Fly one lawnmower survey with a PX4 SITL vehicle through MAVSDK and log telemetry.

The area's south-west corner is the vehicle's home position. Nothing here is platform
specific: speed, altitude and lane spacing are scenario parameters, not vehicle data.

    python -m sim.fly_survey --system-address udpin://0.0.0.0:14541
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path
from typing import Any

from mavsdk_grpc import System
from mavsdk_grpc.mission import MissionItem, MissionPlan

from sim.survey import GeoPoint, lawnmower, local_to_geo, path_length_m

DEFAULT_ADDRESS = "udpin://0.0.0.0:14541"  # PX4 SITL instance 1: remote port 14540 + instance


def build_mission_plan(
    origin: GeoPoint,
    width_m: float,
    height_m: float,
    spacing_m: float,
    altitude_m: float,
    speed_m_s: float,
) -> MissionPlan:
    local = lawnmower(width_m, height_m, spacing_m)
    items = []
    for p in local:
        geo = local_to_geo(origin, p)
        items.append(
            MissionItem(
                latitude_deg=geo.lat_deg,
                longitude_deg=geo.lon_deg,
                relative_altitude_m=altitude_m,
                speed_m_s=speed_m_s,
                is_fly_through=True,
                gimbal_pitch_deg=float("nan"),
                gimbal_yaw_deg=float("nan"),
                camera_action=MissionItem.CameraAction.NONE,
                loiter_time_s=float("nan"),
                camera_photo_interval_s=float("nan"),
                acceptance_radius_m=float("nan"),
                yaw_deg=float("nan"),
                camera_photo_distance_m=float("nan"),
                vehicle_action=MissionItem.VehicleAction.NONE,
            )
        )
    return MissionPlan(items)


class JsonlLog:
    """Append-only JSON-lines log with a monotonic-relative timestamp per record."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = path.open("w", encoding="utf-8")
        self._t0 = time.monotonic()
        self.path = path

    def write(self, event: str, **fields: Any) -> None:
        record = {"t_s": round(time.monotonic() - self._t0, 3), "event": event, **fields}
        self._fh.write(json.dumps(record) + "\n")
        self._fh.flush()

    def close(self) -> None:
        self._fh.close()


async def _log_position(drone: System, log: JsonlLog) -> None:
    async for pos in drone.telemetry.position():
        log.write(
            "position",
            lat_deg=pos.latitude_deg,
            lon_deg=pos.longitude_deg,
            rel_alt_m=pos.relative_altitude_m,
        )


async def _log_progress(drone: System, log: JsonlLog) -> None:
    async for prog in drone.mission.mission_progress():
        log.write("mission_progress", current=prog.current, total=prog.total)


async def _wait_until_ready(drone: System) -> None:
    async for state in drone.core.connection_state():
        if state.is_connected:
            return
    # unreachable: the stream does not end while the link is up


async def _wait_for_health(drone: System) -> None:
    async for health in drone.telemetry.health():
        if health.is_global_position_ok and health.is_home_position_ok:
            return


async def _wait_for_finish(drone: System) -> None:
    async for finished in drone.mission.is_mission_finished():
        if finished:
            return


async def _wait_for_landing(drone: System) -> None:
    async for in_air in drone.telemetry.in_air():
        if not in_air:
            return


async def run(args: argparse.Namespace) -> Path:
    log_path = Path(args.log_dir) / f"survey-{time.strftime('%Y%m%dT%H%M%S')}.jsonl"
    log = JsonlLog(log_path)
    drone = System(port=args.grpc_port)
    background: list[asyncio.Task[None]] = []
    try:
        await drone.connect(system_address=args.system_address)
        await _wait_until_ready(drone)
        log.write("connected", address=args.system_address)

        await _wait_for_health(drone)
        home = await anext(aiter(drone.telemetry.home()))
        origin = GeoPoint(home.latitude_deg, home.longitude_deg)
        log.write("home", lat_deg=origin.lat_deg, lon_deg=origin.lon_deg)

        plan = build_mission_plan(
            origin, args.width, args.height, args.spacing, args.altitude, args.speed
        )
        log.write(
            "plan",
            waypoints=len(plan.mission_items),
            path_length_m=path_length_m(lawnmower(args.width, args.height, args.spacing)),
            width_m=args.width,
            height_m=args.height,
            spacing_m=args.spacing,
            altitude_m=args.altitude,
            speed_m_s=args.speed,
        )
        await drone.mission.set_return_to_launch_after_mission(True)
        await drone.mission.upload_mission(plan)

        background = [
            asyncio.create_task(_log_position(drone, log)),
            asyncio.create_task(_log_progress(drone, log)),
        ]
        await drone.action.arm()
        log.write("armed")
        await drone.mission.start_mission()
        log.write("mission_started")
        await _wait_for_finish(drone)
        log.write("mission_finished")
        await _wait_for_landing(drone)
        log.write("landed")
    finally:
        for task in background:
            task.cancel()
        log.close()
    return log_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0] if __doc__ else None)
    p.add_argument("--system-address", default=DEFAULT_ADDRESS)
    p.add_argument("--grpc-port", type=int, default=50051, help="local mavsdk_server port")
    p.add_argument("--width", type=float, default=1000.0, help="east-west extent, m")
    p.add_argument("--height", type=float, default=1000.0, help="north-south extent, m")
    p.add_argument("--spacing", type=float, default=100.0, help="max lane spacing, m")
    p.add_argument("--altitude", type=float, default=30.0, help="height above home, m")
    p.add_argument("--speed", type=float, default=10.0, help="mission speed, m/s")
    p.add_argument("--log-dir", default="logs")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    log_path = asyncio.run(run(parse_args(argv)))
    print(f"log written to {log_path}")


if __name__ == "__main__":
    main()
