"""Rule-based recommender (C2-02). Rules follow ADR 0002, amended by ADR 0003:

    AMBER                                  nothing (the operator is informed by the trust state)
    RED, GNSS_LOSS or STALE                re-task the vehicle's unfinished sectors; no vehicle
                                           command (PX4's failsafe is acting or the data is gone)
    RED, INCONSISTENT_INNOVATION           LAND, plus re-task its unfinished sectors

LAND, not HOLD or RTL, for INCONSISTENT_INNOVATION. In simulation with ground truth a vehicle
whose GPS position is frozen does not stall: it keeps flying away, accelerating (5.3 km
away by the end of a 220 s run; an earlier run reached 5.9 km) and no PX4 failsafe fires.
In single clean runs only LAND ended the flight in a controlled stop; HOLD and RTL ended in
fast, uncontrolled descents hundreds of metres from where the vehicle believed it was
(tests/replay/test_stuck_action_evidence.py).

Only GREEN vehicles may take over work. If there is none, there is nothing to recommend for a
GNSS_LOSS/STALE vehicle (a recommendation needs a command or a move); the alert itself still
shows. One recommendation per vehicle and reason per RED episode, but it is issued again if it
expires unanswered while the vehicle is still RED (`on_decision`), because a runaway vehicle
must not be left without an open recommendation. A denied one is not repeated.

Pure Python. All thresholds are proposals.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from c2.allocator import reassign
from c2.fleet import FleetState
from c2.messages import Command, Decision, Outcome, Recommendation, SectorMove
from navtrust.types import NavTrust, ReasonCode, TrustState


@dataclass(frozen=True)
class RecommenderConfig:
    ttl_s: float = 60.0  # how long an operator has to answer (proposal)

    def __post_init__(self) -> None:
        if self.ttl_s <= 0:
            raise ValueError("ttl_s must be > 0")


class Recommender:
    def __init__(self, clock: Callable[[], float], config: RecommenderConfig | None = None) -> None:
        self._clock = clock
        self._cfg = config or RecommenderConfig()
        self._latest: dict[str, TrustState] = {}
        self._issued: dict[str, ReasonCode] = {}  # vehicle -> reason of the open episode
        self._counter = 0

    def observe(self, msg: NavTrust, fleet: FleetState) -> list[Recommendation]:
        """Feed one trust message; returns the recommendations it triggers (usually none)."""
        self._latest[msg.vehicle_id] = msg.state
        if msg.state is TrustState.GREEN:
            self._issued.pop(msg.vehicle_id, None)
            return []
        if msg.state is not TrustState.RED or msg.reason is None:
            return []
        if self._issued.get(msg.vehicle_id) == msg.reason:
            return []

        rec = self._build(msg, fleet)
        if rec is not None:
            self._issued[msg.vehicle_id] = msg.reason
        return [rec] if rec is not None else []

    def on_decision(self, decision: Decision, vehicle_id: str) -> None:
        """Tell the recommender how a recommendation ended. An expired one is allowed to be
        issued again if the vehicle is still RED; an answered one is not repeated."""
        if decision.outcome is Outcome.EXPIRED:
            self._issued.pop(vehicle_id, None)

    def _build(self, msg: NavTrust, fleet: FleetState) -> Recommendation | None:
        vehicle = msg.vehicle_id
        assert msg.reason is not None
        command = Command.LAND if msg.reason is ReasonCode.INCONSISTENT_INNOVATION else None
        moves = self._moves(vehicle, fleet)
        if command is None and not moves:
            return None

        now = self._clock()
        self._counter += 1
        parts = []
        if command is not None:
            parts.append(command.value)
        if moves:
            parts.append("re-task " + ", ".join(f"{m.sector_id} to {m.to_vehicle}" for m in moves))
        return Recommendation(
            id=f"rec-{vehicle}-{self._counter}",
            vehicle_id=vehicle,
            created_s=now,
            expires_s=now + self._cfg.ttl_s,
            reason=msg.reason,
            command=command,
            sector_moves=tuple(moves),
            rationale=f"{vehicle} RED ({msg.reason.value}): " + "; ".join(parts),
        )

    def _moves(self, vehicle: str, fleet: FleetState) -> list[SectorMove]:
        pending = fleet.unfinished_of(vehicle)
        takers = [
            v
            for v in fleet.assignment
            if v != vehicle and self._latest.get(v) is TrustState.GREEN and v in fleet.positions
        ]
        if not pending or not takers:
            return []
        after = reassign(
            fleet.assignment, vehicle, fleet.done_sector_ids, fleet.positions, available=takers
        )
        before = {s.id for s in fleet.assignment[vehicle]}
        return [
            SectorMove(s.id, v)
            for v in takers
            for s in after[v]
            if s.id in before and s.id not in fleet.done_sector_ids
        ]
