"""What the console is told about a decision matches what the backend did (issue 161):
a non-finite number is refused at the door, and a command's outcome reaches every console."""

import asyncio
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
from c2.messages import recommendation_from_dict  # noqa: E402
from c2.server import create_app  # noqa: E402

NAVTRUST = (
    '{"vehicle_id": "uav2", "stamp_s": 5.0, "state": "GREEN", "reason": null, '
    '"horizontal_bound_m": %s, "confidence": %s, "headroom": %s}'
)
JSON = {"Content-Type": "application/json"}


class Clock:
    t = 100.0

    def __call__(self) -> float:
        return self.t


def post_trust(
    client: TestClient, bound: str = "5.0", conf: str = "0.99", head: str = "0.5"
) -> int:
    body = NAVTRUST % (bound, conf, head)
    return int(client.post("/navtrust", content=body, headers=JSON).status_code)


@pytest.mark.parametrize("bad", ["NaN", "Infinity", "-Infinity"])
@pytest.mark.parametrize("field", ["bound", "conf", "head"])
def test_a_trust_report_with_a_number_that_is_not_finite_is_refused(field: str, bad: str) -> None:
    hub = Hub(AuditLog(), Clock())
    client = TestClient(create_app(hub))
    assert post_trust(client, **{field: bad}) == 422
    assert hub.state()["vehicles"] == {}


def test_an_unbounded_trust_report_is_still_sent_as_null() -> None:
    client = TestClient(create_app(Hub(AuditLog(), Clock())))
    assert post_trust(client, bound="null", conf="0.0", head="0.0") == 204


@pytest.mark.parametrize("alt", ["NaN", "Infinity"])
def test_a_position_with_an_altitude_that_is_not_finite_is_refused(alt: str) -> None:
    hub = Hub(AuditLog(), Clock())
    client = TestClient(create_app(hub))
    body = '{"vehicle_id": "uav1", "lat_deg": 47.0, "lon_deg": 8.0, "alt_m": ' + alt + "}"
    assert client.post("/positions", content=body, headers=JSON).status_code == 422
    assert hub.state()["positions"] == {}


class Silent(DryRunExecutor):
    """A vehicle that never answers a LAND."""

    async def land(self, vehicle_id: str) -> None:
        await asyncio.sleep(30)


REC: dict[str, Any] = {
    "id": "r1",
    "vehicle_id": "uav2",
    "created_s": 100.0,
    "expires_s": 160.0,
    "reason": "INCONSISTENT_INNOVATION",
    "command": "LAND",
    "sector_moves": [],
    "rationale": "x",
}


def system() -> tuple[TestClient, Hub]:
    hub = Hub(AuditLog(), Clock())
    fleet = FleetState(assign(split_area(900, 900, 2), ["uav1", "uav2"]), positions={})
    gate = CommandGate(hub, fleet, Silent(), ack_timeout_s=0.05)
    hub.add_recommendation(recommendation_from_dict(REC))
    return TestClient(create_app(hub, fleet=fleet, gate=gate)), hub


def test_a_command_that_was_not_acknowledged_reaches_a_second_console() -> None:
    client, _ = system()
    with client.websocket_connect("/ws") as second:
        second.receive_json()  # the snapshot
        approve = {"recommendation_id": "r1", "outcome": "APPROVED", "operator": "daniel"}
        assert client.post("/decisions", json=approve).status_code == 200
        kinds = []
        while True:
            event = second.receive_json()
            if event["type"] == "command":
                kinds.append(event["data"]["kind"])
                if event["data"]["kind"] == "command_not_acknowledged":
                    assert event["data"]["recommendation_id"] == "r1"
                    break
    assert kinds == ["command_sent", "command_not_acknowledged"]


def test_a_console_that_connects_later_is_told_how_the_command_ended() -> None:
    client, _ = system()
    approve = {"recommendation_id": "r1", "outcome": "APPROVED", "operator": "daniel"}
    client.post("/decisions", json=approve)
    outcome = client.get("/state").json()["command_outcomes"]["r1"]
    assert outcome["kind"] == "command_not_acknowledged"
    with client.websocket_connect("/ws") as ws:
        assert ws.receive_json()["data"]["command_outcomes"]["r1"]["kind"] == (
            "command_not_acknowledged"
        )


def test_a_number_that_is_not_finite_in_a_free_form_report_cannot_disconnect_a_console() -> None:
    from c2.contingency import land_on_inconsistent_position

    hub = Hub(AuditLog(), Clock())
    client = TestClient(create_app(hub))
    policy = {**land_on_inconsistent_position(5.0), "mission_id": "m1", "vehicles": ["uav1"]}
    approval = hub.approve_policy(policy, "daniel", max_wait_s=10.0)
    report = (
        '{"vehicle_id": "uav1", "t_s": NaN, "action": "LAND", "reason": "INCONSISTENT_INNOVATION", '
        f'"link_down_s": 6.0, "mission_id": "m1", "report_id": "r1", '
        f'"policy_audit_id": {approval["audit_id"]}, '
        f'"policy_sha256": "{approval["sha256"]}"}}'
    )
    with client.websocket_connect("/ws") as ws:
        ws.receive_json()
        assert client.post("/onboard-actions", content=report, headers=JSON).status_code == 204
        event = ws.receive_json()  # the socket is still open, and the NaN went out as null
        assert event["type"] == "onboard_action" and event["data"]["t_s"] is None
        client.post("/navtrust", content=NAVTRUST % ("5.0", "0.99", "0.5"), headers=JSON)
        assert ws.receive_json()["type"] == "navtrust"
