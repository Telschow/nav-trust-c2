"""A recommendation ends when the trust it was raised about no longer holds (issue 224)."""

import pytest

from c2.audit import AuditLog
from c2.hub import Hub, SupersededRecommendation
from c2.messages import Command, Outcome, Recommendation
from navtrust.types import NavTrust, ReasonCode, TrustState

RED = (TrustState.RED, ReasonCode.INCONSISTENT_INNOVATION)


def report(
    state: TrustState = TrustState.GREEN,
    reason: ReasonCode | None = None,
    vehicle: str = "uav2",
) -> NavTrust:
    bound = 0.15 if state is TrustState.GREEN else float("inf")
    return NavTrust(vehicle, 1.0, state, reason, bound, 1.0)


def rec(rid: str = "r1", vehicle: str = "uav2") -> Recommendation:
    return Recommendation(
        rid, vehicle, 100.0, 160.0, ReasonCode.INCONSISTENT_INNOVATION, Command.LAND, (), "x"
    )


def hub_with_open_rec() -> tuple[Hub, AuditLog]:
    audit = AuditLog()
    hub = Hub(audit, lambda: 100.0, link_timeout_s=2.0)
    hub.ingest_navtrust(report(*RED))
    hub.add_recommendation(rec())
    return hub, audit


def test_a_return_to_green_supersedes_the_open_recommendation() -> None:
    hub, audit = hub_with_open_rec()
    hub.ingest_navtrust(report())
    with pytest.raises(SupersededRecommendation):
        hub.decide("r1", Outcome.APPROVED, "daniel")
    assert audit.events("rejected_decision")[-1].payload["rejected_because"] == "superseded"


def test_a_change_of_reason_supersedes_the_open_recommendation() -> None:
    hub, _ = hub_with_open_rec()
    hub.ingest_navtrust(report(TrustState.RED, ReasonCode.STALE))
    with pytest.raises(SupersededRecommendation):
        hub.decide("r1", Outcome.APPROVED, "daniel")


def test_the_superseding_is_recorded_as_a_system_decision_with_its_reason() -> None:
    hub, audit = hub_with_open_rec()
    hub.ingest_navtrust(report())
    [row] = audit.events("decision")
    assert row.payload["outcome"] == "SUPERSEDED" and row.payload["operator"] == "system"
    assert "changed" in row.payload["note"]


def test_the_same_red_again_leaves_the_recommendation_open() -> None:
    hub, audit = hub_with_open_rec()
    hub.ingest_navtrust(report(*RED))
    hub.decide("r1", Outcome.APPROVED, "daniel")
    assert [r.payload["outcome"] for r in audit.events("decision")] == ["APPROVED"]


def test_another_vehicle_returning_to_green_changes_nothing_here() -> None:
    hub, _ = hub_with_open_rec()
    hub.ingest_navtrust(report(vehicle="uav1"))
    hub.ingest_navtrust(report(vehicle="uav1"))
    hub.decide("r1", Outcome.APPROVED, "daniel")


def test_an_answered_recommendation_is_not_superseded_afterwards() -> None:
    hub, audit = hub_with_open_rec()
    hub.decide("r1", Outcome.DENIED, "daniel")
    hub.ingest_navtrust(report())
    assert [r.payload["outcome"] for r in audit.events("decision")] == ["DENIED"]
