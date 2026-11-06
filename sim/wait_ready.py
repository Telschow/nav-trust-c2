"""Wait until the simulator is ready to record, instead of sleeping a fixed time (issue 180).

Run inside the simulator container, after it was restarted:

    python -m sim.wait_ready --vehicles 1 [--limit 240]

Ready means the Gazebo world answers and every vehicle's PX4 reports a good global position and a
home position (what the survey itself waits for before it takes off). Exit 0 when ready. At the
limit it exits 1 and names what was not ready; the recording scripts then print the container's
last log lines.
"""

from __future__ import annotations

import argparse
import asyncio
import re
import subprocess
import sys
import time
from collections.abc import Callable, Mapping
from functools import partial

from mavsdk_grpc import System

LIMIT_S = 240.0  # proposal: the fixed wait it replaces was 90 s and too short under load
POLL_S = 5.0
HEALTH_TRY_S = 20.0  # how long one look at a vehicle's health may take
GRPC_PORT = 50100  # local mavsdk_server ports, apart from the ones the recorders use
MAVLINK_PORT = 14540  # vehicle i answers on this plus i (sim/docker/run_sitl.sh)


def unmet_after_waiting(
    checks: Mapping[str, Callable[[], bool]],
    limit_s: float,
    poll_s: float,
    clock: Callable[[], float],
    sleep: Callable[[float], None],
) -> list[str]:
    """Poll until every check passes or the limit. The names of the checks still failing."""
    deadline = clock() + limit_s
    pending = list(checks)
    while True:
        pending = [name for name in pending if not _passes(checks[name])]
        if not pending or clock() >= deadline:
            return pending
        sleep(poll_s)


def _passes(check: Callable[[], bool]) -> bool:
    try:
        return check()
    except Exception:  # a check that cannot run is not ready  # noqa: BLE001
        return False


def gazebo_world_answers() -> bool:
    out = subprocess.run(
        ["gz", "topic", "-l"], capture_output=True, text=True, timeout=10, check=True
    ).stdout
    return re.search(r"^/world/.*/clock", out, re.MULTILINE) is not None


async def _health_ok(index: int) -> bool:
    drone = System(port=GRPC_PORT + index)
    await drone.connect(system_address=f"udpin://0.0.0.0:{MAVLINK_PORT + index}")
    async for health in drone.telemetry.health():
        return bool(health.is_global_position_ok and health.is_home_position_ok)
    return False


def vehicle_is_healthy(index: int) -> bool:
    return asyncio.run(asyncio.wait_for(_health_ok(index), HEALTH_TRY_S))


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--vehicles", type=int, required=True)
    parser.add_argument("--limit", type=float, default=LIMIT_S)
    args = parser.parse_args(argv)
    checks: dict[str, Callable[[], bool]] = {"the Gazebo world": gazebo_world_answers}
    for i in range(1, args.vehicles + 1):
        checks[f"PX4 of vehicle {i}"] = partial(vehicle_is_healthy, i)
    unmet = unmet_after_waiting(checks, args.limit, POLL_S, time.monotonic, time.sleep)
    if unmet:
        print(f"not ready after {args.limit:.0f} s: {', '.join(unmet)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
