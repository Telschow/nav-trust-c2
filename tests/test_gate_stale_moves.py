"""An approved sector move is checked against the fleet as it is now (issue 203, audit NTC-A06).

The recommender chose the moves when the vehicle went RED. By the time the operator approves, the
recipient may have gone RED or silent, or the sector may have moved or been finished. The command
the operator approved still goes out; the moves are blocked and audited, and the fleet is left
as it was."""

import asyncio

from c2.allocator import assign, split_area
from c2.audit import AuditLog
from c2.fleet import FleetState
from c2.gate import CommandGate, GateResult
from c2.hub import Hub
from c2.messages import Command, Outcome, Recommendation, SectorMove
from navtrust.types import NavTrust, ReasonCode, TrustState


class Clock:
    t = 100.0

    def __call__(self) -> float:
        return self.t


class Recorder:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def hold(self, vehicle_id: str) -> None:
        self.calls.append(f"hold {vehicle_id}")

    async def return_to_launch(self, vehicle_id: str) -> None:
        self.calls.append(f"rtl {vehicle_id}")

    async def land(self, vehicle_id: str) -> None:
        self.calls.append(f"land {vehicle_id}")

    async def retask(self, assignment, vehicles) -> None:  # type: ignore[no-untyped-def]
        self.calls.append(f"retask {vehicles}")


def trust(vehicle: str, state: TrustState, reason: ReasonCode | None = None) -> NavTrust:
    return NavTrust(
        vehicle, 100.0, state, reason, 0.15 if state is TrustState.GREEN else float("inf"), 1.0
    )


def approved(
    command: Command | None = Command.LAND,
) -> tuple[Hub, FleetState, CommandGate, Recorder, Clock]:
    """uav2 is RED and its only sector S2 is to go to uav3; the operator has approved."""
    clock, ex = Clock(), Recorder()
    hub = Hub(AuditLog(), clock)
    fleet = FleetState(assign(split_area(900, 900, 3), ["uav1", "uav2", "uav3"]))
    for v in ("uav1", "uav3"):
        hub.ingest_navtrust(trust(v, TrustState.GREEN))
    rec = Recommendation(
        "r1", "uav2", 100.0, 160.0, ReasonCode.GNSS_LOSS, command, (SectorMove("S2", "uav3"),), "x"
    )
    hub.add_recommendation(rec)
    hub.decide("r1", Outcome.APPROVED, "daniel")
    return hub, fleet, CommandGate(hub, fleet, ex), ex, clock


def run(gate: CommandGate) -> GateResult:
    return asyncio.run(gate.execute("r1"))


def blocked_reasons(hub: Hub) -> list[str]:
    return [e.payload["reason"] for e in hub.audit.events("command_blocked")]


def test_a_recipient_that_went_red_is_not_given_the_sector() -> None:
    hub, fleet, gate, ex, _ = approved()
    before = {v: [s.id for s in secs] for v, secs in fleet.assignment.items()}
    hub.ingest_navtrust(trust("uav3", TrustState.RED, ReasonCode.GNSS_LOSS))
    result = run(gate)
    assert ex.calls == ["land uav2"]  # the approved command still goes out, no re-task
    assert {v: [s.id for s in secs] for v, secs in fleet.assignment.items()} == before
    assert blocked_reasons(hub) == ["stale_moves: uav3 is RED"]
    assert result.executed and result.reason == "moves_blocked: uav3 is RED"


def test_a_recipient_that_went_silent_is_not_given_the_sector() -> None:
    hub, fleet, gate, ex, clock = approved()
    clock.t += 30.0  # past the link timeout: uav1 and uav3 have said nothing since
    result = run(gate)
    assert ex.calls == ["land uav2"]
    assert [s.id for s in fleet.assignment["uav2"]] == ["S2"]
    assert blocked_reasons(hub) == ["stale_moves: uav3 has no link"]
    assert result.executed


def test_a_sector_that_is_no_longer_the_lost_vehicles_is_not_moved() -> None:
    hub, fleet, gate, ex, _ = approved()
    fleet.apply_moves([("S2", "uav1")])  # another approval already took it
    result = run(gate)
    assert ex.calls == ["land uav2"]
    assert "S2" in [s.id for s in fleet.assignment["uav1"]]
    assert blocked_reasons(hub) == ["stale_moves: S2 is no longer uav2's"]
    assert result.executed


def test_a_sector_that_has_been_finished_is_not_moved() -> None:
    hub, fleet, gate, ex, _ = approved()
    fleet.done_sector_ids.add("S2")
    run(gate)
    assert ex.calls == ["land uav2"]
    assert blocked_reasons(hub) == ["stale_moves: S2 is already done"]


def test_moves_whose_premises_hold_are_applied_as_before() -> None:
    hub, fleet, gate, ex, _ = approved()
    result = run(gate)
    assert ex.calls == ["land uav2", "retask ['uav3']"]  # uav2 has nothing left to fly
    assert "S2" in [s.id for s in fleet.assignment["uav3"]]
    assert blocked_reasons(hub) == []
    assert result.executed and result.reason is None


def test_a_re_task_with_only_stale_moves_sends_nothing_and_is_not_executed() -> None:
    hub, fleet, gate, ex, _ = approved(command=None)
    hub.ingest_navtrust(trust("uav3", TrustState.RED, ReasonCode.GNSS_LOSS))
    result = run(gate)
    assert ex.calls == []
    assert [s.id for s in fleet.assignment["uav2"]] == ["S2"]
    assert not result.executed and result.reason == "moves_blocked: uav3 is RED"
    assert [e.kind for e in hub.audit.events() if e.kind.startswith("command_")] == [
        "command_blocked"
    ]
