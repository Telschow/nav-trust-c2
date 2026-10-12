from typing import Any

import pytest

from c2.audit import AuditLog
from c2.hub import (
    AlreadyDecided,
    DuplicateRecommendation,
    ExpiredRecommendation,
    Hub,
    InvalidOperator,
    InvalidOutcome,
    UnknownRecommendation,
)
from c2.messages import Command, Outcome, Recommendation, SectorMove
from navtrust.types import NavTrust, ReasonCode, TrustState


class Clock:
    def __init__(self) -> None:
        self.t = 100.0

    def __call__(self) -> float:
        return self.t


def trust(vehicle: str = "uav1", state: TrustState = TrustState.GREEN, t: float = 1.0) -> NavTrust:
    reason = None if state is TrustState.GREEN else ReasonCode.GNSS_LOSS
    return NavTrust(
        vehicle, t, state, reason, 0.15 if state is TrustState.GREEN else float("inf"), 1.0
    )


def rec(rid: str = "r1", expires: float = 130.0) -> Recommendation:
    return Recommendation(
        rid,
        "uav2",
        100.0,
        expires,
        ReasonCode.GNSS_LOSS,
        Command.RTL,
        (SectorMove("S2", "uav3"),),
        "x",
    )


def make() -> tuple[Hub, AuditLog, Clock, list[dict[str, Any]]]:
    audit, clock = AuditLog(), Clock()
    events: list[dict[str, Any]] = []
    hub = Hub(audit, clock)
    hub.subscribe(events.append)
    return hub, audit, clock, events


def test_navtrust_is_stored_published_and_only_changes_are_audited() -> None:
    hub, audit, _, events = make()
    hub.ingest_navtrust(trust(t=1.0))
    hub.ingest_navtrust(trust(t=2.0))
    hub.ingest_navtrust(trust(state=TrustState.AMBER, t=3.0))
    assert len(events) == 3 and all(e["type"] == "navtrust" for e in events)
    changes = audit.events("navtrust_change")
    assert [c.payload["state"] for c in changes] == ["GREEN", "AMBER"]
    assert changes[1].payload["previous_state"] == "GREEN"
    assert hub.state()["vehicles"]["uav1"]["state"] == "AMBER"


def test_unknown_bound_is_json_null() -> None:
    hub, _, _, _ = make()
    hub.ingest_navtrust(trust(state=TrustState.RED))
    assert hub.state()["vehicles"]["uav1"]["horizontal_bound_m"] is None


def test_approve_records_the_decision_and_closes_the_recommendation() -> None:
    hub, audit, clock, events = make()
    hub.add_recommendation(rec())
    clock.t = 110.0
    d = hub.decide("r1", Outcome.APPROVED, "daniel", "ok")
    assert (d.outcome, d.decided_s, d.operator) == (Outcome.APPROVED, 110.0, "daniel")
    assert hub.state()["open_recommendations"] == []
    kinds = [e.kind for e in audit.events()]
    assert kinds == ["recommendation", "decision"]
    assert audit.events("decision")[0].payload["operator"] == "daniel"
    assert [e["type"] for e in events] == ["recommendation", "decision"]


def test_deny_is_recorded_too() -> None:
    hub, audit, _, _ = make()
    hub.add_recommendation(rec())
    hub.decide("r1", Outcome.DENIED, "daniel")
    assert audit.events("decision")[0].payload["outcome"] == "DENIED"


@pytest.mark.parametrize(
    ("setup", "error", "because"),
    [
        ("none", UnknownRecommendation, "unknown_recommendation"),
        ("decided", AlreadyDecided, "already_decided"),
        ("expired", ExpiredRecommendation, "expired"),
    ],
)
def test_bad_decisions_are_rejected_and_logged(
    setup: str, error: type[Exception], because: str
) -> None:
    hub, audit, clock, _ = make()
    if setup != "none":
        hub.add_recommendation(rec())
    if setup == "decided":
        hub.decide("r1", Outcome.DENIED, "a")
    if setup == "expired":
        clock.t = 131.0
    with pytest.raises(error):
        hub.decide("r1", Outcome.APPROVED, "b")
    rejected = audit.events("rejected_decision")
    assert len(rejected) == 1 and rejected[0].payload["rejected_because"] == because
    assert rejected[0].payload["operator"] == "b"


def test_expiry_is_recorded_once_by_the_system() -> None:
    hub, audit, clock, events = make()
    hub.add_recommendation(rec(expires=130.0))
    clock.t = 131.0
    assert len(hub.sweep()) == 1 and hub.sweep() == []
    decisions = audit.events("decision")
    assert [(d.payload["outcome"], d.payload["operator"]) for d in decisions] == [
        ("EXPIRED", "system")
    ]
    assert events[-1]["type"] == "decision"
    assert hub.state()["open_recommendations"] == []


def test_a_client_cannot_send_expired_and_duplicates_are_refused() -> None:
    hub, _, _, _ = make()
    hub.add_recommendation(rec())
    with pytest.raises(InvalidOutcome):
        hub.decide("r1", Outcome.EXPIRED, "a")
    with pytest.raises(DuplicateRecommendation):
        hub.add_recommendation(rec())


def test_audit_log_is_append_only() -> None:
    import sqlite3

    audit = AuditLog()
    audit.append(1.0, "k", None, {})
    with pytest.raises(sqlite3.DatabaseError):
        audit._db.execute("UPDATE events SET kind = 'x'")
    with pytest.raises(sqlite3.DatabaseError):
        audit._db.execute("DELETE FROM events")
    assert len(audit.events()) == 1


def test_a_recommendation_needs_something_to_do_and_a_valid_window() -> None:
    with pytest.raises(ValueError):
        Recommendation("r", "u", 1.0, 2.0, ReasonCode.STALE, None, (), "x")
    with pytest.raises(ValueError):
        Recommendation("r", "u", 5.0, 5.0, ReasonCode.STALE, Command.HOLD, (), "x")


def test_trust_messages_close_recommendations_that_expired_unanswered() -> None:
    hub, audit, clock, events = make()
    hub.add_recommendation(rec(expires=130.0))
    clock.t = 131.0
    hub.ingest_navtrust(trust())  # no decide(), no state(): only trust arriving
    [decision] = audit.events("decision")
    assert (decision.payload["outcome"], decision.payload["operator"]) == ("EXPIRED", "system")
    assert [e["type"] for e in events][-2:] == ["decision", "navtrust"]


@pytest.mark.parametrize("operator", ["", "   ", "\t\n"])
def test_a_decision_must_name_the_operator(operator: str) -> None:
    # C2-01: every command needs a recorded operator approval; a blank name records nobody.
    hub, audit, _, _ = make()
    hub.add_recommendation(rec())
    with pytest.raises(InvalidOperator):
        hub.decide("r1", Outcome.APPROVED, operator)
    assert hub.decision_for("r1") is None
    (rejected,) = audit.events("rejected_decision")
    assert rejected.payload["rejected_because"] == "invalid_operator"
    # the recommendation stays open for a named operator
    assert hub.decide("r1", Outcome.APPROVED, "Duty operator").outcome is Outcome.APPROVED
