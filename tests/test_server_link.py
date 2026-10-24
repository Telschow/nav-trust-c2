"""LL-01: the server sweeps the hub on a timer, so a fleet that went completely silent is noticed."""

import time

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from c2.audit import AuditLog  # noqa: E402
from c2.hub import Hub  # noqa: E402
from c2.messages import Decision  # noqa: E402
from c2.server import create_app  # noqa: E402
from navtrust.types import NavTrust, TrustState  # noqa: E402


class Clock:
    def __init__(self) -> None:
        self.t = 100.0

    def __call__(self) -> float:
        return self.t


def test_a_silent_vehicle_is_marked_no_link_without_any_request_arriving() -> None:
    clock, audit = Clock(), AuditLog()
    hub = Hub(audit, clock)
    hub.ingest_navtrust(NavTrust("uav1", 1.0, TrustState.GREEN, None, 0.15, 1.0))
    with TestClient(create_app(hub, sweep_interval_s=0.01)):
        clock.t = 110.0  # nothing is sent, no endpoint is called
        deadline = time.monotonic() + 5.0
        while not audit.events("link_change") and time.monotonic() < deadline:
            time.sleep(0.01)
    assert [e.payload["state"] for e in audit.events("link_change")] == ["NO_LINK"]


class FlakyHub(Hub):
    """A hub whose first sweep fails, as a failing subscriber callback would."""

    failures = 0

    def sweep(self) -> list[Decision]:
        if self.failures:
            self.failures -= 1
            raise RuntimeError("a subscriber failed")
        return super().sweep()


def test_one_failed_sweep_does_not_stop_the_link_timer() -> None:
    clock, audit = Clock(), AuditLog()
    hub = FlakyHub(audit, clock)
    hub.ingest_navtrust(NavTrust("uav1", 1.0, TrustState.GREEN, None, 0.15, 1.0))
    hub.failures = 1  # armed after setup: the timer's first sweep fails, the next must still run
    with TestClient(create_app(hub, sweep_interval_s=0.01)):
        clock.t = 110.0
        deadline = time.monotonic() + 5.0
        while not audit.events("link_change") and time.monotonic() < deadline:
            time.sleep(0.01)
    assert [e.payload["state"] for e in audit.events("link_change")] == ["NO_LINK"]
