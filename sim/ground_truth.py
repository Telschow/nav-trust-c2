"""True vehicle positions from Gazebo, for evaluation only.

The trust engine never sees this. It is recorded next to the estimator's own position so the
evaluation can measure how wrong a position really was when the engine said GREEN.

Source: the world's `dynamic_pose/info` topic, read through the `gz` command line tool
(there are no Python bindings in the image), one JSON object per line. Poses are in the
Gazebo world frame, x east and y north in metres. Vehicle N is the model `x500_N`; vehicle 1
spawns at the world origin, which is also the origin of the sector grid, so these coordinates
are in the same frame as the sectors.
"""

from __future__ import annotations

import asyncio
import json
import re
import shutil
from collections.abc import AsyncIterator
from typing import Any

from sim.fly_survey import JsonlLog

TOPIC = "/world/default/dynamic_pose/info"
_MODEL = re.compile(r"^x500_(\d+)$")


def gz_command(topic: str = TOPIC) -> list[str]:
    return ["gz", "topic", "-e", "-t", topic, "--json-output"]


def gz_available() -> bool:
    return shutil.which("gz") is not None


def parse_poses(line: str) -> tuple[float, dict[str, tuple[float, float, float]]]:
    """One topic message -> (simulation time in s, {"uavN": (east, north, up)}).

    Entries that are not vehicle models (links, other models) are ignored.
    """
    msg: dict[str, Any] = json.loads(line)
    stamp = msg.get("header", {}).get("stamp", {})
    sim_s = float(stamp.get("sec", 0)) + float(stamp.get("nsec", 0)) / 1e9
    poses: dict[str, tuple[float, float, float]] = {}
    for pose in msg.get("pose", []):
        match = _MODEL.match(pose.get("name", ""))
        if match:
            p = pose["position"]
            poses[f"uav{match.group(1)}"] = (
                float(p.get("x", 0.0)),
                float(p.get("y", 0.0)),
                float(p.get("z", 0.0)),
            )
    return sim_s, poses


async def stream_lines(command: list[str]) -> AsyncIterator[str]:
    proc = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        limit=1 << 22,
    )
    assert proc.stdout is not None
    try:
        # a full world message can exceed asyncio's default 64 KiB line limit
        while line := await proc.stdout.readline():
            yield line.decode()
    finally:
        if proc.returncode is None:
            proc.terminate()
            await proc.wait()


async def log_ground_truth(
    log: JsonlLog,
    vehicles: list[str],
    interval_s: float = 0.5,
    command: list[str] | None = None,
) -> None:
    """Write `truth` events (at most one per vehicle per interval_s of simulation time)."""
    last: dict[str, float] = {}
    async for line in stream_lines(command or gz_command()):
        try:
            sim_s, poses = parse_poses(line)
        except (ValueError, KeyError):
            continue  # a partial or unexpected line; the next one will do
        for vehicle in vehicles:
            if vehicle not in poses or sim_s - last.get(vehicle, float("-inf")) < interval_s:
                continue
            last[vehicle] = sim_s
            east, north, up = poses[vehicle]
            log.write(
                "truth",
                vehicle=vehicle,
                east_m=round(east, 3),
                north_m=round(north, 3),
                alt_m=round(up, 3),
                sim_s=round(sim_s, 3),
            )
