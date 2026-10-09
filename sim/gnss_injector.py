"""Inject a GNSS failure while the vehicle is inside an interference polygon.

Uses the MAVSDK failure plugin, which sends MAV_CMD_INJECT_FAILURE. PX4 SITL enables
failure injection by default (SYS_FAILURE_EN=1 in the posix rcS); `ensure_enabled` checks it.
On Gazebo, `gps` supports off, stuck and wrong (PX4 docs, System Failure Injection).

Runs until stopped (Ctrl-C or `timeout`).

    python -m sim.gnss_injector --west 400 --south 0 --east 700 --north 1000
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from pathlib import Path

from mavsdk_grpc import System
from mavsdk_grpc.failure import FailureType, FailureUnit

from sim.fly_survey import DEFAULT_ADDRESS, JsonlLog
from sim.interference import point_in_polygon, rectangle
from sim.survey import GeoPoint, LocalPoint, geo_to_local

MODES = {"off": FailureType.OFF, "stuck": FailureType.STUCK, "wrong": FailureType.WRONG}

Inject = Callable[[FailureType], Awaitable[None]]


class ZoneInjector:
    """Edge-triggered: injects once on entering the zone, clears once on leaving."""

    def __init__(self, polygon: list[LocalPoint], mode: FailureType, inject: Inject) -> None:
        self._polygon = polygon
        self._mode = mode
        self._inject = inject
        self.inside = False

    async def update(self, position: LocalPoint) -> str | None:
        """Feed one position. Returns 'enter' or 'exit' when it acted, else None."""
        now_inside = point_in_polygon(position, self._polygon)
        if now_inside == self.inside:
            return None
        self.inside = now_inside
        await self._inject(self._mode if now_inside else FailureType.OK)
        return "enter" if now_inside else "exit"


async def ensure_enabled(drone: System) -> None:
    if await drone.param.get_param_int("SYS_FAILURE_EN") != 1:
        raise RuntimeError("SYS_FAILURE_EN is not 1; failure injection is disabled")


async def _log_gps_info(drone: System, log: JsonlLog) -> None:
    """Log the receiver's reported fix type and satellite count whenever either changes."""
    last: tuple[str, int] | None = None
    async for info in drone.telemetry.gps_info():
        current = (info.fix_type.name, info.num_satellites)
        if current != last:
            last = current
            log.write("gps_info", fix_type=current[0], num_satellites=current[1])


async def run(args: argparse.Namespace) -> Path:
    log_path = Path(args.log_dir) / f"injector-{time.strftime('%Y%m%dT%H%M%S')}.jsonl"
    log = JsonlLog(log_path)
    # Attach to a mavsdk_server that another script (e.g. fly_survey) already started: two
    # servers cannot both receive PX4's single MAVLink stream on the same UDP port.
    drone = (
        System(mavsdk_server_address=args.server_address, port=args.grpc_port)
        if args.server_address
        else System(port=args.grpc_port)
    )
    gps_task: asyncio.Task[None] | None = None
    try:
        await drone.connect(system_address=None if args.server_address else args.system_address)
        await ensure_enabled(drone)
        home = await anext(aiter(drone.telemetry.home()))
        origin = GeoPoint(home.latitude_deg, home.longitude_deg)
        polygon = rectangle(args.west, args.south, args.east, args.north)
        log.write("zone", polygon=[[p.east_m, p.north_m] for p in polygon], mode=args.mode)

        async def inject(failure_type: FailureType) -> None:
            await drone.failure.inject(FailureUnit.SENSOR_GPS, failure_type, 0)

        injector = ZoneInjector(polygon, MODES[args.mode], inject)
        gps_task = asyncio.create_task(_log_gps_info(drone, log))
        async for pos in drone.telemetry.position():
            local = geo_to_local(origin, GeoPoint(pos.latitude_deg, pos.longitude_deg))
            action = await injector.update(local)
            if action:
                log.write(
                    f"gnss_{action}",
                    east_m=round(local.east_m, 1),
                    north_m=round(local.north_m, 1),
                )
                print(json.dumps({"event": f"gnss_{action}", "mode": args.mode}))
    finally:
        if gps_task is not None:
            gps_task.cancel()
        log.close()
    return log_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Inject GNSS failure inside a rectangular zone")
    p.add_argument("--system-address", default=DEFAULT_ADDRESS)
    p.add_argument("--grpc-port", type=int, default=50052, help="mavsdk_server port")
    p.add_argument(
        "--server-address",
        help="attach to a running mavsdk_server (e.g. localhost) instead of starting one; "
        "use with --grpc-port 50051 to share fly_survey's server",
    )
    p.add_argument("--west", type=float, required=True, help="metres east of home")
    p.add_argument("--south", type=float, required=True, help="metres north of home")
    p.add_argument("--east", type=float, required=True)
    p.add_argument("--north", type=float, required=True)
    p.add_argument("--mode", choices=sorted(MODES), default="off")
    p.add_argument("--log-dir", default="logs")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    print(f"log written to {asyncio.run(run(parse_args(argv)))}")


if __name__ == "__main__":
    main()
