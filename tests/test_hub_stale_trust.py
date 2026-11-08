"""A recommendation cannot be approved on stale trust that position reports hide.

Position reports keep a vehicle's link up, so when trust reports stop and positions do not, no new
trust state arrives to supersede the open recommendation. The hub supersedes it instead once the
vehicle's latest trust report is older than the link timeout; the recommender raises a new one
when trust resumes and the vehicle still needs it. A full outage is left to the reconnection rules
(ADR 0004 item 7), and the gate does not give a sector to a recipient whose trust is stale."""

import asyncio
from typing import Any

import pytest
from support import Clock

from c2.allocator import assign, split_area
from c2.audit import AuditLog
from c2.fleet import FleetState
from c2.gate import CommandGate
from c2.hub import Hub, SupersededRecommendation
from c2.messages import Command, Outcome, Recommendation, SectorMove
from navtrust.types import NavTrust, ReasonCode, TrustState


def trust(vehicle: str, state: TrustState, reason: ReasonCode | None = None) -> NavTrust:
    return NavTrust(
        vehicle, 100.0, state, reason, 0.15 if state is TrustState.GREEN else float("inf"), 1.0
    )


def red(vehicle: str = "uav2") -> NavTrust:
    return trust(vehicle, TrustState.RED, ReasonCode.INCONSISTENT_INNOVATION)


def land(clock: Clock, moves: tuple[SectorMove, ...] = ()) -> Recommendation:
    return Recommendation(
        "r1",
        "uav2",
        clock.t,
        clock.t + 60.0,
        ReasonCode.INCONSISTENT_INNOVATION,
        Command.LAND,
        moves,
        "x",
    )


def make() -> tuple[Hub, Clock, list[dict[str, Any]]]:
    clock = Clock()
    hub = Hub(AuditLog(), clock)
    events: list[dict[str, Any]] = []
    hub.subscribe(events.append)
    hub.ingest_navtrust(red())
    hub.add_recommendation(land(clock))
    return hub, clock, events


def positions_only(hub: Hub, clock: Clock, seconds: float, *vehicles: str) -> None:
    """The vehicles send positions twice a second; no trust report arrives."""
    for _ in range(int(seconds * 2)):
        clock.t += 0.5
        for v in vehicles:
            hub.ingest_position(v, 47.0, 8.0, 50.0)


def outcomes(events: list[dict[str, Any]]) -> list[str]:
    return [e["data"]["outcome"] for e in events if e["type"] == "decision"]


def test_positions_without_trust_supersede_the_recommendation() -> None:
    hub, clock, events = make()
    positions_only(hub, clock, 3.0, "uav2")
    assert hub.is_reachable("uav2")  # the link looks healthy
    assert hub.stale_trust_age_s("uav2") == pytest.approx(3.0)
    with pytest.raises(SupersededRecommendation):
        hub.decide("r1", Outcome.APPROVED, "daniel")
    assert outcomes(events) == ["SUPERSEDED"]
    [row] = hub.audit.events("decision")
    assert row.payload["note"] == "trust reports stopped while the link stayed up"
    [rejected] = hub.audit.events("rejected_decision")
    assert rejected.payload["rejected_because"] == "superseded"


def test_the_sweep_supersedes_it_without_an_approval_attempt() -> None:
    hub, clock, events = make()
    positions_only(hub, clock, 3.0, "uav2")
    hub.sweep()  # what the server does every 0.5 s, so the console sees it close
    assert outcomes(events) == ["SUPERSEDED"]


def test_trust_arriving_with_the_positions_keeps_it_open() -> None:
    hub, clock, events = make()
    for _ in range(10):
        clock.t += 0.5
        hub.ingest_position("uav2", 47.0, 8.0, 50.0)
        hub.ingest_navtrust(red())
    assert hub.decide("r1", Outcome.APPROVED, "daniel").outcome is Outcome.APPROVED


def test_trust_exactly_at_the_link_timeout_is_still_current() -> None:
    hub, clock, _ = make()
    clock.t += 2.0  # the default link timeout; positions keep the link up
    hub.ingest_position("uav2", 47.0, 8.0, 50.0)
    assert hub.stale_trust_age_s("uav2") is None
    assert hub.decide("r1", Outcome.APPROVED, "daniel").outcome is Outcome.APPROVED


def test_a_full_outage_leaves_it_to_the_reconnection_rules() -> None:
    """Nothing heard at all is NO_LINK: the recommendation stays open (ADR 0004 item 7)."""
    hub, clock, events = make()
    clock.t += 3.0
    hub.sweep()
    assert not hub.is_reachable("uav2")
    assert outcomes(events) == []


def test_other_vehicles_are_not_touched() -> None:
    hub, clock, events = make()
    hub.ingest_navtrust(trust("uav1", TrustState.GREEN))
    for _ in range(6):
        clock.t += 0.5
        hub.ingest_position("uav1", 47.0, 8.0, 50.0)
        hub.ingest_navtrust(red())
    hub.sweep()
    assert outcomes(events) == []


def test_a_vehicle_never_heard_from_is_not_known_to_be_stale() -> None:
    hub = Hub(AuditLog(), Clock())
    assert hub.stale_trust_age_s("uav9") is None


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


def test_a_recipient_with_stale_trust_is_not_given_the_sector() -> None:
    clock, ex = Clock(), Recorder()
    hub = Hub(AuditLog(), clock)
    fleet = FleetState(assign(split_area(900, 900, 3), ["uav1", "uav2", "uav3"]))
    hub.ingest_navtrust(trust("uav3", TrustState.GREEN))
    hub.ingest_navtrust(red())
    hub.add_recommendation(land(clock, (SectorMove("S2", "uav3"),)))
    for _ in range(6):  # uav3 sends only positions; uav2's trust stays current
        clock.t += 0.5
        hub.ingest_position("uav3", 47.0, 8.0, 50.0)
        hub.ingest_navtrust(red())
    hub.decide("r1", Outcome.APPROVED, "daniel")
    before = {v: [s.id for s in secs] for v, secs in fleet.assignment.items()}
    result = asyncio.run(CommandGate(hub, fleet, ex).execute("r1"))
    assert ex.calls == ["land uav2"]  # the command rests on current trust, the move does not
    assert {v: [s.id for s in secs] for v, secs in fleet.assignment.items()} == before
    assert result.reason == "moves_blocked: uav3's trust report is stale"
