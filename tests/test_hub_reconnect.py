"""M5b: what the link being down means for decisions (issues 135 and 77)."""

from typing import Any

import pytest

from c2.audit import AuditLog
from c2.hub import Hub, SupersededRecommendation
from c2.messages import Command, Outcome, Recommendation
from navtrust.types import NavTrust, ReasonCode, TrustState


class Clock:
    def __init__(self) -> None:
        self.t = 100.0

    def __call__(self) -> float:
        return self.t


def report(state: TrustState = TrustState.GREEN, reason: ReasonCode | None = None) -> NavTrust:
    bound = 0.15 if state is TrustState.GREEN else float("inf")
    return NavTrust("uav2", 1.0, state, reason, bound, 1.0)


RED = (TrustState.RED, ReasonCode.INCONSISTENT_INNOVATION)


def rec(rid: str = "r1", created: float = 100.0, ttl: float = 60.0) -> Recommendation:
    return Recommendation(
        rid, "uav2", created, created + ttl, ReasonCode.INCONSISTENT_INNOVATION,
        Command.LAND, (), "x",
    )  # fmt: skip


def make() -> tuple[Hub, AuditLog, Clock, list[dict[str, Any]]]:
    audit, clock = AuditLog(), Clock()
    events: list[dict[str, Any]] = []
    hub = Hub(audit, clock, link_timeout_s=2.0)
    hub.subscribe(events.append)
    return hub, audit, clock, events


def of_type(events: list[dict[str, Any]], kind: str) -> list[dict[str, Any]]:
    return [e["data"] for e in events if e["type"] == kind]


class TestExpiryRecordsWhetherTheVehicleCouldBeHeard:
    """Issue 135: the backend knows the link state at the moment it expires a recommendation."""

    def test_an_expiry_while_heard_says_so_and_stays_so_after_the_link_is_lost(self) -> None:
        hub, audit, clock, events = make()
        hub.ingest_navtrust(report())
        hub.add_recommendation(rec(ttl=0.5))
        clock.t = 101.0
        hub.sweep()
        clock.t = 110.0
        hub.sweep()  # the link is lost afterwards
        [decision] = of_type(events, "decision")
        assert decision["outcome"] == "EXPIRED" and decision["vehicle_heard"] is True
        assert audit.events("decision")[-1].payload["vehicle_heard"] is True

    def test_an_expiry_with_no_link_says_so_and_stays_so_after_the_link_returns(self) -> None:
        hub, audit, clock, events = make()
        hub.ingest_navtrust(report())
        hub.add_recommendation(rec(ttl=1.0))
        clock.t = 104.0
        hub.sweep()
        hub.ingest_navtrust(report())  # the link returns
        [decision] = of_type(events, "decision")
        assert decision["vehicle_heard"] is False
        assert audit.events("decision")[-1].payload["vehicle_heard"] is False

    def test_an_answer_does_not_carry_the_field(self) -> None:
        hub, _, _, events = make()
        hub.ingest_navtrust(report())
        hub.add_recommendation(rec())
        hub.decide("r1", Outcome.DENIED, "daniel")
        [decision] = of_type(events, "decision")
        assert "vehicle_heard" not in decision


class TestRecoveryAfterAnOutage:
    """Issue 77: when the link returns, say what changed and close what is stale."""

    def outage(self, hub: Hub, clock: Clock, during: tuple[TrustState, ReasonCode | None]) -> None:
        """uav2 is heard GREEN, goes quiet 10 s, and comes back reporting `during`."""
        hub.ingest_navtrust(report())
        hub.add_recommendation(rec())
        clock.t = 110.0
        hub.sweep()
        clock.t = 112.0
        hub.ingest_navtrust(report(*during))

    def test_a_changed_trust_state_supersedes_the_recommendation_and_publishes_a_summary(
        self,
    ) -> None:
        hub, audit, clock, events = make()
        self.outage(hub, clock, (TrustState.AMBER, ReasonCode.STALE))
        [superseded] = [d for d in of_type(events, "decision") if d["outcome"] == "SUPERSEDED"]
        assert superseded["recommendation_id"] == "r1" and superseded["operator"] == "system"
        [summary] = of_type(events, "outage_summary")
        assert summary["vehicle_id"] == "uav2" and summary["duration_s"] == pytest.approx(12.0)
        assert summary["trust"]["state"] == "AMBER"
        assert summary["superseded"] == ["r1"]
        assert summary["onboard_actions"] == []
        assert summary["trust_changes"][-1]["state"] == "AMBER"
        [row] = audit.events("outage_summary")
        assert row.vehicle_id == "uav2" and row.payload["superseded"] == ["r1"]

    def test_a_changed_reason_alone_supersedes(self) -> None:
        hub, _, clock, events = make()
        hub.ingest_navtrust(report(*RED))
        hub.add_recommendation(rec())
        clock.t = 110.0
        hub.sweep()
        clock.t = 112.0
        hub.ingest_navtrust(report(TrustState.RED, ReasonCode.STALE))
        assert [d["outcome"] for d in of_type(events, "decision")] == ["SUPERSEDED"]

    def test_an_unchanged_situation_keeps_the_recommendation_open(self) -> None:
        hub, _, clock, events = make()
        hub.ingest_navtrust(report(*RED))
        hub.add_recommendation(rec())
        clock.t = 110.0
        hub.sweep()
        clock.t = 112.0
        hub.ingest_navtrust(report(*RED))
        assert of_type(events, "decision") == []
        assert of_type(events, "outage_summary")[0]["superseded"] == []
        assert [r["id"] for r in hub.state()["open_recommendations"]] == ["r1"]

    def test_a_recommendation_raised_during_the_outage_is_left_alone(self) -> None:
        hub, _, clock, events = make()
        hub.ingest_navtrust(report())
        clock.t = 110.0
        hub.sweep()  # no link since 108
        hub.add_recommendation(rec("r2", created=111.0))
        clock.t = 112.0
        hub.ingest_navtrust(report(*RED))
        assert [d["outcome"] for d in of_type(events, "decision")] == []

    def test_a_superseded_recommendation_cannot_be_approved(self) -> None:
        hub, audit, clock, _ = make()
        self.outage(hub, clock, (TrustState.AMBER, ReasonCode.STALE))
        with pytest.raises(SupersededRecommendation):
            hub.decide("r1", Outcome.APPROVED, "daniel")
        assert audit.events("rejected_decision")[-1].payload["rejected_because"] == "superseded"

    def test_other_vehicles_are_not_touched(self) -> None:
        hub, _, clock, events = make()
        hub.ingest_navtrust(NavTrust("uav1", 1.0, TrustState.GREEN, None, 0.15, 1.0))
        self.outage(hub, clock, (TrustState.AMBER, ReasonCode.STALE))
        assert all(d["vehicle_id"] == "uav2" for d in of_type(events, "outage_summary"))

    def test_the_summary_waits_for_a_trust_report_when_a_position_came_back_first(self) -> None:
        hub, _, clock, events = make()
        hub.ingest_navtrust(report())
        hub.add_recommendation(rec())
        clock.t = 110.0
        hub.sweep()
        clock.t = 112.0
        hub.ingest_position("uav2", 47.0, 8.0, 30.0)
        assert of_type(events, "outage_summary") == []
        hub.ingest_navtrust(report(TrustState.AMBER, ReasonCode.STALE))
        assert len(of_type(events, "outage_summary")) == 1

    def test_no_outage_means_no_summary(self) -> None:
        hub, _, _, events = make()
        hub.ingest_navtrust(report())
        hub.ingest_navtrust(report())
        assert of_type(events, "outage_summary") == []
