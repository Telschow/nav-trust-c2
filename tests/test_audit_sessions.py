"""The audit log proves which approval authorised which command, across backend restarts
(issue 159): sessions are marked, recommendation ids differ between sessions, every command row
names the decision row that authorised it, and a verifier checks that on a database."""

import asyncio
from pathlib import Path

from c2.allocator import assign, split_area
from c2.audit import AuditLog
from c2.audit_verify import problems
from c2.dryrun import DryRunExecutor
from c2.fleet import FleetState
from c2.gate import CommandGate
from c2.hub import Hub
from c2.messages import Outcome
from c2.recommender import Recommender
from navtrust.types import NavTrust, ReasonCode, TrustState

RED = NavTrust("uav2", 5.0, TrustState.RED, ReasonCode.INCONSISTENT_INNOVATION, float("inf"), 0.0)
GREEN = NavTrust("uav1", 5.0, TrustState.GREEN, None, 5.0, 0.99, 0.5)


class Clock:
    t = 5.0

    def __call__(self) -> float:
        return self.t


def session(db: Path, approve: bool = True) -> tuple[Hub, str]:
    """One backend run on the database: it recommends LAND for uav2 and the operator approves."""
    clock = Clock()  # every session's clock starts again, as a restarted backend's does
    hub = Hub(AuditLog(db), clock)
    session_id = hub.start_session()
    fleet = FleetState(assign(split_area(900, 900, 2), ["uav1", "uav2"]), positions={})
    recommender = Recommender(clock)
    recommender.use_session(session_id)
    hub.ingest_navtrust(GREEN)
    fleet.positions["uav1"] = (0.0, 0.0)
    msg = RED
    hub.ingest_navtrust(msg)
    [rec] = recommender.observe(msg, fleet)
    hub.add_recommendation(rec)
    if approve:
        hub.decide(rec.id, Outcome.APPROVED, "daniel")
        asyncio.run(CommandGate(hub, fleet, DryRunExecutor()).execute(rec.id))
    return hub, rec.id


def test_two_sessions_on_one_database_never_reuse_a_recommendation_id(tmp_path: Path) -> None:
    db = tmp_path / "audit.sqlite"
    _, first = session(db)
    _, second = session(db)
    assert first != second
    rows = AuditLog(db).events("recommendation")
    assert len({r.payload["id"] for r in rows}) == len(rows) == 2


def test_each_session_starts_with_a_row_that_says_so(tmp_path: Path) -> None:
    db = tmp_path / "audit.sqlite"
    session(db)
    session(db)
    starts = AuditLog(db).events("session_started")
    assert len(starts) == 2 and starts[0].payload["session_id"] != starts[1].payload["session_id"]
    assert "wall_clock_utc" in starts[0].payload


def test_every_command_row_names_the_decision_row_that_authorised_it(tmp_path: Path) -> None:
    db = tmp_path / "audit.sqlite"
    session(db)
    log = AuditLog(db)
    [decision] = log.events("decision")
    commands = [e for e in log.events() if e.kind.startswith("command_")]
    assert [e.kind for e in commands] == [
        "command_sent",
        "command_acknowledged",
        "command_executed",
    ]
    assert {e.payload["decision_audit_id"] for e in commands} == {decision.id}


def test_the_verifier_passes_a_database_the_backend_produced_across_two_restarts(
    tmp_path: Path,
) -> None:
    db = tmp_path / "audit.sqlite"
    session(db)
    session(db)
    assert problems(db) == []


def test_the_verifier_fails_a_command_that_has_no_approval(tmp_path: Path) -> None:
    db = tmp_path / "audit.sqlite"
    log = AuditLog(db)
    log.append(0.0, "session_started", None, {"session_id": "s1", "wall_clock_utc": "x"})
    log.append(1.0, "command_sent", "uav2", {"recommendation_id": "rec-1", "action": "LAND uav2"})
    [problem] = problems(db)
    assert "command_sent" in problem and "decision" in problem


def test_the_verifier_fails_a_command_whose_decision_was_a_denial(tmp_path: Path) -> None:
    db = tmp_path / "audit.sqlite"
    hub, rec_id = session(db, approve=False)
    hub.decide(rec_id, Outcome.DENIED, "daniel")
    [denial] = hub.audit.events("decision")
    hub.audit.append(
        9.0,
        "command_sent",
        "uav2",
        {"recommendation_id": rec_id, "action": "LAND uav2", "decision_audit_id": denial.id},
    )
    assert any("approv" in p for p in problems(db))


def test_the_verifier_fails_a_decision_taken_in_an_earlier_session(tmp_path: Path) -> None:
    db = tmp_path / "audit.sqlite"
    hub, rec_id = session(db)
    [decision] = hub.audit.events("decision")
    later = Hub(AuditLog(db), Clock())
    later.start_session()
    later.audit.append(
        1.0,
        "command_sent",
        "uav2",
        {"recommendation_id": rec_id, "action": "LAND uav2", "decision_audit_id": decision.id},
    )
    assert any("session" in p for p in problems(db))


def test_an_app_gives_its_recommender_the_session_so_no_caller_can_forget_it(
    tmp_path: Path,
) -> None:
    from fastapi.testclient import TestClient

    from c2.server import create_app

    db = tmp_path / "audit.sqlite"
    ids = []
    for _ in range(2):  # two backend runs on one database, the recommender built with no session
        clock = Clock()
        hub = Hub(AuditLog(db), clock)
        fleet = FleetState(assign(split_area(900, 900, 2), ["uav1", "uav2"]), positions={})
        fleet.positions["uav1"] = (0.0, 0.0)
        client = TestClient(create_app(hub, fleet=fleet, recommender=Recommender(clock)))
        for msg in (GREEN, RED):
            body = {
                "vehicle_id": msg.vehicle_id, "stamp_s": msg.stamp_s, "state": msg.state.value,
                "reason": msg.reason.value if msg.reason else None, "horizontal_bound_m": None,
                "confidence": msg.confidence, "headroom": msg.headroom,
            }  # fmt: skip
            client.post("/navtrust", json=body)
        ids.append(hub.state()["open_recommendations"][0]["id"])
    assert ids[0] != ids[1]
    assert len(AuditLog(db).events("session_started")) == 2


def forged(db: Path, **changes: str) -> None:
    """A command_sent row that cites the real approval but differs from the recommendation."""
    log = AuditLog(db)
    [decision] = log.events("decision")
    [rec] = log.events("recommendation")
    sent = {
        "recommendation_id": rec.payload["id"],
        "action": "LAND uav2",
        "decision_audit_id": decision.id,
    }
    log.append(9.0, "command_sent", changes.pop("vehicle", "uav2"), {**sent, **changes})


def test_the_verifier_fails_a_command_to_another_vehicle_than_the_one_recommended(
    tmp_path: Path,
) -> None:
    db = tmp_path / "audit.sqlite"
    session(db)
    forged(db, vehicle="uav1", action="LAND uav1")
    assert any("uav2" in p and "uav1" in p for p in problems(db))


def test_the_verifier_fails_an_action_other_than_the_one_recommended(tmp_path: Path) -> None:
    db = tmp_path / "audit.sqlite"
    session(db)
    forged(db, action="RTL uav2")
    assert any("LAND" in p and "RTL" in p for p in problems(db))


def test_the_verifier_fails_a_command_whose_recommendation_row_is_missing(tmp_path: Path) -> None:
    db = tmp_path / "audit.sqlite"
    log = AuditLog(db)
    log.append(0.0, "session_started", None, {"session_id": "s1", "wall_clock_utc": "x"})
    approval = log.append(
        1.0, "decision", "uav2", {"recommendation_id": "r9", "outcome": "APPROVED", "operator": "d"}
    )
    sent = {"recommendation_id": "r9", "action": "LAND uav2", "decision_audit_id": approval.id}
    log.append(2.0, "command_sent", "uav2", sent)
    [problem] = problems(db)
    assert "no recommendation row r9" in problem
