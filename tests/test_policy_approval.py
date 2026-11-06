"""LL-02, issue 76, ADR 0004 item 5 and 7: the policy is approved once per mission as an audited
approval, and what a vehicle did on its own is reported when the link returns and audited."""

import itertools
from typing import Any

import pytest

from c2.audit import AuditLog
from c2.hub import (
    Hub,
    InvalidPolicy,
    MalformedReportId,
    OutsideBinding,
    OutsidePolicy,
    UnknownPolicy,
)
from navtrust.types import NavTrust, TrustState

UNBOUND = {
    "entries": [{"reason": "INCONSISTENT_INNOVATION", "link": "NO_LINK", "action": "LAND"}],
    "wait_s": 5.0,
}
POLICY = {**UNBOUND, "mission_id": "m1", "vehicles": ["uav1"]}  # ADR 0004 item 5, 2026-11-06


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


_report_ids = itertools.count(1)


def report(hub: Hub, approval: dict[str, Any], **over: Any) -> None:
    hub.report_onboard_action(
        {
            "vehicle_id": "uav1", "t_s": 51.0, "action": "LAND",
            "reason": "INCONSISTENT_INNOVATION", "link_down_s": 5.2,
            "policy_audit_id": approval["audit_id"], "policy_sha256": approval["sha256"],
            "mission_id": "m1", "report_id": f"r{next(_report_ids)}",
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


NAV = NavTrust("uav1", 1.0, TrustState.GREEN, None, 5.0, 0.99, 0.5)


@pytest.mark.parametrize(
    "over",
    [
        {"action": "RTL"},  # the policy names LAND only
        {"reason": "GNSS_LOSS"},  # a reason it has no entry for
        {"link_down_s": 3.0},  # the vehicle may act only after the wait (5 s) has passed
    ],
)
def test_a_report_the_cited_policy_does_not_authorise_is_refused_and_audited(
    over: dict[str, Any],
) -> None:
    hub, audit, clock, events = make()
    approval = hub.approve_policy(POLICY, "daniel", max_wait_s=10.0)
    hub.ingest_navtrust(NAV)
    clock.t += 10.0  # silent: the backend has marked the vehicle NO_LINK
    assert hub.state()["links"]["uav1"]["state"] == "NO_LINK"
    with pytest.raises(OutsidePolicy):
        report(hub, approval, **over)
    [row] = audit.events("rejected_onboard_action")
    assert row.payload["rejected_because"] == "outside_policy"
    assert audit.events("onboard_action") == []
    assert (
        hub.state()["links"]["uav1"]["state"] == "NO_LINK"
    )  # a refused report is not a sign of life
    assert not [e for e in events if e["type"] == "onboard_action"]


def test_a_report_inside_the_policy_is_still_accepted() -> None:
    hub, audit, _, _ = make()
    approval = hub.approve_policy(POLICY, "daniel", max_wait_s=10.0)
    report(hub, approval)
    assert len(audit.events("onboard_action")) == 1


def test_the_outcome_of_an_onboard_land_is_audited_and_an_unknown_one_is_refused() -> None:
    from c2.hub import InvalidOutcome

    hub, audit, _, _ = make()
    approval = hub.approve_policy(POLICY, "daniel", max_wait_s=10.0)
    report(hub, approval, outcome="failed")
    [row] = audit.events("onboard_action")
    assert row.payload["outcome"] == "failed"
    with pytest.raises(InvalidOutcome):
        report(hub, approval, outcome="probably")
    [rejected] = audit.events("rejected_onboard_action")
    assert rejected.payload["rejected_because"] == "invalid_outcome"
    assert len(audit.events("onboard_action")) == 1


@pytest.mark.parametrize(
    "policy",
    [
        UNBOUND,  # no mission, no vehicles
        {**UNBOUND, "mission_id": "m1"},  # no vehicles
        {**UNBOUND, "vehicles": ["uav1"]},  # no mission
        {**POLICY, "mission_id": "  "},
        {**POLICY, "vehicles": []},
        {**POLICY, "vehicles": "uav1"},  # a string, not a list
        {**POLICY, "vehicles": ["uav1", "uav1"]},
    ],
)
def test_a_policy_not_bound_to_a_mission_and_its_vehicles_is_not_approved(
    policy: dict[str, Any],
) -> None:
    hub, audit, _, _ = make()
    with pytest.raises(InvalidPolicy):
        hub.approve_policy(policy, "daniel", max_wait_s=10.0)
    assert audit.events("policy_approved") == []


@pytest.mark.parametrize(
    "over",
    [
        {"vehicle_id": "uav2"},  # the policy covers uav1 only
        {"mission_id": "m2"},  # a report for another mission than the one approved
        {"mission_id": None},
    ],
)
def test_a_report_outside_the_policys_mission_and_vehicles_is_refused_and_audited(
    over: dict[str, Any],
) -> None:
    hub, audit, clock, events = make()
    approval = hub.approve_policy(POLICY, "daniel", max_wait_s=10.0)
    hub.ingest_navtrust(NAV)
    hub.ingest_navtrust(NavTrust("uav2", 1.0, TrustState.GREEN, None, 5.0, 0.99, 0.5))
    clock.t += 10.0  # both vehicles silent: NO_LINK
    with pytest.raises(OutsideBinding):
        report(hub, approval, **over)
    [row] = audit.events("rejected_onboard_action")
    assert row.payload["rejected_because"] == "outside_binding"
    assert audit.events("onboard_action") == []
    assert hub.state()["links"][over.get("vehicle_id", "uav1")]["state"] == "NO_LINK"
    assert not [e for e in events if e["type"] == "onboard_action"]


def test_a_repeated_report_is_acknowledged_once_and_neither_audited_nor_published_again() -> None:
    hub, audit, clock, events = make()
    approval = hub.approve_policy(POLICY, "daniel", max_wait_s=10.0)
    hub.ingest_navtrust(NAV)
    report(hub, approval, report_id="a1")
    clock.t += 10.0  # silent again: NO_LINK
    assert hub.state()["links"]["uav1"]["state"] == "NO_LINK"
    report(hub, approval, report_id="a1")  # the vehicle sent it again; no error
    assert len(audit.events("onboard_action")) == 1
    [dup] = audit.events("duplicate_onboard_action")
    assert dup.payload["report_id"] == "a1" and dup.vehicle_id == "uav1"
    assert len([e for e in events if e["type"] == "onboard_action"]) == 1
    assert hub.state()["links"]["uav1"]["state"] == "NO_LINK"  # no second sign of life


def test_the_same_id_from_another_vehicle_or_mission_is_a_different_report() -> None:
    hub, audit, _, _ = make()
    bound = {**POLICY, "vehicles": ["uav1", "uav2"]}
    approval = hub.approve_policy(bound, "daniel", max_wait_s=10.0)
    report(hub, approval, report_id="a1")
    report(hub, approval, report_id="a1", vehicle_id="uav2")
    assert len(audit.events("onboard_action")) == 2


def test_a_repeat_is_still_recognised_after_a_restart() -> None:
    audit = AuditLog()
    first = Hub(audit, Clock())
    approval = first.approve_policy(POLICY, "daniel", max_wait_s=10.0)
    report(first, approval, report_id="a1")
    second = Hub(audit, Clock())  # the same audit log, a new run
    report(second, approval, report_id="a1")
    assert len(audit.events("onboard_action")) == 1


@pytest.mark.parametrize("bad", [None, "", "   ", 7, "x" * 65, ["a"]])
def test_a_report_without_a_usable_id_is_refused_and_audited(bad: Any) -> None:
    hub, audit, clock, _ = make()
    approval = hub.approve_policy(POLICY, "daniel", max_wait_s=10.0)
    hub.ingest_navtrust(NAV)
    clock.t += 10.0
    with pytest.raises(MalformedReportId):
        report(hub, approval, report_id=bad)
    [row] = audit.events("rejected_onboard_action")
    assert row.payload["rejected_because"] == "malformed_report_id"
    assert audit.events("onboard_action") == []
    assert hub.state()["links"]["uav1"]["state"] == "NO_LINK"


def test_a_report_with_no_id_field_at_all_is_refused() -> None:
    hub, _, _, _ = make()
    approval = hub.approve_policy(POLICY, "daniel", max_wait_s=10.0)
    body = {
        "vehicle_id": "uav1", "t_s": 51.0, "action": "LAND",
        "reason": "INCONSISTENT_INNOVATION", "link_down_s": 5.2,
        "policy_audit_id": approval["audit_id"], "policy_sha256": approval["sha256"],
        "mission_id": "m1",
    }  # fmt: skip
    with pytest.raises(MalformedReportId):
        hub.report_onboard_action(body)
