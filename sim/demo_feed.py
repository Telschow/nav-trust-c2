"""Demo data for the console without the simulator. NOT a live flight.

Trust comes from real recordings run through the trust engine. Positions are synthetic: each
vehicle walks its sector route at the survey speed times --speed. The backend is told the source
is a replay, so the console labels it as one.

Scenarios (--scenario):
    stuck    uav2's GPS position freezes (ADR 0003): RED, a LAND + re-task recommendation, and
             uav2 stops where the fault starts. The default.
    outage   uav3 loses GNSS for long enough that PX4 lands it (ADR 0002): AMBER, then RED, a
             re-task-only recommendation (there is nothing to command), and uav3 stops where it
             lands.
    both     the two above in one run, about five seconds apart: two alerts to prioritise.

The feed follows the fleet assignment: when an approved re-task gives a vehicle new sectors, it
appends their routes.

    python -m sim.demo_feed --backend http://127.0.0.1:8000 --speed 5 --scenario outage
"""

from __future__ import annotations

import argparse
import asyncio
import math
from dataclasses import dataclass
from pathlib import Path

import httpx

from c2.allocator import Sector
from c2.messages import navtrust_to_dict
from navtrust.engine import TrustEngine
from navtrust.recording import Recording, load_recording
from navtrust.replay import replay_engine
from navtrust.types import NavTrust
from sim.fly_fleet import sector_route
from sim.survey import GeoPoint, LocalPoint, local_to_geo

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "tests" / "replay" / "data"
EVAL = ROOT / "eval" / "recordings"
ORIGIN = GeoPoint(47.397971, 8.546164)  # PX4 SITL default home, where the recordings were made

NOMINAL = {
    "uav1": DATA / "nominal-1.jsonl",
    "uav2": DATA / "nominal-2.jsonl",
    "uav3": DATA / "nominal-3.jsonl",
}


@dataclass(frozen=True)
class VehicleScript:
    """Where a vehicle's trust comes from and when (recording time, s) it stops moving."""

    recording: Path
    stops_at_s: float | None


def stop_time(rec: Recording, kind: str) -> float:
    """Recording time at which the vehicle stops moving.

    freeze: a frozen GPS position, so the reported position stops where the fault starts.
    land: PX4 landed the vehicle, so it stops where its true altitude first reaches the ground."""
    fault = rec.first("gnss_enter")
    if fault is None:
        raise ValueError("recording has no fault")
    if kind == "freeze":
        return float(fault["t_s"])
    if kind == "land":
        landed = next(
            (t["t_s"] for t in rec.of("truth") if t["t_s"] > fault["t_s"] and t["alt_m"] < 0.5),
            None,
        )
        return float(landed if landed is not None else rec.records[-1]["t_s"])
    raise ValueError(f"unknown stop kind {kind!r}")


def scenario_plan(name: str) -> dict[str, VehicleScript]:
    """Per vehicle: its trust recording and when it stops. Nominal vehicles never stop."""
    plan = {v: VehicleScript(path, None) for v, path in NOMINAL.items()}
    if name in ("stuck", "both"):
        path = DATA / "stuck_zone-1.jsonl"
        plan["uav2"] = VehicleScript(path, stop_time(load_recording(path), "freeze"))
    if name in ("outage", "both"):
        path = EVAL / "long_outage-1.jsonl"
        plan["uav3"] = VehicleScript(path, stop_time(load_recording(path), "land"))
    if name not in ("stuck", "outage", "both"):
        raise ValueError(f"unknown scenario {name!r}; choose stuck, outage or both")
    return plan


class RouteWalker:
    """Moves along a polyline at a given speed. Pure; no I/O."""

    def __init__(self, start: LocalPoint, route: list[LocalPoint]) -> None:
        self.position = start
        self._route = list(route)
        self.frozen = False

    def extend(self, route: list[LocalPoint]) -> None:
        self._route.extend(route)

    @property
    def finished(self) -> bool:
        return not self._route

    def advance(self, distance_m: float) -> LocalPoint:
        if self.frozen:
            return self.position
        while distance_m > 0 and self._route:
            target = self._route[0]
            gap = math.hypot(
                target.east_m - self.position.east_m, target.north_m - self.position.north_m
            )
            if gap <= distance_m:
                self.position = target
                self._route.pop(0)
                distance_m -= gap
            else:
                f = distance_m / gap
                self.position = LocalPoint(
                    self.position.east_m + (target.east_m - self.position.east_m) * f,
                    self.position.north_m + (target.north_m - self.position.north_m) * f,
                )
                distance_m = 0
        return self.position


def trust_at(reports: list[NavTrust], recording_t_s: float) -> NavTrust:
    """Latest engine output at or before recording_t_s."""
    best = reports[0]
    for r in reports:
        if r.stamp_s > recording_t_s:
            break
        best = r
    return best


def sectors_from_fleet(payload: dict) -> dict[str, list[Sector]]:  # type: ignore[type-arg]
    return {
        v: [Sector(s["id"], s["west"], s["south"], s["east"], s["north"]) for s in secs]
        for v, secs in payload["assignment"].items()
    }


async def run(args: argparse.Namespace) -> None:
    plan = scenario_plan(args.scenario)
    reports = {
        v: replay_engine(load_recording(script.recording), TrustEngine(v))
        for v, script in plan.items()
    }
    async with httpx.AsyncClient(base_url=args.backend, timeout=2.0) as http:
        await http.post("/source", json={"label": "REPLAY DEMO"})
        await http.post("/origin", json={"lat_deg": ORIGIN.lat_deg, "lon_deg": ORIGIN.lon_deg})
        assignment = sectors_from_fleet((await http.get("/fleet")).json())
        walkers = {
            v: RouteWalker(
                LocalPoint(0.0, 5.0 * i),
                [p for s in secs for p in sector_route(s, 100.0)],
            )
            for i, (v, secs) in enumerate(sorted(assignment.items()))
        }
        known = {v: {s.id for s in secs} for v, secs in assignment.items()}
        step, t_demo = 0.5, 0.0
        while True:
            t_rec = t_demo * args.speed
            fresh = sectors_from_fleet((await http.get("/fleet")).json())
            for v, w in walkers.items():
                trust = trust_at(reports[v], t_rec)
                stops = plan[v].stops_at_s
                if stops is not None and t_rec >= stops:
                    w.frozen = True
                for s in fresh.get(v, []):
                    if s.id not in known[v]:  # re-tasked to this vehicle
                        known[v].add(s.id)
                        w.extend(sector_route(s, 100.0))
                pos = w.advance(10.0 * args.speed * step)
                geo = local_to_geo(ORIGIN, pos)
                await http.post("/navtrust", json=navtrust_to_dict(trust))
                await http.post(
                    "/positions",
                    json={
                        "vehicle_id": v,
                        "lat_deg": geo.lat_deg,
                        "lon_deg": geo.lon_deg,
                        "alt_m": 30.0,
                    },
                )
            t_demo += step
            await asyncio.sleep(step)


def main() -> None:
    p = argparse.ArgumentParser(
        description="Console demo feed (replayed trust, synthetic positions)"
    )
    p.add_argument("--backend", default="http://127.0.0.1:8000")
    p.add_argument("--speed", type=float, default=5.0, help="recording time per demo second")
    p.add_argument("--scenario", choices=["stuck", "outage", "both"], default="stuck")
    asyncio.run(run(p.parse_args()))


if __name__ == "__main__":
    main()
