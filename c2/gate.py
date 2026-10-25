"""Policy gate (C2-01): no vehicle command without a recorded operator approval.

This is the only place in c2/ that talks to an Executor, and the executor is private to the
gate, so the only way to a vehicle command is `execute(recommendation_id)`. It runs only when
the hub holds an APPROVED decision for that recommendation, and only once. Every outcome is
written to the audit log: command_sent then command_acknowledged (the vehicle answered) or
command_not_acknowledged (no answer within the timeout), and command_executed, command_blocked or
command_failed. A command that was never acknowledged is audited, not resent: its approval is
spent, and the operator decides again.

PX4's own failsafes are not commands from the C2 and never pass through here.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from dataclasses import dataclass, field
from typing import Protocol

from c2.allocator import Assignment
from c2.fleet import FleetState
from c2.hub import Hub
from c2.messages import Command, Outcome


class Executor(Protocol):
    async def hold(self, vehicle_id: str) -> None: ...

    async def return_to_launch(self, vehicle_id: str) -> None: ...

    async def land(self, vehicle_id: str) -> None: ...

    async def retask(self, assignment: Assignment, vehicles: list[str]) -> None:
        """Apply the new assignment: the listed vehicles' routes changed."""
        ...


class NotAcknowledged(Exception):
    """The vehicle did not answer a command in time."""


@dataclass(frozen=True)
class GateResult:
    executed: bool
    reason: str | None = None  # why it was blocked or failed
    actions: list[str] = field(default_factory=list)


class CommandGate:
    def __init__(
        self, hub: Hub, fleet: FleetState, executor: Executor, ack_timeout_s: float = 5.0
    ) -> None:
        """ack_timeout_s: how long a vehicle has to answer a command (a proposal)."""
        if ack_timeout_s <= 0:
            raise ValueError("ack_timeout_s must be > 0")
        self._ack_timeout_s = ack_timeout_s
        self._hub = hub
        self._fleet = fleet
        self._executor = executor
        self._executed: set[str] = set()

    async def execute(self, recommendation_id: str) -> GateResult:
        rec = self._hub.recommendation(recommendation_id)
        decision = self._hub.decision_for(recommendation_id)
        if rec is None:
            return self._blocked(recommendation_id, None, "unknown_recommendation")
        if decision is None:
            return self._blocked(recommendation_id, rec.vehicle_id, "no_decision")
        if decision.outcome is not Outcome.APPROVED:
            return self._blocked(recommendation_id, rec.vehicle_id, decision.outcome.value.lower())
        if recommendation_id in self._executed:
            return self._blocked(recommendation_id, rec.vehicle_id, "already_executed")
        self._executed.add(recommendation_id)  # before any await: a second call cannot overlap

        done: list[str] = []
        moved = False
        original = {v: list(s) for v, s in self._fleet.assignment.items()}
        try:

            async def send(action: str, call: Awaitable[None]) -> None:
                await self._send(recommendation_id, rec.vehicle_id, action, call)
                done.append(action)

            if rec.command is Command.HOLD:
                await send(f"HOLD {rec.vehicle_id}", self._executor.hold(rec.vehicle_id))
            elif rec.command is Command.RTL:
                await send(f"RTL {rec.vehicle_id}", self._executor.return_to_launch(rec.vehicle_id))
            elif rec.command is Command.LAND:
                await send(f"LAND {rec.vehicle_id}", self._executor.land(rec.vehicle_id))
            if rec.sector_moves:
                self._fleet.apply_moves([(m.sector_id, m.to_vehicle) for m in rec.sector_moves])
                moved = True
                changed = sorted({rec.vehicle_id, *(m.to_vehicle for m in rec.sector_moves)})
                moves = ", ".join(f"{m.sector_id}->{m.to_vehicle}" for m in rec.sector_moves)
                await send(
                    f"RETASK {moves}", self._executor.retask(self._fleet.assignment, changed)
                )
        except NotAcknowledged as err:
            # the approval is spent and nothing is resent; whether the vehicle got it is unknown,
            # so the plan is not rolled back
            return GateResult(False, f"not_acknowledged: {err}", done)
        except Exception as err:  # noqa: BLE001 - any executor or validation failure is audited
            if moved:
                self._fleet.assignment.clear()
                self._fleet.assignment.update(original)
            self._hub.audit.append(
                self._hub.now(),
                "command_failed",
                rec.vehicle_id,
                {"recommendation_id": recommendation_id, "error": repr(err), "completed": done},
            )
            return GateResult(False, f"failed: {err}", done)

        self._hub.audit.append(
            self._hub.now(),
            "command_executed",
            rec.vehicle_id,
            {"recommendation_id": recommendation_id, "actions": done},
        )
        return GateResult(True, None, done)

    async def _send(
        self, recommendation_id: str, vehicle_id: str, action: str, call: Awaitable[None]
    ) -> None:
        """Send one command and wait for the vehicle's answer: the executor call returns when the
        vehicle has accepted it. Audited as sent, then acknowledged or not."""
        payload = {"recommendation_id": recommendation_id, "action": action}
        self._hub.audit.append(self._hub.now(), "command_sent", vehicle_id, payload)
        try:
            await asyncio.wait_for(call, self._ack_timeout_s)
        except TimeoutError as err:
            self._hub.audit.append(
                self._hub.now(),
                "command_not_acknowledged",
                vehicle_id,
                {**payload, "timeout_s": self._ack_timeout_s},
            )
            raise NotAcknowledged(f"{action} had no answer in {self._ack_timeout_s:g} s") from err
        self._hub.audit.append(self._hub.now(), "command_acknowledged", vehicle_id, payload)

    def _blocked(self, recommendation_id: str, vehicle_id: str | None, reason: str) -> GateResult:
        self._hub.audit.append(
            self._hub.now(),
            "command_blocked",
            vehicle_id,
            {"recommendation_id": recommendation_id, "reason": reason},
        )
        return GateResult(False, reason)
