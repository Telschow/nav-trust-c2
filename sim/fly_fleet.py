"""Fly a survey of one area with several vehicles at once, one sector each.

Vehicle i (1-based) listens on udp 14540+i, matching run_sitl.sh. Routes are in one frame
whose origin is vehicle 1's home, so every vehicle flies the sector it was given regardless
of where it started. Writes one JSON-lines log per vehicle.

    python -m sim.fly_fleet --vehicles 3
"""

from __future__ import annotations

import argparse
import asyncio
import time
from pathlib import Path

from mavsdk_grpc import System

from c2.allocator import Sector, assign, split_area
from sim.fly_survey import JsonlLog, fly
from sim.survey import GeoPoint, LocalPoint, lawnmower_rect


def sector_route(sector: Sector, spacing_m: float) -> list[LocalPoint]:
    return lawnmower_rect(sector.west, sector.south, sector.east, sector.north, spacing_m)


def vehicle_ids(n: int) -> list[str]:
    return [f"uav{i}" for i in range(1, n + 1)]


async def fly_vehicle(
    index: int,
    vehicle_id: str,
    sectors: list[Sector],
    origin: GeoPoint,
    args: argparse.Namespace,
    out_dir: Path,
) -> None:
    address = f"udpin://0.0.0.0:{14540 + index}"
    log = JsonlLog(out_dir / f"{vehicle_id}.jsonl")
    drone = System(port=50050 + index)
    try:
        await drone.connect(system_address=address)
        log.write("connected", vehicle=vehicle_id, address=address)
        log.write("sectors", ids=[s.id for s in sectors])
        route = [p for s in sectors for p in sector_route(s, args.spacing)]
        await fly(
            drone,
            log,
            width=0,
            height=0,
            spacing=args.spacing,
            altitude=args.altitude + 5 * (index - 1),  # vertical separation between vehicles
            speed=args.speed,
            position_interval_s=args.position_interval,
            route=route,
            route_origin=origin,
        )
    finally:
        log.close()


async def home_of(index: int) -> GeoPoint:
    drone = System(port=50040 + index)
    await drone.connect(system_address=f"udpin://0.0.0.0:{14540 + index}")
    async for state in drone.core.connection_state():
        if state.is_connected:
            break
    async for health in drone.telemetry.health():
        if health.is_home_position_ok:
            break
    home = await anext(aiter(drone.telemetry.home()))
    return GeoPoint(home.latitude_deg, home.longitude_deg)


async def run(args: argparse.Namespace) -> Path:
    out_dir = Path(args.log_dir) / f"fleet-{time.strftime('%Y%m%dT%H%M%S')}"
    ids = vehicle_ids(args.vehicles)
    assignment = assign(split_area(args.width, args.height, args.vehicles), ids)
    origin = await home_of(1)
    await asyncio.gather(
        *(
            fly_vehicle(i, vid, assignment[vid], origin, args, out_dir)
            for i, vid in enumerate(ids, start=1)
        )
    )
    return out_dir


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Fly one survey with several vehicles")
    p.add_argument("--vehicles", type=int, default=3)
    p.add_argument("--width", type=float, default=1000.0)
    p.add_argument("--height", type=float, default=1000.0)
    p.add_argument("--spacing", type=float, default=100.0)
    p.add_argument("--altitude", type=float, default=30.0, help="vehicle 1; +5 m per vehicle")
    p.add_argument("--speed", type=float, default=10.0)
    p.add_argument("--position-interval", type=float, default=1.0)
    p.add_argument("--log-dir", default="logs")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    print(f"logs written to {asyncio.run(run(parse_args(argv)))}")


if __name__ == "__main__":
    main()
