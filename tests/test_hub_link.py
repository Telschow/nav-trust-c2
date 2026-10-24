"""LL-01, link health: a vehicle that goes silent is NO_LINK, and the next report restores it."""

from typing import Any

from c2.audit import AuditLog
from c2.hub import Hub
from navtrust.types import NavTrust, TrustState


class Clock:
    def __init__(self) -> None:
        self.t = 100.0

    def __call__(self) -> float:
        return self.t


def report(vehicle: str = "uav1") -> NavTrust:
    return NavTrust(vehicle, 1.0, TrustState.GREEN, None, 0.15, 1.0)


def make(timeout_s: float = 2.0) -> tuple[Hub, AuditLog, Clock, list[dict[str, Any]]]:
    audit, clock = AuditLog(), Clock()
    events: list[dict[str, Any]] = []
    hub = Hub(audit, clock, link_timeout_s=timeout_s)
    hub.subscribe(events.append)
    return hub, audit, clock, events


def link_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [e["data"] for e in events if e["type"] == "link"]


def test_silence_past_the_timeout_marks_the_vehicle_no_link_once() -> None:
    hub, audit, clock, events = make()
    hub.ingest_navtrust(report())
    clock.t = 102.5
    hub.sweep()
    hub.sweep()  # nothing changes the second time
    assert link_events(events) == [
        {"vehicle_id": "uav1", "state": "NO_LINK", "last_report_age_s": 2.5}
    ]
    [row] = audit.events("link_change")
    assert row.vehicle_id == "uav1" and row.t_s == 102.5
    assert row.payload == {
        "state": "NO_LINK",
        "previous_state": "LINK_OK",
        "last_report_age_s": 2.5,
        "link_timeout_s": 2.0,
    }


def test_exactly_the_timeout_is_still_a_live_link() -> None:
    hub, audit, clock, events = make(timeout_s=2.0)
    hub.ingest_navtrust(report())
    clock.t = 102.0
    hub.sweep()
    assert audit.events("link_change") == [] and link_events(events) == []
    clock.t = 102.001
    hub.sweep()
    assert [e["state"] for e in link_events(events)] == ["NO_LINK"]


def test_the_next_trust_report_restores_the_link_and_records_how_long_it_was_silent() -> None:
    hub, audit, clock, events = make()
    hub.ingest_navtrust(report())
    clock.t = 105.0
    hub.sweep()
    hub.ingest_navtrust(report())
    assert [(e["state"], e["last_report_age_s"]) for e in link_events(events)] == [
        ("NO_LINK", 5.0),
        ("LINK_OK", 5.0),
    ]
    assert [r.payload["state"] for r in audit.events("link_change")] == ["NO_LINK", "LINK_OK"]


def test_a_position_report_alone_keeps_a_vehicle_alive_and_restores_it() -> None:
    hub, _, clock, events = make()
    hub.ingest_navtrust(report())
    clock.t = 101.5
    hub.ingest_position("uav1", 47.0, 8.0, 30.0)
    clock.t = 103.0  # 1.5 s since the position, 3.0 s since the trust report
    hub.sweep()
    assert link_events(events) == []
    clock.t = 106.0
    hub.sweep()
    hub.ingest_position("uav1", 47.0, 8.0, 30.0)
    assert [e["state"] for e in link_events(events)] == ["NO_LINK", "LINK_OK"]


def test_an_outage_nobody_swept_is_still_recorded_when_the_vehicle_returns() -> None:
    hub, audit, clock, _ = make()
    hub.ingest_position("uav1", 47.0, 8.0, 30.0)
    clock.t = 110.0
    hub.ingest_position("uav1", 47.0, 8.0, 30.0)  # no sweep ran in between
    assert [r.payload["state"] for r in audit.events("link_change")] == ["NO_LINK", "LINK_OK"]


def test_state_reports_each_vehicles_link_and_the_age_of_its_last_report() -> None:
    hub, _, clock, _ = make()
    hub.ingest_navtrust(report("uav1"))
    clock.t = 101.0
    hub.ingest_navtrust(report("uav2"))
    clock.t = 103.5  # uav1 has been silent 3.5 s, uav2 2.5 s; the 2 s timeout has passed for both
    hub.ingest_position("uav2", 47.0, 8.0, 30.0)  # uav2 is heard again
    clock.t = 104.0
    state = hub.state()
    assert state["links"] == {
        "uav1": {"vehicle_id": "uav1", "state": "NO_LINK", "last_report_age_s": 4.0},
        "uav2": {"vehicle_id": "uav2", "state": "LINK_OK", "last_report_age_s": 0.5},
    }
    # the last trust state is still there, to be shown as last known
    assert set(state["vehicles"]) == {"uav1", "uav2"}


def test_a_vehicle_never_heard_from_has_no_link_entry() -> None:
    hub, _, _, _ = make()
    assert hub.state()["links"] == {}


def test_a_vehicle_is_reachable_unless_it_has_been_silent_past_the_timeout() -> None:
    hub, _, clock, _ = make()
    assert hub.is_reachable("uav9")  # never heard from: no evidence the link is lost
    hub.ingest_navtrust(report())
    assert hub.is_reachable("uav1")
    clock.t = 102.5  # no sweep has run
    assert not hub.is_reachable("uav1")
    hub.ingest_navtrust(report())
    assert hub.is_reachable("uav1")
