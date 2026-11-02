"""Only the recommender can put a recommendation in front of the operator (issue 157).

A client may post one only when the app is built for tests or a demo, and even then the hub
decides when it was created and when it expires, and refuses vehicles it cannot command.
"""

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
    "reason": "INCONSISTENT_INNOVATION",
    "horizontal_bound_m": None,
    "confidence": 0.0,
    "headroom": 0.0,
}
LAND = {
    "id": "r1",
    "vehicle_id": "uav2",
    "created_s": 0.0,
    "expires_s": 1e12,
    "reason": "INCONSISTENT_INNOVATION",
    "command": "LAND",
    "sector_moves": [],
    "rationale": "posted by a client",
}
RE_TASK = {
    **LAND,
    "id": "r2",
    "command": None,
    "sector_moves": [{"sector_id": "S2", "to_vehicle": "uav3"}],
}


class Clock:
    t = 100.0

    def __call__(self) -> float:
        return self.t


def build(allow: bool) -> tuple[TestClient, Clock, Hub]:
    clock = Clock()
    hub = Hub(AuditLog(), clock)
    return TestClient(create_app(hub, allow_external_recommendations=allow)), clock, hub


def test_the_production_app_has_no_way_to_post_a_recommendation() -> None:
    client, _, hub = build(allow=False)
    client.post("/navtrust", json=NAVTRUST)
    assert client.post("/recommendations", json=LAND).status_code == 404
    assert hub.state()["open_recommendations"] == []


def test_a_recommendation_for_a_vehicle_nobody_has_heard_of_is_refused() -> None:
    client, _, hub = build(allow=True)
    response = client.post("/recommendations", json={**LAND, "vehicle_id": "uav9"})
    assert response.status_code == 422 and response.json()["detail"] == "unknown_vehicle"
    assert hub.state()["open_recommendations"] == []


def test_a_command_for_a_vehicle_without_a_link_is_refused_but_a_re_task_is_not() -> None:
    client, clock, hub = build(allow=True)
    client.post("/navtrust", json=NAVTRUST)
    clock.t += 30.0
    hub.sweep()
    refused = client.post("/recommendations", json=LAND)
    assert refused.status_code == 422 and refused.json()["detail"] == "no_link"
    assert client.post("/recommendations", json=RE_TASK).status_code == 201


def test_the_hub_sets_the_times_whatever_the_client_says() -> None:
    client, clock, _ = build(allow=True)
    client.post("/navtrust", json=NAVTRUST)
    body: dict[str, Any] = client.post("/recommendations", json=LAND).json()
    assert body["created_s"] == clock.t and body["expires_s"] == clock.t + 60.0


def test_every_recommendation_row_in_the_audit_log_says_who_proposed_it() -> None:
    client, _, hub = build(allow=True)
    client.post("/navtrust", json=NAVTRUST)
    client.post("/recommendations", json=LAND)
    [row] = hub.audit.events("recommendation")
    assert row.payload["source"] == "external"


def test_a_malformed_or_repeated_post_is_refused_when_the_route_is_on() -> None:
    client, _, _ = build(allow=True)
    client.post("/navtrust", json=NAVTRUST)
    assert (
        client.post(
            "/recommendations", json={**LAND, "command": None, "sector_moves": []}
        ).status_code
        == 422
    )
    assert client.post("/recommendations", json=LAND).status_code == 201
    assert client.post("/recommendations", json=LAND).status_code == 409
