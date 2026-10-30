"""The glue around the onboard monitor that needs no simulator (issue 76)."""

import asyncio
import json
from typing import Any

import pytest

from c2.contingency import policy_sha256
from sim.onboard_monitor import OnboardAction
from sim.onboard_policy import load_policy
from sim.onboard_run import action_report, experiment_approval

ACTION = OnboardAction("uav1", 59.0, "LAND", "INCONSISTENT_INNOVATION", 5.2, 7, "ab" * 32)


def test_an_experiment_approval_loads_and_says_what_it_is() -> None:
    approval = experiment_approval(wait_s=5.0)
    assert approval["audit_id"] == 0  # not an operator approval: a recorded experiment's own
    assert approval["sha256"] == policy_sha256(approval["policy"])
    policy = load_policy(approval, now_s=approval["approved_s"], max_age_s=3600.0)
    assert policy.wait_s == 5.0 and policy.matches("INCONSISTENT_INNOVATION", "NO_LINK")


def test_a_wait_the_vehicle_would_refuse_cannot_make_an_experiment_policy() -> None:
    approval = experiment_approval(wait_s=12.0)
    with pytest.raises(Exception, match="wait"):
        load_policy(approval, now_s=approval["approved_s"], max_age_s=3600.0)


def test_the_report_to_the_backend_carries_the_action_and_its_policy_reference() -> None:
    assert action_report(ACTION) == {
        "vehicle_id": "uav1", "t_s": 59.0, "action": "LAND",
        "reason": "INCONSISTENT_INNOVATION", "link_down_s": 5.2,
        "policy_audit_id": 7, "policy_sha256": "ab" * 32,
    }  # fmt: skip


def test_unreported_actions_are_posted_once_to_the_backend() -> None:
    httpx = pytest.importorskip("httpx")
    from sim.onboard_run import report_actions

    seen: list[dict[str, Any]] = []

    def handler(request: Any) -> Any:
        seen.append(json.loads(request.content))
        return httpx.Response(204)

    async def go() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await report_actions(client, "http://backend", [ACTION])

    asyncio.run(go())
    assert seen == [action_report(ACTION)]


class _Silent:
    """A telemetry stream that never produces anything."""

    def __aiter__(self) -> "_Silent":
        return self

    async def __anext__(self) -> Any:
        await asyncio.sleep(3600)


class _FakeDrone:
    def __init__(self) -> None:
        self.landed = 0
        outer = self

        class Telemetry:
            def gps_info(self) -> _Silent:
                return _Silent()

        class Direct:
            def message(self, name: str) -> _Silent:
                return _Silent()

        class Action:
            async def land(self) -> None:
                outer.landed += 1

        self.telemetry, self.mavlink_direct, self.action = Telemetry(), Direct(), Action()


class _FrozenEngine:
    def update_fix(self, *a: Any) -> None: ...
    def update_estimator(self, *a: Any) -> None: ...

    def report(self, t_s: float) -> Any:
        from navtrust.types import NavTrust, ReasonCode, TrustState

        return NavTrust(
            "uav1", t_s, TrustState.RED, ReasonCode.INCONSISTENT_INNOVATION, float("inf"), 0.0
        )


def test_the_monitor_lands_the_vehicle_itself_and_reports_only_once_the_link_is_back() -> None:
    from sim.onboard_monitor import OnboardMonitor
    from sim.onboard_run import run_monitor

    approval = experiment_approval(wait_s=0.1)
    policy = load_policy(approval, now_s=approval["approved_s"], max_age_s=3600.0)
    drone, link, written, reported = _FakeDrone(), {"up": True}, [], []

    async def report(actions: list[OnboardAction]) -> None:
        reported.append((link["up"], actions))

    async def go() -> None:
        import time

        monitor = OnboardMonitor("uav1", policy, started_s=time.monotonic())
        task = asyncio.create_task(
            run_monitor(
                drone, monitor, lambda: link["up"], lambda e, **f: written.append((e, f)),
                engine=_FrozenEngine(), report=report, interval_s=0.02,  # type: ignore[arg-type]
            )
        )  # fmt: skip
        await asyncio.sleep(0.2)  # the link is up: nothing happens
        assert drone.landed == 0 and reported == []
        link["up"] = False
        await asyncio.sleep(0.5)  # down longer than the wait: it lands once, reports nothing yet
        assert drone.landed == 1 and reported == []
        link["up"] = True
        await asyncio.sleep(0.2)  # back: it tells the backend what it did, once
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    asyncio.run(go())
    assert drone.landed == 1
    assert [e for e, _ in written] == ["onboard_action"]
    [(up, actions)] = reported
    assert up and len(actions) == 1 and actions[0].action == "LAND"
