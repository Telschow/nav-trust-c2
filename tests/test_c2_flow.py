"""End to end without the simulator: recording -> trust engine -> HTTP -> hub -> WebSocket
and audit log. This is the issue 10 exit condition for the vehicle -> backend -> websocket path."""

from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from c2.audit import AuditLog  # noqa: E402
from c2.hub import Hub  # noqa: E402
from c2.messages import navtrust_to_dict  # noqa: E402
from c2.server import create_app  # noqa: E402
from navtrust.engine import TrustEngine  # noqa: E402
from navtrust.recording import load_recording  # noqa: E402
from navtrust.replay import replay_engine  # noqa: E402
from navtrust.types import TrustState  # noqa: E402

DATA = Path(__file__).parent / "replay" / "data"


def test_jamming_recording_reaches_the_websocket_and_the_audit_log() -> None:
    reports = replay_engine(load_recording(DATA / "jamming_zone-1.jsonl"), TrustEngine("uav1"))
    audit = AuditLog()
    client = TestClient(create_app(Hub(audit, lambda: 0.0)))
    with client.websocket_connect("/ws") as ws:
        assert ws.receive_json()["type"] == "state"
        for msg in reports:
            assert client.post("/navtrust", json=navtrust_to_dict(msg)).status_code == 204
        received = [ws.receive_json() for _ in reports]

    assert [m["data"]["stamp_s"] for m in received] == [r.stamp_s for r in reports]
    states = {m["data"]["state"] for m in received}
    assert {"AMBER", "RED", "GREEN"} <= states
    # only changes are audited, so far fewer rows than messages, ending in GREEN
    changes = audit.events("navtrust_change")
    assert 2 < len(changes) < len(reports) / 10
    assert changes[-1].payload["state"] == TrustState.GREEN.value
    assert client.get("/state").json()["vehicles"]["uav1"]["state"] == "GREEN"
