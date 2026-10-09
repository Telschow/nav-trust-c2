"""Fly one survey, optionally with a GNSS-denied zone, and record a replayable run.

One MAVSDK connection does everything: the survey, the zone injector and the recording.
Output is a JSON-lines file readable with navtrust.recording.load_recording.

    python -m sim.record_run --scenario nominal
    python -m sim.record_run --scenario jamming_zone --zone 400 -50 440 300
"""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from mavsdk_grpc import System

from navtrust.recording import SCHEMA
from sim.fly_survey import DEFAULT_ADDRESS, JsonlLog, fly
from sim.gnss_injector import MODES, ensure_enabled, inject_loop, log_gps_info
from sim.interference import rectangle
from sim.survey import GeoPoint

ESTIMATOR_FIELDS = (
    "vel_ratio",
    "pos_horiz_ratio",
    "pos_vert_ratio",
    "mag_ratio",
    "pos_horiz_accuracy",
    "pos_vert_accuracy",
    "flags",
)


def parse_estimator_status(fields_json: str) -> dict[str, Any]:
    """Pick the estimator health fields from an ESTIMATOR_STATUS message, dropping nulls."""
    fields = json.loads(fields_json)
    return {k: fields[k] for k in ESTIMATOR_FIELDS if fields.get(k) is not None}


async def log_estimator_status(drone: System, log: JsonlLog) -> None:
    async for msg in drone.mavlink_direct.message("ESTIMATOR_STATUS"):
        log.write("estimator_status", **parse_estimator_status(msg.fields_json))


def px4_commit() -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", "/opt/PX4-Autopilot", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return out.stdout.strip()


def build_header(args: argparse.Namespace) -> dict[str, Any]:
    zone = (
        {"west": args.zone[0], "south": args.zone[1], "east": args.zone[2], "north": args.zone[3]}
        if args.zone
        else None
    )
    return {
        "schema": SCHEMA,
        "scenario": args.scenario,
        "created_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "px4_commit": px4_commit(),
        "survey": {
            "width_m": args.width,
            "height_m": args.height,
            "spacing_m": args.spacing,
            "altitude_m": args.altitude,
            "speed_m_s": args.speed,
        },
        "zone": zone,
        "failure_mode": args.mode if zone else None,
        "position_interval_s": args.position_interval,
        "max_duration_s": args.max_duration,
    }


async def run(args: argparse.Namespace) -> Path:
    log = JsonlLog(Path(args.out))
    drone = System(port=args.grpc_port)
    try:
        log.write("header", **build_header(args))
        await drone.connect(system_address=args.system_address)
        log.write("connected", address=args.system_address)
        await ensure_enabled(drone)

        def on_ready(origin: GeoPoint) -> list[asyncio.Task[None]]:
            tasks = [
                asyncio.create_task(log_gps_info(drone, log)),
                asyncio.create_task(log_estimator_status(drone, log)),
            ]
            if args.zone:
                polygon = rectangle(*args.zone)
                log.write("zone", polygon=[[p.east_m, p.north_m] for p in polygon])
                tasks.append(
                    asyncio.create_task(inject_loop(drone, origin, polygon, MODES[args.mode], log))
                )
            return tasks

        try:
            await asyncio.wait_for(
                fly(
                    drone,
                    log,
                    width=args.width,
                    height=args.height,
                    spacing=args.spacing,
                    altitude=args.altitude,
                    speed=args.speed,
                    position_interval_s=args.position_interval,
                    on_ready=on_ready,
                ),
                timeout=args.max_duration,
            )
        except TimeoutError:
            # Fault runs can stall for good (e.g. a frozen position never reaches the next
            # waypoint). Say so in the file instead of leaving a silent truncation.
            log.write("recording_stopped", reason="max_duration", max_duration_s=args.max_duration)
    finally:
        log.close()
    return log.path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Record a replayable survey run")
    p.add_argument("--scenario", required=True, help="name stored in the header")
    p.add_argument("--out", help="default: tests/replay/data/<scenario>.jsonl")
    p.add_argument("--system-address", default=DEFAULT_ADDRESS)
    p.add_argument("--grpc-port", type=int, default=50051)
    p.add_argument(
        "--zone",
        nargs=4,
        type=float,
        metavar=("WEST", "SOUTH", "EAST", "NORTH"),
        help="GNSS-denied rectangle, metres east/north of home",
    )
    p.add_argument("--mode", choices=sorted(MODES), default="off")
    p.add_argument("--width", type=float, default=1000.0)
    p.add_argument("--height", type=float, default=200.0)
    p.add_argument("--spacing", type=float, default=100.0)
    p.add_argument("--altitude", type=float, default=30.0)
    p.add_argument("--speed", type=float, default=10.0)
    p.add_argument(
        "--max-duration",
        type=float,
        help="stop recording after this many seconds and write a recording_stopped event",
    )
    p.add_argument("--position-interval", type=float, default=0.5, help="seconds between samples")
    args = p.parse_args(argv)
    args.out = args.out or f"tests/replay/data/{args.scenario}.jsonl"
    return args


def main(argv: list[str] | None = None) -> None:
    print(f"recording written to {asyncio.run(run(parse_args(argv)))}")


if __name__ == "__main__":
    main()
