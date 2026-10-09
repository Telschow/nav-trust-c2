from typing import Any

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from c2.audit import AuditLog  # noqa: E402
from c2.hub import Hub  # noqa: E402
from c2.server import create_app  # noqa: E402

NAVTRUST = {
    "vehicle_id": "uav2",
    "stamp_s": 5.0,
    "state": "RED",
    "reason": "GNSS_LOSS",
    "horizontal_bound_m": None,
    "confidence": 0.0,
}
REC = {
    "id": "r1",
    "vehicle_id": "uav2",
    "created_s": 100.0,
    "expires_s": 130.0,
    "reason": "GNSS_LOSS",
    "command": "RTL",
    "sector_moves": [{"sector_id": "S2", "to_vehicle": "uav3"}],
    "rationale": "uav2 lost GNSS",
}


class Clock:
    t = 100.0

    def __call__(self) -> float:
        return self.t


@pytest.fixture
def client() -> tuple[TestClient, Clock]:
    clock = Clock()
    return TestClient(create_app(Hub(AuditLog(), clock))), clock


def test_navtrust_in_state_out(client: tuple[TestClient, Clock]) -> None:
    c, _ = client
    assert c.post("/navtrust", json=NAVTRUST).status_code == 204
    assert c.get("/state").json()["vehicles"]["uav2"]["state"] == "RED"


def test_bad_messages_are_422(client: tuple[TestClient, Clock]) -> None:
    c, _ = client
    assert c.post("/navtrust", json={"vehicle_id": "x"}).status_code == 422
    assert c.post("/navtrust", json={**NAVTRUST, "state": "BLUE"}).status_code == 422
    assert (
        c.post("/recommendations", json={**REC, "command": None, "sector_moves": []}).status_code
        == 422
    )
    assert c.post("/decisions", json={"recommendation_id": "r1"}).status_code == 422


def test_approve_flow_and_audit(client: tuple[TestClient, Clock]) -> None:
    c, clock = client
    assert c.post("/recommendations", json=REC).status_code == 201
    assert [r["id"] for r in c.get("/state").json()["open_recommendations"]] == ["r1"]
    clock.t = 110.0
    r = c.post(
        "/decisions", json={"recommendation_id": "r1", "outcome": "APPROVED", "operator": "daniel"}
    )
    assert r.status_code == 200 and r.json()["decided_s"] == 110.0
    assert c.get("/state").json()["open_recommendations"] == []
    kinds = [e["kind"] for e in c.get("/audit").json()]
    assert kinds == ["recommendation", "decision"]
    assert c.get("/audit", params={"kind": "decision"}).json()[0]["payload"]["operator"] == "daniel"


@pytest.mark.parametrize(
    ("prepare", "status"),
    [("none", 404), ("decided", 409), ("expired", 410)],
)
def test_decision_errors_map_to_http_codes(
    client: tuple[TestClient, Clock], prepare: str, status: int
) -> None:
    c, clock = client
    body = {"recommendation_id": "r1", "outcome": "APPROVED", "operator": "daniel"}
    if prepare != "none":
        c.post("/recommendations", json=REC)
    if prepare == "decided":
        c.post("/decisions", json={**body, "outcome": "DENIED"})
    if prepare == "expired":
        clock.t = 131.0
    assert c.post("/decisions", json=body).status_code == status
    assert c.get("/audit", params={"kind": "rejected_decision"}).json()


def test_client_cannot_send_expired(client: tuple[TestClient, Clock]) -> None:
    c, _ = client
    c.post("/recommendations", json=REC)
    r = c.post(
        "/decisions", json={"recommendation_id": "r1", "outcome": "EXPIRED", "operator": "x"}
    )
    assert r.status_code == 422


def test_duplicate_recommendation_is_409(client: tuple[TestClient, Clock]) -> None:
    c, _ = client
    assert c.post("/recommendations", json=REC).status_code == 201
    assert c.post("/recommendations", json=REC).status_code == 409


def test_websocket_sends_state_then_live_events(client: tuple[TestClient, Clock]) -> None:
    c, _ = client
    c.post("/navtrust", json={**NAVTRUST, "vehicle_id": "uav1", "state": "GREEN", "reason": None})
    with c.websocket_connect("/ws") as ws:
        first: dict[str, Any] = ws.receive_json()
        assert first["type"] == "state" and "uav1" in first["data"]["vehicles"]
        c.post("/navtrust", json=NAVTRUST)
        assert ws.receive_json() == {"type": "navtrust", "data": NAVTRUST}
        c.post("/recommendations", json=REC)
        assert ws.receive_json()["type"] == "recommendation"
        c.post("/decisions", json={"recommendation_id": "r1", "outcome": "DENIED", "operator": "d"})
        ev = ws.receive_json()
        assert ev["type"] == "decision" and ev["data"]["outcome"] == "DENIED"
