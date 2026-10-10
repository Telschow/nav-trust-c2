import ast
import asyncio
from pathlib import Path

import pytest

from c2.allocator import Assignment, assign, split_area
from c2.audit import AuditLog
from c2.fleet import FleetState
from c2.gate import CommandGate
from c2.hub import Hub
from c2.messages import Command, Outcome, Recommendation, SectorMove
from navtrust.types import ReasonCode


class Clock:
    t = 100.0

    def __call__(self) -> float:
        return self.t


class FakeExecutor:
    def __init__(self, fail_on: str | None = None) -> None:
        self.calls: list[str] = []
        self.fail_on = fail_on

    async def hold(self, vehicle_id: str) -> None:
        self._do(f"hold {vehicle_id}")

    async def return_to_launch(self, vehicle_id: str) -> None:
        self._do(f"rtl {vehicle_id}")

    async def land(self, vehicle_id: str) -> None:
        self._do(f"land {vehicle_id}")

    async def retask(self, assignment: Assignment, vehicles: list[str]) -> None:
        self._do(
            f"retask {vehicles} " + str({v: [s.id for s in sec] for v, sec in assignment.items()})
        )

    def _do(self, call: str) -> None:
        if self.fail_on and call.startswith(self.fail_on):
            raise RuntimeError("link lost")
        self.calls.append(call)


def rec(
    rid: str = "r1", command: Command | None = Command.HOLD, moves: bool = True
) -> Recommendation:
    return Recommendation(
        rid,
        "uav2",
        100.0,
        160.0,
        ReasonCode.INCONSISTENT_INNOVATION,
        command,
        (SectorMove("S2", "uav3"),) if moves else (),
        "x",
    )


def setup(
    executor: FakeExecutor | None = None,
) -> tuple[Hub, FleetState, CommandGate, FakeExecutor, Clock]:
    clock, ex = Clock(), executor or FakeExecutor()
    hub = Hub(AuditLog(), clock)
    fleet = FleetState(assign(split_area(900, 900, 3), ["uav1", "uav2", "uav3"]))
    return hub, fleet, CommandGate(hub, fleet, ex), ex, clock


def run(gate: CommandGate, rid: str = "r1"):  # type: ignore[no-untyped-def]
    return asyncio.run(gate.execute(rid))


def audit_kinds(hub: Hub) -> list[str]:
    return [e.kind for e in hub.audit.events() if e.kind.startswith("command_")]


def test_approved_recommendation_executes_command_and_retask_and_is_audited() -> None:
    hub, fleet, gate, ex, _ = setup()
    hub.add_recommendation(rec())
    hub.decide("r1", Outcome.APPROVED, "daniel")
    result = run(gate)
    assert result.executed and result.actions == ["HOLD uav2", "RETASK S2->uav3"]
    assert ex.calls[0] == "hold uav2" and ex.calls[1].startswith("retask ['uav2', 'uav3']")
    assert [s.id for s in fleet.assignment["uav3"]] == ["S3", "S2"] and fleet.assignment[
        "uav2"
    ] == []
    [event] = hub.audit.events("command_executed")
    assert event.payload["recommendation_id"] == "r1" and event.vehicle_id == "uav2"


def test_rtl_is_executed_as_rtl() -> None:
    hub, _, gate, ex, _ = setup()
    hub.add_recommendation(rec(command=Command.RTL, moves=False))
    hub.decide("r1", Outcome.APPROVED, "daniel")
    assert run(gate).executed and ex.calls == ["rtl uav2"]


@pytest.mark.parametrize("case", ["no_decision", "denied", "expired", "unknown_recommendation"])
def test_nothing_runs_without_an_approval(case: str) -> None:
    hub, fleet, gate, ex, clock = setup()
    before = {v: list(s) for v, s in fleet.assignment.items()}
    if case != "unknown_recommendation":
        hub.add_recommendation(rec())
    if case == "denied":
        hub.decide("r1", Outcome.DENIED, "daniel")
    if case == "expired":
        clock.t = 161.0
        hub.sweep()
    result = run(gate)
    assert not result.executed and result.reason == case
    assert ex.calls == [] and fleet.assignment == before
    [event] = hub.audit.events("command_blocked")
    assert event.payload["reason"] == case
    assert "command_executed" not in audit_kinds(hub)


def test_an_approval_runs_only_once() -> None:
    hub, _, gate, ex, _ = setup()
    hub.add_recommendation(rec())
    hub.decide("r1", Outcome.APPROVED, "daniel")
    assert run(gate).executed
    second = run(gate)
    assert not second.executed and second.reason == "already_executed"
    assert len([c for c in ex.calls if c.startswith("hold")]) == 1


def test_executor_failure_is_audited_and_the_fleet_is_restored() -> None:
    hub, fleet, gate, ex, _ = setup(FakeExecutor(fail_on="retask"))
    before = {v: [s.id for s in secs] for v, secs in fleet.assignment.items()}
    hub.add_recommendation(rec())
    hub.decide("r1", Outcome.APPROVED, "daniel")
    result = run(gate)
    assert not result.executed and result.reason is not None and "link lost" in result.reason
    assert {v: [s.id for s in secs] for v, secs in fleet.assignment.items()} == before
    [event] = hub.audit.events("command_failed")
    assert event.payload["completed"] == ["HOLD uav2"] and "link lost" in event.payload["error"]
    assert audit_kinds(hub) == ["command_failed"]


def test_invalid_sector_moves_change_nothing() -> None:
    hub, fleet, gate, _, _ = setup()
    bad = Recommendation(
        "r1", "uav2", 100.0, 160.0, ReasonCode.STALE, None, (SectorMove("S9", "uav3"),), "x"
    )
    before = {v: [s.id for s in secs] for v, secs in fleet.assignment.items()}
    hub.add_recommendation(bad)
    hub.decide("r1", Outcome.APPROVED, "daniel")
    assert not run(gate).executed
    assert {v: [s.id for s in secs] for v, secs in fleet.assignment.items()} == before


def test_only_the_gate_issues_vehicle_commands_in_c2() -> None:
    """Architecture check for C2-01: no module in c2/ except gate.py calls an executor method."""
    forbidden = {"hold", "return_to_launch", "land", "retask"}
    offenders = []
    for path in sorted(Path(__file__).parent.parent.joinpath("c2").glob("*.py")):
        if path.name == "gate.py":
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in forbidden
            ):
                offenders.append(f"{path.name}:{node.lineno} .{node.func.attr}()")
    assert offenders == []


def test_land_is_executed_as_land() -> None:
    hub, _, gate, ex, _ = setup()
    hub.add_recommendation(rec(command=Command.LAND, moves=False))
    hub.decide("r1", Outcome.APPROVED, "daniel")
    result = run(gate)
    assert result.executed and result.actions == ["LAND uav2"] and ex.calls == ["land uav2"]
