"""Replay a link_intermittent recording's link timing through the backend (issue 77).

The recording is vehicle-side: its link cuts and restores, no backend, no operator, no command. So
this is a regression check of the hub and the command gate, not evidence about real reconnects or
PX4. It drops and restores the link at the recorded times, with one synthetic recommendation (LAND,
raised while the vehicle is RED), synthetic trust reports and a scripted operator who tries to
approve it after each restore, or also during the first outage.

    python -m eval.intermittent_replay eval/lost_link/recordings
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from c2.allocator import Assignment, assign, split_area
from c2.audit import AuditLog
from c2.fleet import FleetState
from c2.gate import CommandGate
from c2.hub import Hub, HubError
from c2.messages import Command, Outcome, Recommendation
from navtrust.types import NavTrust, ReasonCode, TrustState

VEHICLE = "uav1"
RECOMMENDATION_ID = "r1"
STEP_S = 0.5  # the cadence of the vehicle's trust reports while the link is up (proposal)
TRY_AFTER_RESTORE_S = 1.0  # when the operator tries again, after each restore (arbitrary)
ACK_TIMEOUT_S = 0.05  # short, so a vehicle that never answers costs the test no time
RECOMMENDATION_TTL_S = 1000.0  # long, so that expiry is not what ends the recommendation


class Situation(Enum):
    UNCHANGED = "unchanged"  # RED for the whole run
    CHANGED = "changed"  # RED, then GREEN from the first restore on


class Vehicle(Enum):
    ANSWERS = "answers"  # an executor call returns at once
    SILENT = "silent"  # an executor call never returns


@dataclass(frozen=True)
class OutageReplay:
    cuts: int
    outages: int  # outage summaries the hub published
    superseded: list[str]
    commands_sent: dict[str, int]  # recommendation id -> command_sent rows
    not_acknowledged: int  # command_not_acknowledged rows
    attempts: list[str]  # what the hub or gate said to each of the operator's tries, in order
    gate_repeat: str | None  # what the gate said when asked again to run an approval it had run


class _Executor:
    def __init__(self, vehicle: Vehicle) -> None:
        self._vehicle = vehicle

    async def land(self, vehicle_id: str) -> None:
        if self._vehicle is Vehicle.SILENT:
            await asyncio.sleep(3600)

    async def hold(self, vehicle_id: str) -> None: ...
    async def return_to_launch(self, vehicle_id: str) -> None: ...
    async def retask(self, assignment: Assignment, vehicles: list[str]) -> None: ...


class _Clock:
    def __init__(self) -> None:
        self.t = 0.0

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


def replay_outages(
    path: Path,
    situation: Situation,
    vehicle: Vehicle = Vehicle.ANSWERS,
    also_try_during_first_outage: bool = False,
) -> OutageReplay:
    cuts, restores = _link_events(path)
    clock, audit = _Clock(), AuditLog()
    hub = Hub(audit, clock)
    fleet = FleetState(assign(split_area(900, 900, 1), [VEHICLE]))
    gate = CommandGate(hub, fleet, _Executor(vehicle), ack_timeout_s=ACK_TIMEOUT_S)
    summaries: list[dict[str, Any]] = []
    hub.subscribe(lambda e: summaries.append(e) if e["type"] == "outage_summary" else None)

    hub.ingest_navtrust(_report(TrustState.RED))
    hub.add_recommendation(
        Recommendation(
            id=RECOMMENDATION_ID,
            vehicle_id=VEHICLE,
            created_s=0.0,
            expires_s=RECOMMENDATION_TTL_S,
            reason=ReasonCode.INCONSISTENT_INNOVATION,
            command=Command.LAND,
            sector_moves=(),
            rationale="synthetic",
        )
    )

    attempts: list[str] = []
    gate_repeat: list[str] = []

    def try_to_approve() -> None:
        try:
            hub.decide(RECOMMENDATION_ID, Outcome.APPROVED, "replay")
        except HubError as err:
            attempts.append(err.code)
            return
        result = asyncio.run(gate.execute(RECOMMENDATION_ID))
        attempts.append("executed" if result.executed else str(result.reason))
        gate_repeat.append(str(asyncio.run(gate.execute(RECOMMENDATION_ID)).reason))

    tries = [r + TRY_AFTER_RESTORE_S for r in restores]
    if also_try_during_first_outage:
        tries.insert(0, (cuts[0] + restores[0]) / 2)

    def link_down(t: float) -> bool:
        return any(c <= t < r for c, r in zip(cuts, restores, strict=True))

    t, next_try = 0.0, 0
    while next_try < len(tries):
        clock.t = t
        hub.sweep()
        if not link_down(t):
            changed = situation is Situation.CHANGED and t >= restores[0]
            hub.ingest_navtrust(_report(TrustState.GREEN if changed else TrustState.RED))
        if t >= tries[next_try]:
            try_to_approve()
            next_try += 1
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
    return OutageReplay(
        cuts=len(cuts),
        outages=len(summaries),
        superseded=superseded,
        commands_sent=sent,
        not_acknowledged=len(audit.events("command_not_acknowledged")),
        attempts=attempts,
        gate_repeat=gate_repeat[0] if gate_repeat else None,
    )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("directory", type=Path, help="holds link_intermittent-N.jsonl")
    args = parser.parse_args(argv)
    for path in sorted(args.directory.glob("link_intermittent-*.jsonl")):
        for situation in Situation:
            for during in (False, True):
                r = replay_outages(path, situation, also_try_during_first_outage=during)
                print(
                    f"{path.stem} {situation.value}{', tries during outage 1' if during else ''}: "
                    f"{r.outages} outages, superseded {r.superseded}, sent {r.commands_sent}, "
                    f"tries {r.attempts}, gate asked again: {r.gate_repeat}"
                )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
