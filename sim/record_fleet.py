"""Record one three-vehicle run with a vehicle lost and a scripted operator. Run in the sim image.

Starts fly_fleet (each vehicle flies its sector), the C2 backend with the MAVSDK executor, the
live trust feed and a GNSS fault on one vehicle; logs ground truth for every vehicle; and plays
the operator: every recommendation is answered `--operator` (approve, deny or none) after
`--operator-delay` seconds. The delay is a parameter of the scenario, not a measured human time.
Writes one JSON-lines file: header, truth, and the C2's audit rows as they appear.

    python -m sim.record_fleet --name loss_approved --run 1 --operator approve
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import httpx

from sim.fly_survey import JsonlLog
from sim.ground_truth import log_ground_truth
from sim.record_run import px4_commit

BACKEND = "http://127.0.0.1:8000"
VEHICLES = ["uav1", "uav2", "uav3"]


class FleetLog(JsonlLog):
    """JsonlLog that also remembers each vehicle's latest true altitude (to know when to stop)."""

    def __init__(self, path: Path) -> None:
        super().__init__(path)
        self.alt: dict[str, float] = {}
        self.airborne: set[str] = set()

    def write(self, event: str, **fields: Any) -> None:
        if event == "truth":
            v, alt = fields["vehicle"], fields["alt_m"]
            self.alt[v] = alt
            if alt > 5.0:
                self.airborne.add(v)
        super().write(event, **fields)

    def all_landed(self) -> bool:
        return set(VEHICLES) <= self.airborne and all(self.alt[v] < 0.5 for v in VEHICLES)


async def spawn(args: list[str], out: Path) -> asyncio.subprocess.Process:
    fh = out.open("wb")
    return await asyncio.create_subprocess_exec(
        sys.executable, "-m", *args, stdout=fh, stderr=subprocess.STDOUT
    )


async def home_of_first(work: Path) -> tuple[float, float]:
    """vehicle 1's home, from fly_fleet's own log (a second connection would split PX4's stream)"""
    while True:
        for path in work.glob("fleet-*/uav1.jsonl"):
            for line in path.read_text().splitlines():
                rec = json.loads(line)
                if rec["event"] == "home":
                    return rec["lat_deg"], rec["lon_deg"]
        await asyncio.sleep(1.0)


async def planned_spacing(work: Path) -> float:
    """Lane spacing vehicle 1 says it planned with, from fly_fleet's own log."""
    while True:
        for path in work.glob("fleet-*/uav1.jsonl"):
            for line in path.read_text().splitlines():
                rec = json.loads(line)
                if rec["event"] == "plan":
                    return float(rec["spacing_m"])
        await asyncio.sleep(0.5)


async def operator(
    log: FleetLog, http: httpx.AsyncClient, policy: str, delay_s: float, stop: asyncio.Event
) -> None:
    first_seen: dict[str, float] = {}
    answered: set[str] = set()
    audit_seen = 0
    t0 = time.monotonic()
    while not stop.is_set():
        try:
            state = (await http.get("/state")).json()
            rows = (await http.get("/audit")).json()
        except httpx.HTTPError:
            await asyncio.sleep(1.0)
            continue
        for row in rows[audit_seen:]:
            log.write("audit", row=row)
        audit_seen = len(rows)
        now = time.monotonic() - t0
        for rec in state["open_recommendations"]:
            rid = rec["id"]
            if rid in answered or policy == "none":
                continue
            if rid not in first_seen:
                first_seen[rid] = now
                log.write("recommendation_seen", id=rid, rationale=rec["rationale"])
            if now - first_seen[rid] >= delay_s:
                answered.add(rid)
                body = {
                    "recommendation_id": rid,
                    "outcome": "APPROVED" if policy == "approve" else "DENIED",
                    "operator": "scripted",
                }
                resp = await http.post("/decisions", json=body)
                result = resp.json() if resp.status_code == 200 else resp.text
                log.write(
                    "operator_decision", id=rid, policy=policy, status=resp.status_code,
                    response=result,
                )  # fmt: skip
        await asyncio.sleep(0.5)


async def run(args: argparse.Namespace) -> Path:
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    work = Path(args.work_dir) / f"{args.name}-{args.run}"
    shutil.rmtree(work, ignore_errors=True)  # a reused audit database or log would leak old runs
    work.mkdir(parents=True)
    log = FleetLog(out / f"{args.name}-{args.run}.jsonl")
    px4 = px4_commit()
    log.write(
        "header",
        schema=1,
        scenario=args.name,
        px4_commit=px4,
        area={"width_m": args.width, "height_m": args.height, "spacing_m": args.spacing},
        vehicles=VEHICLES,
        fault={"vehicle": args.fault_vehicle, "mode": args.mode, "zone": args.zone},
        operator={"policy": args.operator, "delay_s": args.operator_delay},
        ground_truth=True,
        max_duration_s=args.max_duration,
    )
    procs: list[asyncio.subprocess.Process] = []
    tasks: list[asyncio.Task[Any]] = []
    stop = asyncio.Event()
    try:
        procs.append(
            await spawn(
                [
                    "sim.fly_fleet",
                    "--vehicles",
                    "3",
                    "--width",
                    str(args.width),
                    "--height",
                    str(args.height),
                    "--spacing",
                    str(args.spacing),
                    "--log-dir",
                    str(work),
                ],  # fmt: skip
                work / "fly_fleet.out",
            )
        )
        lat, lon = await home_of_first(work)
        log.write("home", lat_deg=lat, lon_deg=lon)
        planned = await planned_spacing(work)
        if planned != args.spacing:  # an argument that never reached fly_fleet once went unnoticed
            raise RuntimeError(f"fly_fleet planned {planned} m lanes, expected {args.spacing} m")
        procs.append(
            await spawn(
                [
                    "c2.server",
                    "--executor",
                    "mavsdk",
                    "--width",
                    str(args.width),
                    "--height",
                    str(args.height),
                    "--spacing",
                    str(args.spacing),
                    "--db",
                    str(work / "audit.sqlite"),
                    "--console",
                    "none",
                    "--origin",
                    str(lat),
                    str(lon),
                    "--source",
                    "SIM FLEET RECORDING",
                ],  # fmt: skip
                work / "server.out",
            )
        )
        await asyncio.sleep(4.0)
        procs.append(await spawn(["sim.vehicle_feed", "--vehicles", "3"], work / "feed.out"))
        n = int(args.fault_vehicle.removeprefix("uav"))
        west, south, east, north = args.zone
        # the injector's frame is the faulted vehicle's own home, 5 m further north per vehicle
        procs.append(
            await spawn(
                [
                    "sim.gnss_injector",
                    "--server-address",
                    "localhost",
                    "--grpc-port",
                    str(50050 + n),
                    "--west",
                    str(west),
                    "--south",
                    str(south - 5 * (n - 1)),
                    "--east",
                    str(east),
                    "--north",
                    str(north - 5 * (n - 1)),
                    "--mode",
                    args.mode,
                    "--log-dir",
                    str(work),
                ],  # fmt: skip
                work / "injector.out",
            )
        )
        tasks.append(asyncio.create_task(log_ground_truth(log, VEHICLES)))
        async with httpx.AsyncClient(base_url=BACKEND, timeout=5.0) as http:
            tasks.append(
                asyncio.create_task(operator(log, http, args.operator, args.operator_delay, stop))
            )
            start = time.monotonic()
            while time.monotonic() - start < args.max_duration:
                if log.all_landed():
                    await asyncio.sleep(5.0)
                    log.write("recording_stopped", reason="all_landed")
                    break
                await asyncio.sleep(1.0)
            else:
                log.write("recording_stopped", reason="max_duration")
            stop.set()
            await asyncio.sleep(1.0)
    finally:
        for t in tasks:
            t.cancel()
        for p in procs:
            if p.returncode is None:
                p.terminate()
        for p in procs:
            await p.wait()
        log.close()
    return log.path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Record a three-vehicle run with a scripted operator")
    p.add_argument("--name", required=True)
    p.add_argument("--run", type=int, default=1)
    p.add_argument("--operator", choices=["approve", "deny", "none"], required=True)
    p.add_argument("--operator-delay", type=float, default=15.0)
    p.add_argument("--fault-vehicle", default="uav2")
    p.add_argument("--mode", choices=["off", "stuck", "wrong"], default="off")
    p.add_argument(
        "--zone", nargs=4, type=float, default=[150.0, 90.0, 450.0, 210.0],
        metavar=("WEST", "SOUTH", "EAST", "NORTH"),
        help="in vehicle 1's frame",
    )  # fmt: skip
    p.add_argument("--width", type=float, default=600.0)
    p.add_argument("--height", type=float, default=300.0)
    p.add_argument("--spacing", type=float, default=50.0, help="lane spacing; sectors are 100 m")
    p.add_argument("--max-duration", type=float, default=900.0)
    p.add_argument("--out-dir", default="eval/fleet/recordings")
    p.add_argument("--work-dir", default="logs/fleet-work")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    print(f"recorded {asyncio.run(run(parse_args(argv)))}")


if __name__ == "__main__":
    main()
