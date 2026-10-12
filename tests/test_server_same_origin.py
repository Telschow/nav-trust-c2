"""C2-01 against the browser: a web page must not reach the gate or read the vehicles.

Regression: with no login and no Origin or Host check, a page that rebinds its own DNS name to
the backend could create a LAND recommendation, approve it with an empty operator name and have
the gate execute it; any page could read live positions over the WebSocket.
"""

from typing import Any

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402
from starlette.websockets import WebSocketDisconnect  # noqa: E402

from c2.allocator import assign, split_area  # noqa: E402
from c2.audit import AuditLog  # noqa: E402
from c2.dryrun import DryRunExecutor  # noqa: E402
from c2.fleet import FleetState  # noqa: E402
from c2.gate import CommandGate  # noqa: E402
from c2.hub import Hub  # noqa: E402
from c2.server import create_app, cross_site_reason  # noqa: E402

REC: dict[str, Any] = {
    "id": "forged-1",
    "vehicle_id": "uav1",
    "created_s": 0.0,
    "expires_s": 999.0,
    "reason": "GNSS_LOSS",
    "command": "LAND",
    "sector_moves": [],
    "rationale": "forged by a web page",
}
APPROVE = {"recommendation_id": "forged-1", "outcome": "APPROVED", "operator": "web page"}


@pytest.fixture
def system() -> tuple[TestClient, DryRunExecutor, Hub]:
    executor = DryRunExecutor()
    hub = Hub(AuditLog(), lambda: 1.0)
    fleet = FleetState(assign(split_area(900, 900, 2), ["uav1", "uav2"]), positions={})
    app = create_app(hub, fleet=fleet, gate=CommandGate(hub, fleet, executor))
    return TestClient(app), executor, hub


def test_rebound_page_cannot_create_or_approve_a_command(
    system: tuple[TestClient, DryRunExecutor, Hub],
) -> None:
    client, executor, hub = system
    rebound = {"Host": "rebind.example.org:8000", "Origin": "http://rebind.example.org:8000"}
    assert client.post("/recommendations", json=REC, headers=rebound).status_code == 403
    assert client.post("/decisions", json=APPROVE, headers=rebound).status_code == 403
    assert client.get("/state", headers={"Host": "rebind.example.org:8000"}).status_code == 403
    assert executor.log == []
    assert hub.recommendation("forged-1") is None


def test_cross_origin_page_is_refused_even_for_a_real_recommendation(
    system: tuple[TestClient, DryRunExecutor, Hub],
) -> None:
    client, executor, _ = system
    assert client.post("/recommendations", json=REC).status_code == 201  # backend-side client
    other_site = {"Origin": "https://example.org"}
    assert client.post("/decisions", json=APPROVE, headers=other_site).status_code == 403
    assert client.post("/decisions", json=APPROVE, headers={"Origin": "null"}).status_code == 403
    assert executor.log == []
    # the console, served by this backend or by the Vite dev server, still decides
    console = {"Origin": "http://localhost:5173"}
    response = client.post("/decisions", json=APPROVE, headers=console)
    assert response.status_code == 200 and response.json()["execution"]["executed"] is True
    assert executor.log == ["land uav1"]


def test_websocket_refuses_other_sites(system: tuple[TestClient, DryRunExecutor, Hub]) -> None:
    client, _, _ = system
    with (
        pytest.raises(WebSocketDisconnect) as closed,
        client.websocket_connect("/ws", headers={"Origin": "https://example.org"}),
    ):
        pass
    assert closed.value.code == 1008
    with client.websocket_connect("/ws", headers={"Origin": "http://127.0.0.1:8000"}) as ws:
        assert ws.receive_json()["type"] == "state"


@pytest.mark.parametrize(
    ("origin", "host", "allowed"),
    [
        (None, "127.0.0.1:8000", True),  # replay feed, scripted operator, curl
        (None, "c2:8000", True),  # a single-label container name
        ("http://192.168.1.20:8000", "192.168.1.20:8000", True),  # console opened over the LAN
        ("http://[::1]:5173", "[::1]:8000", True),
        ("http://192.168.1.20:9000", "192.168.1.20:8000", False),  # another site on the LAN
        (None, "attacker.example.org", False),  # rebindable name
        ("http://localhost.example.org", "127.0.0.1:8000", False),
    ],
)
def test_cross_site_rules(origin: str | None, host: str, allowed: bool) -> None:
    assert (cross_site_reason(origin, host) is None) is allowed


def test_blank_operator_is_refused_and_nothing_executes(
    system: tuple[TestClient, DryRunExecutor, Hub],
) -> None:
    client, executor, hub = system
    assert client.post("/recommendations", json=REC).status_code == 201
    blank = {**APPROVE, "operator": "  "}
    response = client.post("/decisions", json=blank)
    assert response.status_code == 422 and response.json()["detail"] == "invalid_operator"
    assert executor.log == [] and hub.decision_for("forged-1") is None
