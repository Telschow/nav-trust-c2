"""ADR 0004 handoff, issue 76: a vehicle pulls the approved policy for its mission before launch.
The pull is audited, so delivery is on record, and the answer carries the backend's clock once so
the vehicle can age the policy on its own clock."""

from typing import Any

import pytest

from c2.audit import AuditLog
from c2.hub import Hub, OutsideBinding, UnknownPolicy

POLICY = {
    "entries": [{"reason": "INCONSISTENT_INNOVATION", "link": "NO_LINK", "action": "LAND"}],
    "wait_s": 5.0,
    "mission_id": "m1",
    "vehicles": ["uav1", "uav2"],
}


class Clock:
    t = 100.0

    def __call__(self) -> float:
        return self.t


def make() -> tuple[Hub, AuditLog, Clock]:
    audit, clock = AuditLog(), Clock()
    return Hub(audit, clock), audit, clock


def test_a_listed_vehicle_gets_the_approval_record_and_the_backends_clock() -> None:
    hub, audit, clock = make()
    approval = hub.approve_policy(POLICY, "daniel", max_wait_s=10.0)
    clock.t = 160.0
    record = hub.deliver_policy("m1", "uav1")
    assert record == {**approval, "server_s": 160.0}
    [row] = audit.events("policy_delivered")
    assert row.vehicle_id == "uav1"
    assert row.payload == {
        "mission_id": "m1",
        "policy_audit_id": approval["audit_id"],
        "sha256": approval["sha256"],
    }


def test_a_vehicle_the_policy_does_not_cover_is_refused_and_nothing_is_delivered() -> None:
    hub, audit, _ = make()
    hub.approve_policy(POLICY, "daniel", max_wait_s=10.0)
    with pytest.raises(OutsideBinding):
        hub.deliver_policy("m1", "uav3")
    assert audit.events("policy_delivered") == []
    [row] = audit.events("rejected_policy_delivery")
    assert row.vehicle_id == "uav3"
    assert row.payload == {"mission_id": "m1", "rejected_because": "outside_binding"}


def test_a_mission_with_no_approved_policy_is_refused() -> None:
    hub, audit, _ = make()
    hub.approve_policy(POLICY, "daniel", max_wait_s=10.0)
    with pytest.raises(UnknownPolicy):
        hub.deliver_policy("m2", "uav1")
    assert audit.events("policy_delivered") == []
    [row] = audit.events("rejected_policy_delivery")
    assert row.payload == {"mission_id": "m2", "rejected_because": "unknown_policy"}


def test_a_mission_approved_twice_delivers_the_latest_approval() -> None:
    hub, _, clock = make()
    hub.approve_policy(POLICY, "daniel", max_wait_s=10.0)
    clock.t = 120.0
    later: dict[str, Any] = {**POLICY, "wait_s": 6.0}
    second = hub.approve_policy(later, "daniel", max_wait_s=10.0)
    assert hub.deliver_policy("m1", "uav1")["audit_id"] == second["audit_id"]
