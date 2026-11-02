"""The backend with the MAVSDK executor: approved commands go to fly_fleet's simulated vehicles
(issue 177). The backend itself (`python -m c2.server`) knows only the dry-run executor and never
imports this package; this launcher registers the MAVSDK one by name and starts the same backend.

    python -m sim.backend --executor mavsdk --origin LAT LON --width 1000 --height 1000
"""

from __future__ import annotations

import argparse
import asyncio
from typing import Any

from c2.fleet import FleetState
from c2.server import main


def mavsdk_executor(args: argparse.Namespace, fleet: FleetState) -> Any:
    """The executor for the vehicles fly_fleet is flying: home of vehicle 1 from --origin, or asked
    of the simulator, and the plan each vehicle already flies."""
    from sim.executor import MavsdkExecutor
    from sim.fly_fleet import home_of
    from sim.survey import GeoPoint

    origin = GeoPoint(*args.origin) if args.origin else asyncio.run(home_of(1))
    return MavsdkExecutor(
        origin,
        spacing_m=args.spacing,
        altitude_m=30.0,
        speed_m_s=10.0,
        initial={v: list(secs) for v, secs in fleet.assignment.items()},
    )


if __name__ == "__main__":
    main({"mavsdk": mavsdk_executor})
