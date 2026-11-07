"""Replay a link_intermittent recording through the backend (issue 77). Evaluation only.

The recording is vehicle-side: its link cuts and restores, no backend, no operator, no command. So
this does not show what a real run did. It shows what the hub and the command gate do when the link
drops and returns at the recorded times, with one synthetic recommendation (LAND, raised while the
vehicle is RED) and a scripted operator who tries to approve it. The trust reports are synthetic
too: RED all along, or, after the first outage, GREEN.

    python -m eval.intermittent_replay eval/lost_link/recordings
"""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from c2.allocator import Assignment, assign, split_area
from c2.audit import AuditLog
from c2.fleet import FleetState
from c2.gate import CommandGate
from c2.hub import Hub, HubError
from c2.messages import Command, Outcome, Recommendation
from navtrust.types import NavTrust, ReasonCode, TrustState

VEHICLE = "uav1"
STEP_S = 0.5  # the cadence of the vehicle's trust reports while the link is up (proposal)
APPROVE_AFTER_RESTORE_S = 1.0
RECOMMENDATION_TTL_S = 1000.0  # long, so that expiry is not what ends the recommendation


class Situation(Enum):
    UNCHANGED = "unchanged"  # RED for the whole run
    CHANGED = "changed"  # RED, then GREEN from the first restore on


@dataclass(frozen=True)
class FlapReplay:
    cuts: int
    outages: int  # outage summaries the hub published
    superseded: list[str]
    commands_sent: dict[str, int]  # recommendation id -> command_sent rows
    last_attempt: str  # what the hub or gate said to the operator's last try to approve


class _Executor:
    async def hold(self, vehicle_id: str) -> None: ...
    async def return_to_launch(self, vehicle_id: str) -> None: ...
    async def land(self, vehicle_id: str) -> None: ...
    async def retask(self, assignment: Assignment, vehicles: list[str]) -> None: ...


class _Clock:
    t = 0.0

    def __call__(self) -> float:
        return self.t


def _link_events(path: Path) -> tuple[list[float], list[float]]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    cuts = [r["t_s"] for r in rows if r.get("event") == "link_cut"]
    restores = [r["t_s"] for r in rows if r.get("event") == "link_restore"]
    return cuts, restores


def _report(state: TrustState) -> NavTrust:
    reason = ReasonCode.INCONSISTENT_INNOVATION if state is TrustState.RED else None
    bound = 0.15 if state is TrustState.GREEN else float("inf")
    return NavTrust(VEHICLE, 1.0, state, reason, bound, 1.0)


def replay_flaps(path: Path, situation: Situation) -> FlapReplay:
    cuts, restores = _link_events(path)
    clock, audit = _Clock(), AuditLog()
    hub = Hub(audit, clock)
    fleet = FleetState(assign(split_area(900, 900, 1), [VEHICLE]))
    gate = CommandGate(hub, fleet, _Executor())
    outages: list[object] = []
    hub.subscribe(lambda e: outages.append(e) if e["type"] == "outage_summary" else None)

    hub.ingest_navtrust(_report(TrustState.RED))
    hub.add_recommendation(
        Recommendation(
            "r1",
            VEHICLE,
            0.0,
            RECOMMENDATION_TTL_S,
            ReasonCode.INCONSISTENT_INNOVATION,
            Command.LAND,
            (),
            "synthetic",
        )  # fmt: skip
    )

    def link_down(t: float) -> bool:
        return any(c <= t < r for c, r in zip(cuts, restores, strict=True))

    def attempt() -> str:
        try:
            hub.decide("r1", Outcome.APPROVED, "replay")
        except HubError as err:
            return err.code
        return asyncio.run(gate.execute("r1")).reason or "executed"

    approve_at = [r + APPROVE_AFTER_RESTORE_S for r in restores]
    last = ""
    end = restores[-1] + APPROVE_AFTER_RESTORE_S + STEP_S
    t, tried = 0.0, 0
    while t <= end:
        clock.t = t
        hub.sweep()
        if not link_down(t):
            changed = situation is Situation.CHANGED and t >= restores[0]
            hub.ingest_navtrust(_report(TrustState.GREEN if changed else TrustState.RED))
        if tried < len(approve_at) and t >= approve_at[tried]:
            if tried in (0, len(approve_at) - 1):  # after the first restore, and again at the end
                last = attempt()
            tried += 1
        t += STEP_S

    sent: dict[str, int] = {}
    for row in audit.events("command_sent"):
        rid = row.payload["recommendation_id"]
        sent[rid] = sent.get(rid, 0) + 1
    superseded = [
        row.payload["recommendation_id"]
        for row in audit.events("decision")
        if row.payload["outcome"] == Outcome.SUPERSEDED.value
    ]
    return FlapReplay(len(cuts), len(outages), superseded, sent, last)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("directory", type=Path, help="holds link_intermittent-N.jsonl")
    args = parser.parse_args(argv)
    for path in sorted(args.directory.glob("link_intermittent-*.jsonl")):
        for situation in Situation:
            r = replay_flaps(path, situation)
            print(
                f"{path.stem} {situation.value}: {r.cuts} cuts, {r.outages} outages, "
                f"superseded {r.superseded}, commands sent {r.commands_sent}, "
                f"last attempt: {r.last_attempt}"
            )
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main(sys.argv[1:]))
