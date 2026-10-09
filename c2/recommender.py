"""Rule-based recommender (C2-02). Rules follow ADR 0002:

    AMBER                                  nothing (the operator is informed by the trust state)
    RED, GNSS_LOSS or STALE                re-task the vehicle's unfinished sectors; no vehicle
                                           command (PX4's failsafe is acting or the data is gone)
    RED, INCONSISTENT_INNOVATION           HOLD, plus re-task its unfinished sectors

For INCONSISTENT_INNOVATION the rule picks HOLD, not RTL. That is an assumption, not a
measurement: return-to-launch navigates by the position estimate, which is the thing that is
suspect, and in the recorded stuck-position run the vehicle stalled in place. The ADR left
"HOLD or RTL" open.

Only GREEN vehicles may take over work. If there is none, there is nothing to recommend for a
GNSS_LOSS/STALE vehicle (a recommendation needs a command or a move); the alert itself still
shows. One recommendation per vehicle and reason per RED episode; it can be issued again after
the vehicle has been GREEN.

Pure Python. All thresholds are proposals.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from c2.allocator import reassign
from c2.fleet import FleetState
from c2.messages import Command, Recommendation, SectorMove
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

    def _build(self, msg: NavTrust, fleet: FleetState) -> Recommendation | None:
        vehicle = msg.vehicle_id
        assert msg.reason is not None
        command = Command.HOLD if msg.reason is ReasonCode.INCONSISTENT_INNOVATION else None
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
