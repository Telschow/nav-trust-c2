"""Issue 76, ADR 0004 item 5 and 7: the policy is approved once per mission as an audited
approval, and what a vehicle did on its own is reported when the link returns and audited."""

from typing import Any

import pytest

from c2.audit import AuditLog
from c2.hub import Hub, InvalidPolicy, UnknownPolicy
from navtrust.types import NavTrust, TrustState

POLICY = {
    "entries": [{"reason": "INCONSISTENT_INNOVATION", "link": "NO_LINK", "action": "LAND"}],
    "wait_s": 5.0,
}


class Clock:
    t = 100.0

    def __call__(self) -> float:
        return self.t


def make() -> tuple[Hub, AuditLog, Clock, list[dict[str, Any]]]:
    audit, clock = AuditLog(), Clock()
    events: list[dict[str, Any]] = []
    hub = Hub(audit, clock)
    hub.subscribe(events.append)
    return hub, audit, clock, events


def report(hub: Hub, approval: dict[str, Any], **over: Any) -> None:
    hub.report_onboard_action(
        {
            "vehicle_id": "uav1", "t_s": 51.0, "action": "LAND",
            "reason": "INCONSISTENT_INNOVATION", "link_down_s": 5.2,
            "policy_audit_id": approval["audit_id"], "policy_sha256": approval["sha256"],
            **over,
        }
    )  # fmt: skip


def test_an_approved_policy_is_an_audited_row_with_its_hash_and_returns_the_reference() -> None:
    hub, audit, clock, _ = make()
    approval = hub.approve_policy(POLICY, "daniel", max_wait_s=10.0)
    [row] = audit.events("policy_approved")
    assert approval["audit_id"] == row.id and approval["sha256"] == row.payload["sha256"]
    assert row.payload["operator"] == "daniel" and row.payload["policy"] == POLICY
    assert approval["approved_s"] == clock.t and approval["policy"] == POLICY
    assert approval["max_age_s"] > 0


@pytest.mark.parametrize(
    "policy",
    [
        {**POLICY, "wait_s": 10.0},  # not shorter than PX4's data-link-loss time
        {**POLICY, "wait_s": 0},
        {"entries": [{"reason": "STALE", "link": "NO_LINK", "action": "RTL"}], "wait_s": 5.0},
        {"entries": [{"reason": "MOON", "link": "NO_LINK", "action": "LAND"}], "wait_s": 5.0},
    ],
)
def test_a_policy_the_vehicle_would_refuse_is_not_approved(policy: dict[str, Any]) -> None:
    hub, audit, _, _ = make()
    with pytest.raises(InvalidPolicy):
        hub.approve_policy(policy, "daniel", max_wait_s=10.0)
    assert audit.events("policy_approved") == []


def test_an_approval_needs_a_named_operator() -> None:
    hub, audit, _, _ = make()
    with pytest.raises(Exception):  # noqa: B017 - InvalidOperator, as for a decision
        hub.approve_policy(POLICY, "  ", max_wait_s=10.0)
    assert audit.events("policy_approved") == []


def test_an_onboard_action_is_audited_with_its_policy_reference_and_published() -> None:
    hub, audit, _, events = make()
    approval = hub.approve_policy(POLICY, "daniel", max_wait_s=10.0)
    report(hub, approval)
    [row] = audit.events("onboard_action")
    assert row.vehicle_id == "uav1"
    assert row.payload["policy_audit_id"] == approval["audit_id"]
    assert row.payload["reason"] == "INCONSISTENT_INNOVATION" and row.payload["action"] == "LAND"
    assert [e["type"] for e in events if e["type"] == "onboard_action"] == ["onboard_action"]


def test_a_report_citing_a_policy_that_was_never_approved_is_refused_and_audited() -> None:
    hub, audit, _, _ = make()
    approval = hub.approve_policy(POLICY, "daniel", max_wait_s=10.0)
    with pytest.raises(UnknownPolicy):
        report(hub, approval, policy_sha256="0" * 64)  # the hash does not match the audit row
    with pytest.raises(UnknownPolicy):
        report(hub, approval, policy_audit_id=999)
    assert audit.events("onboard_action") == []
    assert len(audit.events("rejected_onboard_action")) == 2


def test_the_outage_summary_lists_what_the_vehicle_did_on_its_own() -> None:
    hub, _, clock, events = make()
    approval = hub.approve_policy(POLICY, "daniel", max_wait_s=10.0)
    hub.ingest_navtrust(NavTrust("uav1", 1.0, TrustState.GREEN, None, 0.15, 1.0))
    clock.t = 110.0
    hub.sweep()  # no link
    clock.t = 120.0
    report(hub, approval)  # the vehicle is heard again and says what it did
    hub.ingest_navtrust(NavTrust("uav1", 2.0, TrustState.RED, None, float("inf"), 0.0))
    [summary] = [e["data"] for e in events if e["type"] == "outage_summary"]
    [action] = summary["onboard_actions"]
    assert action["action"] == "LAND" and action["policy_audit_id"] == approval["audit_id"]
