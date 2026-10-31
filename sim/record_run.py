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
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from mavsdk_grpc import System

from c2.contingency import POLICY_MAX_AGE_S
from navtrust.recording import SCHEMA
from sim.failsafe_params import apply_failsafe_params
from sim.flight_mode_log import log_flight_mode
from sim.fly_survey import DEFAULT_ADDRESS, JsonlLog, VehicleDisarmed, fly
from sim.gnss_injector import MODES, ensure_enabled, inject_loop, log_gps_info
from sim.ground_truth import gz_available, log_ground_truth
from sim.interference import rectangle
from sim.link_cut import LinkCutSchedule, UdpRelay, drive_link_cut, relay_ports
from sim.onboard_monitor import OnboardMonitor
from sim.onboard_policy import load_policy
from sim.onboard_run import experiment_approval, run_monitor
from sim.scenario import LINK_CUT_AFTER, LINK_CUT_DIRECTIONS, LinkCut
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


async def operator_action_after_fault(
    drone: System, log: JsonlLog, entered: asyncio.Event, action: str, delay_s: float
) -> None:
    """Simulate the operator: send `action` delay_s after the GNSS fault begins.

    Used to measure what an action really does to a faulted vehicle; it bypasses the console
    and the gate on purpose, so it is only for recorded experiments."""
    await entered.wait()
    await asyncio.sleep(delay_s)
    log.write("operator_action", action=action)
    if action == "hold":
        await drone.action.hold()
    elif action == "rtl":
        await drone.action.return_to_launch()
    elif action == "land":
        await drone.action.land()
    else:  # pragma: no cover - argparse restricts the choices
        raise ValueError(action)


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
        "ground_truth": args.ground_truth,
        "latch_fault": args.latch_fault,
        "link_cut": (
            {
                "after": args.link_cut_after,
                "delay_s": args.link_cut_delay,
                "duration_s": args.link_cut_duration,
                "direction": args.link_cut_direction,
                "cycles": args.link_cut_cycles,
                "gap_s": args.link_cut_gap,
            }
            if args.link_cut_after
            else None
        ),
        "operator_action": (
            {"action": args.operator_action, "delay_s": args.operator_delay}
            if args.operator_action
            else None
        ),
        "flight_mode_log": args.log_flight_mode or bool(args.link_cut_after),
        "onboard_policy": (
            {
                **experiment_approval(args.onboard_wait)["policy"],
                "audit_id": 0,
                "note": "this experiment's own policy, not an operator approval",
            }
            if args.onboard_wait is not None
            else None
        ),
    }


class GroundTruthMissing(RuntimeError):
    """The run asked for Gazebo's true position and recorded none."""


class _EventLog(JsonlLog):
    """A log that tells the link-cut schedule when the mission starts and the fault begins, and
    counts what it wrote."""

    def __init__(self, path: Path, schedule: LinkCutSchedule | None) -> None:
        super().__init__(path)
        self._schedule = schedule
        self.counts: dict[str, int] = {}

    def write(self, event: str, **fields: Any) -> None:
        super().write(event, **fields)
        self.counts[event] = self.counts.get(event, 0) + 1
        if self._schedule is not None:
            if event == "mission_started":
                self._schedule.mission_started(time.monotonic())
            elif event == "gnss_enter":
                self._schedule.fault_started(time.monotonic())


def ensure_ground_truth(log: _EventLog, requested: bool) -> None:
    """Fail a run that was meant to carry ground truth and has none: the Gazebo stream can come up
    empty, and a recording without it is useless for evaluation but looks like a success."""
    if requested and log.counts.get("truth", 0) == 0:
        raise GroundTruthMissing("ground truth was requested but no ground truth was recorded")


async def run(args: argparse.Namespace) -> Path:
    cut = (
        LinkCut(
            args.link_cut_after,
            args.link_cut_delay,
            args.link_cut_duration,
            args.link_cut_direction,
            args.link_cut_cycles,
            args.link_cut_gap,
        )
        if args.link_cut_after
        else None
    )
    schedule = LinkCutSchedule(cut) if cut else None
    log = _EventLog(Path(args.out), schedule)
    drone = System(port=args.grpc_port)
    relay: UdpRelay | None = None
    side_tasks: list[asyncio.Task[None]] = []
    address = args.system_address
    try:
        log.write("header", **build_header(args))
        if schedule is not None:
            listen_port, px4_port, script_port = relay_ports(address)
            relay = UdpRelay(listen_port, px4_port, script_port)
            await relay.start()
            address = f"udpin://0.0.0.0:{script_port}"
            side_tasks.append(asyncio.create_task(drive_link_cut(relay, schedule, log.write)))
        await drone.connect(system_address=address)
        log.write("connected", address=address)
        await ensure_enabled(drone)
        if schedule is not None:
            log.write("failsafe_params", **await apply_failsafe_params(drone))
        if schedule is not None or args.log_flight_mode:
            side_tasks.append(asyncio.create_task(log_flight_mode(drone, log)))

        def on_ready(origin: GeoPoint) -> list[asyncio.Task[None]]:
            tasks = [
                asyncio.create_task(log_gps_info(drone, log)),
                asyncio.create_task(log_estimator_status(drone, log)),
            ]
            if args.ground_truth:
                tasks.append(asyncio.create_task(log_ground_truth(log, ["uav1"])))
            if args.onboard_wait is not None:
                approval = experiment_approval(args.onboard_wait)
                policy = load_policy(
                    approval, now_s=approval["approved_s"], max_age_s=POLICY_MAX_AGE_S
                )
                monitor = OnboardMonitor("uav1", policy, started_s=time.monotonic())
                # in the simulator the C2 link is the link-cut relay: down while it is cut
                tasks.append(
                    asyncio.create_task(
                        run_monitor(
                            drone, monitor, lambda: relay is None or not relay.is_cut, log.write
                        )
                    )
                )
            entered = asyncio.Event()
            if args.operator_action:
                tasks.append(
                    asyncio.create_task(
                        operator_action_after_fault(
                            drone, log, entered, args.operator_action, args.operator_delay
                        )
                    )
                )
            if args.zone:
                polygon = rectangle(*args.zone)
                log.write("zone", polygon=[[p.east_m, p.north_m] for p in polygon])
                tasks.append(
                    asyncio.create_task(
                        inject_loop(
                            drone,
                            origin,
                            polygon,
                            MODES[args.mode],
                            log,
                            lambda a: entered.set() if a == "enter" else None,
                            args.latch_fault,
                        )
                    )
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
        except VehicleDisarmed:
            # e.g. a long GNSS outage makes PX4 land the vehicle itself: an expected ending
            log.write("recording_stopped", reason="disarmed")
        except TimeoutError:
            # Fault runs can stall for good (e.g. a frozen position never reaches the next
            # waypoint). Say so in the file instead of leaving a silent truncation.
            log.write("recording_stopped", reason="max_duration", max_duration_s=args.max_duration)
    finally:
        try:
            for task in side_tasks:
                task.cancel()
            await asyncio.gather(*side_tasks, return_exceptions=True)
            if relay is not None:
                await relay.stop()
        finally:
            log.close()
    ensure_ground_truth(log, args.ground_truth)
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
    p.add_argument(
        "--operator-action",
        choices=["hold", "rtl", "land"],
        help="experiment: send this command --operator-delay seconds after the fault begins",
    )
    p.add_argument("--operator-delay", type=float, default=15.0)
    p.add_argument(
        "--link-cut-after",
        choices=LINK_CUT_AFTER,
        help="cut the MAVLink link (both directions) for this vehicle after this event",
    )
    p.add_argument(
        "--onboard-wait",
        type=float,
        help="run the onboard monitor with the ADR 0004 contingency (LAND on a position "
        "inconsistency, link down longer than this many seconds; below COM_DL_LOSS_T)",
    )
    p.add_argument("--link-cut-cycles", type=int, default=1, help="cut and restore this many times")
    p.add_argument("--link-cut-gap", type=float, help="seconds between a restore and the next cut")
    p.add_argument("--link-cut-delay", type=float, default=0.0, help="seconds after the event")
    p.add_argument(
        "--link-cut-direction",
        choices=LINK_CUT_DIRECTIONS,
        default="both",
        help="uplink: drop only what the scripts send to PX4, so the recording still hears it",
    )
    p.add_argument(
        "--link-cut-duration", type=float, help="seconds until the link returns; default never"
    )
    p.add_argument(
        "--latch-fault",
        action="store_true",
        help="once the fault starts it never clears, even if the vehicle leaves the zone",
    )
    p.add_argument(
        "--log-flight-mode",
        action="store_true",
        help="record PX4's flight mode on each change (always on with a link cut)",
    )
    p.add_argument(
        "--no-ground-truth",
        action="store_true",
        help="do not record Gazebo's true position (it is recorded when `gz` is available)",
    )
    args = p.parse_args(argv)
    args.ground_truth = gz_available() and not args.no_ground_truth
    args.out = args.out or f"tests/replay/data/{args.scenario}.jsonl"
    return args


def main(argv: list[str] | None = None) -> None:
    print(f"recording written to {asyncio.run(run(parse_args(argv)))}")


if __name__ == "__main__":
    main()
