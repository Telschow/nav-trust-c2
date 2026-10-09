"""C2-01 and C2-02 through the HTTP API: trust in -> recommendation out -> decision -> command."""

from typing import Any

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from c2.allocator import assign, split_area  # noqa: E402
from c2.audit import AuditLog  # noqa: E402
from c2.dryrun import DryRunExecutor  # noqa: E402
from c2.fleet import FleetState  # noqa: E402
from c2.gate import CommandGate  # noqa: E402
from c2.hub import Hub  # noqa: E402
from c2.recommender import Recommender  # noqa: E402
from c2.server import create_app  # noqa: E402


class Clock:
    t = 10.0

    def __call__(self) -> float:
        return self.t


def trust(vehicle: str, state: str, reason: str | None = None) -> dict[str, Any]:
    green = state == "GREEN"
    return {
        "vehicle_id": vehicle,
        "stamp_s": 1.0,
        "state": state,
        "reason": reason,
        "horizontal_bound_m": 0.15 if green else None,
        "confidence": 1.0 if green else 0.0,
    }


@pytest.fixture
def system() -> tuple[TestClient, DryRunExecutor, Hub, Clock, FleetState]:
    clock, executor = Clock(), DryRunExecutor()
    hub = Hub(AuditLog(), clock)
    fleet = FleetState(
        assign(split_area(900, 900, 3), ["uav1", "uav2", "uav3"]),
        positions={"uav1": (0.0, 0.0), "uav2": (0.0, 5.0), "uav3": (0.0, 10.0)},
    )
    app = create_app(
        hub, fleet=fleet, recommender=Recommender(clock), gate=CommandGate(hub, fleet, executor)
    )
    client = TestClient(app)
    for v in ("uav1", "uav2", "uav3"):
        client.post("/navtrust", json=trust(v, "GREEN"))
    return client, executor, hub, clock, fleet


def open_ids(c: TestClient) -> list[str]:
    return [r["id"] for r in c.get("/state").json()["open_recommendations"]]


def test_red_vehicle_produces_a_recommendation_and_nothing_executes_yet(system) -> None:  # type: ignore[no-untyped-def]
    c, executor, hub, _, _ = system
    c.post("/navtrust", json=trust("uav2", "RED", "INCONSISTENT_INNOVATION"))
    [rid] = open_ids(c)
    rec = c.get("/state").json()["open_recommendations"][0]
    assert rec["command"] == "HOLD" and rec["sector_moves"][0]["sector_id"] == "S2"
    assert executor.log == []  # C2-01: a recommendation alone commands nothing
    assert hub.audit.events("command_executed") == [] and rid.startswith("rec-uav2")


def test_approval_executes_exactly_what_was_recommended(system) -> None:  # type: ignore[no-untyped-def]
    c, executor, hub, _, fleet = system
    c.post("/navtrust", json=trust("uav2", "RED", "INCONSISTENT_INNOVATION"))
    [rid] = open_ids(c)
    r = c.post(
        "/decisions", json={"recommendation_id": rid, "outcome": "APPROVED", "operator": "daniel"}
    )
    body = r.json()
    assert r.status_code == 200 and body["execution"]["executed"] is True
    assert body["execution"]["actions"][0] == "HOLD uav2"
    assert executor.log[0] == "hold uav2" and executor.log[1].startswith("retask")
    assert fleet.assignment["uav2"] == []
    kinds = [e.kind for e in hub.audit.events()]
    assert kinds.index("decision") < kinds.index("command_executed")


def test_denial_executes_nothing(system) -> None:  # type: ignore[no-untyped-def]
    c, executor, hub, _, fleet = system
    c.post("/navtrust", json=trust("uav2", "RED", "GNSS_LOSS"))
    [rid] = open_ids(c)
    r = c.post(
        "/decisions", json={"recommendation_id": rid, "outcome": "DENIED", "operator": "daniel"}
    )
    assert r.status_code == 200 and "execution" not in r.json()
    assert executor.log == [] and [s.id for s in fleet.assignment["uav2"]] == ["S2"]
    assert hub.audit.events("command_executed") == []


def test_an_expired_recommendation_cannot_be_approved_or_executed(system) -> None:  # type: ignore[no-untyped-def]
    c, executor, hub, clock, _ = system
    c.post("/navtrust", json=trust("uav2", "RED", "GNSS_LOSS"))
    [rid] = open_ids(c)
    clock.t += 120.0
    r = c.post(
        "/decisions", json={"recommendation_id": rid, "outcome": "APPROVED", "operator": "daniel"}
    )
    assert r.status_code == 410 and executor.log == []
    assert hub.audit.events("command_executed") == []


def test_fleet_endpoint_shows_the_assignment(system) -> None:  # type: ignore[no-untyped-def]
    c, _, _, _, _ = system
    fleet = c.get("/fleet").json()["assignment"]
    assert [s["id"] for s in fleet["uav2"]] == ["S2"]
    assert fleet["uav1"][0]["north"] == pytest.approx(300.0)
