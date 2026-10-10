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
        event = ws.receive_json()
        assert (event["type"], event["data"]) == ("navtrust", NAVTRUST)
        assert event["server_s"] == 100.0  # the hub clock, for client-side countdowns
        c.post("/recommendations", json=REC)
        assert ws.receive_json()["type"] == "recommendation"
        c.post("/decisions", json={"recommendation_id": "r1", "outcome": "DENIED", "operator": "d"})
        ev = ws.receive_json()
        assert ev["type"] == "decision" and ev["data"]["outcome"] == "DENIED"


def test_positions_and_origin_reach_state_and_websocket(client: tuple[TestClient, Clock]) -> None:
    c, _ = client
    with c.websocket_connect("/ws") as ws:
        ws.receive_json()
        pos = {"vehicle_id": "uav1", "lat_deg": 47.4, "lon_deg": 8.55, "alt_m": 30.0}
        assert c.post("/positions", json=pos).status_code == 204
        event = ws.receive_json()
        assert event["type"] == "position" and event["data"]["lat_deg"] == 47.4
        assert c.post("/origin", json={"lat_deg": 47.39, "lon_deg": 8.54}).status_code == 204
        assert ws.receive_json()["type"] == "origin"
    state = c.get("/state").json()
    assert state["positions"]["uav1"]["alt_m"] == 30.0
    assert state["origin"] == {"lat_deg": 47.39, "lon_deg": 8.54} and state["server_s"] == 100.0
    assert c.get("/fleet").json()["origin"]["lon_deg"] == 8.54


def test_bad_positions_are_422(client: tuple[TestClient, Clock]) -> None:
    c, _ = client
    assert (
        c.post(
            "/positions", json={"vehicle_id": "u", "lat_deg": 95, "lon_deg": 0, "alt_m": 1}
        ).status_code
        == 422
    )
    assert c.post("/positions", json={"vehicle_id": "u"}).status_code == 422
    assert c.post("/origin", json={"lat_deg": 0, "lon_deg": 200}).status_code == 422


def test_console_is_served_without_shadowing_the_api(tmp_path) -> None:  # type: ignore[no-untyped-def]
    (tmp_path / "index.html").write_text("<title>console</title>", encoding="utf-8")
    c = TestClient(create_app(Hub(AuditLog(), Clock()), console_dir=tmp_path))
    assert "console" in c.get("/").text
    assert c.get("/state").json()["vehicles"] == {}


def test_source_label_defaults_to_live_and_can_be_marked_as_a_replay(
    client: tuple[TestClient, Clock],
) -> None:
    c, _ = client
    assert c.get("/state").json()["source"] == "live"
    assert c.post("/source", json={"label": "REPLAY DEMO"}).status_code == 204
    assert c.get("/state").json()["source"] == "REPLAY DEMO"
    assert c.post("/source", json={"label": "  "}).status_code == 422
