"""Feed live vehicle telemetry through the trust engine to the C2 backend.

One engine per vehicle. It reads the receiver fix type and ESTIMATOR_STATUS over MAVSDK and
posts a NavTrust to the backend twice a second.

Attach to the MAVSDK servers that fly_fleet already started (a second server on the same
UDP port would split PX4's stream): vehicle i uses grpc port 50050+i.

    python -m sim.vehicle_feed --vehicles 3 --backend http://127.0.0.1:8000
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time

import httpx
from mavsdk_grpc import System

from c2.messages import navtrust_to_dict
from navtrust.engine import TrustEngine
from sim.record_run import parse_estimator_status


async def feed_vehicle(
    index: int, backend: str, interval_s: float, client: httpx.AsyncClient
) -> None:
    vehicle_id = f"uav{index}"
    engine = TrustEngine(vehicle_id)
    clock0 = time.monotonic()

    def now() -> float:
        return time.monotonic() - clock0

    drone = System(mavsdk_server_address="localhost", port=50050 + index)
    await drone.connect()

    async def fixes() -> None:
        async for info in drone.telemetry.gps_info():
            engine.update_fix(now(), info.fix_type.name)

    async def estimator() -> None:
        async for msg in drone.mavlink_direct.message("ESTIMATOR_STATUS"):
            f = parse_estimator_status(msg.fields_json)
            engine.update_estimator(
                now(), f.get("pos_horiz_accuracy"), f.get("pos_horiz_ratio"), f.get("vel_ratio")
            )

    async def positions() -> None:
        last = float("-inf")
        async for pos in drone.telemetry.position():
            if time.monotonic() - last < 0.5:  # the map does not need 50 Hz
                continue
            last = time.monotonic()
            body = {
                "vehicle_id": vehicle_id,
                "lat_deg": pos.latitude_deg,
                "lon_deg": pos.longitude_deg,
                "alt_m": pos.relative_altitude_m,
            }
            try:
                await client.post(f"{backend}/positions", json=body)
            except httpx.HTTPError as err:
                print(json.dumps({"vehicle": vehicle_id, "post_failed": str(err)}))

    async def origin() -> None:
        # the sector grid is anchored at vehicle 1's home (see sim/fly_fleet.py)
        if index != 1:
            return
        home = await anext(aiter(drone.telemetry.home()))
        await client.post(
            f"{backend}/origin", json={"lat_deg": home.latitude_deg, "lon_deg": home.longitude_deg}
        )

    async def publish() -> None:
        while True:
            body = navtrust_to_dict(engine.report(now()))
            try:
                await client.post(f"{backend}/navtrust", json=body)
            except httpx.HTTPError as err:
                print(json.dumps({"vehicle": vehicle_id, "post_failed": str(err)}))
            await asyncio.sleep(interval_s)

    await asyncio.gather(fixes(), estimator(), publish(), positions(), origin())


async def run(args: argparse.Namespace) -> None:
    async with httpx.AsyncClient(timeout=2.0) as client:
        await asyncio.gather(
            *(
                feed_vehicle(i, args.backend, args.interval, client)
                for i in range(1, args.vehicles + 1)
            )
        )


def main() -> None:
    p = argparse.ArgumentParser(description="Live NavTrust feed to the C2 backend")
    p.add_argument("--vehicles", type=int, default=3)
    p.add_argument("--backend", default="http://127.0.0.1:8000")
    p.add_argument("--interval", type=float, default=0.5)
    asyncio.run(run(p.parse_args()))


if __name__ == "__main__":
    main()
