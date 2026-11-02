"""The glue around the onboard monitor that needs no simulator (issue 76)."""

import asyncio
import json
from typing import Any

import pytest

from c2.contingency import policy_sha256
from sim.onboard_monitor import OnboardAction
from sim.onboard_policy import load_policy
from sim.onboard_run import action_report, experiment_approval

ACTION = OnboardAction(
    "uav1", 59.0, "LAND", "INCONSISTENT_INNOVATION", 5.2, 7, "ab" * 32, "acknowledged"
)


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
        "policy_audit_id": 7, "policy_sha256": "ab" * 32, "outcome": "acknowledged",
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
    assert [e for e, _ in written] == ["onboard_action", "onboard_command_acknowledged"]
    assert "t_s" not in written[0][1]  # the recorder's own t_s must not be overwritten
    assert "vehicle_clock_s" in written[0][1]
    [(up, actions)] = reported
    assert up and len(actions) == 1 and actions[0].action == "LAND"


def test_a_report_the_backend_refuses_is_kept_and_sent_again_until_it_is_accepted() -> None:
    from sim.onboard_monitor import OnboardMonitor
    from sim.onboard_run import run_monitor

    approval = experiment_approval(wait_s=0.1)
    policy = load_policy(approval, now_s=approval["approved_s"], max_age_s=3600.0)
    drone, written, attempts = _FakeDrone(), [], []

    async def report(actions: list[OnboardAction]) -> None:
        attempts.append(len(actions))
        if len(attempts) < 3:  # the backend answers 500 twice, then 204
            raise RuntimeError("500")

    async def go() -> None:
        import time

        monitor = OnboardMonitor("uav1", policy, started_s=time.monotonic())
        task = asyncio.create_task(
            run_monitor(
                drone, monitor, lambda: monitor_link["up"], lambda e, **f: written.append((e, f)),
                engine=_FrozenEngine(), report=report, interval_s=0.02,  # type: ignore[arg-type]
                retry_s=0.05,
            )
        )  # fmt: skip
        await asyncio.sleep(0.1)  # the C2 is heard first, or the monitor has nothing to count from
        monitor_link["up"] = False
        await asyncio.sleep(0.4)
        monitor_link["up"] = True
        await asyncio.sleep(1.0)
        assert not task.done()  # a failed POST must not end the monitor
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    monitor_link = {"up": True}
    asyncio.run(go())
    assert attempts == [1, 1, 1]  # the same single action, three tries, then nothing left to send


def test_a_land_that_fails_is_logged_and_the_monitor_keeps_running() -> None:
    from sim.onboard_monitor import OnboardMonitor
    from sim.onboard_run import run_monitor

    class Failing(_FakeDrone):
        def __init__(self) -> None:
            super().__init__()

            async def land() -> None:
                raise RuntimeError("COMMAND_DENIED")

            self.action.land = land  # type: ignore[method-assign]

    approval = experiment_approval(wait_s=0.1)
    policy = load_policy(approval, now_s=approval["approved_s"], max_age_s=3600.0)
    written: list[tuple[str, dict[str, Any]]] = []
    link = {"up": True}

    async def go() -> None:
        import time

        monitor = OnboardMonitor("uav1", policy, started_s=time.monotonic())
        task = asyncio.create_task(
            run_monitor(
                Failing(), monitor, lambda: link["up"], lambda e, **f: written.append((e, f)),
                engine=_FrozenEngine(), interval_s=0.02,  # type: ignore[arg-type]
            )
        )  # fmt: skip
        await asyncio.sleep(0.1)
        link["up"] = False
        await asyncio.sleep(0.5)
        assert not task.done()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    asyncio.run(go())
    kinds = [e for e, _ in written]
    assert kinds[:2] == ["onboard_action", "onboard_command_failed"]
    assert "COMMAND_DENIED" in written[1][1]["error"]


def test_a_land_the_vehicle_accepts_is_logged_as_acknowledged() -> None:
    from sim.onboard_monitor import OnboardMonitor
    from sim.onboard_run import run_monitor

    approval = experiment_approval(wait_s=0.1)
    policy = load_policy(approval, now_s=approval["approved_s"], max_age_s=3600.0)
    written: list[tuple[str, dict[str, Any]]] = []
    link = {"up": True}

    async def go() -> None:
        import time

        monitor = OnboardMonitor("uav1", policy, started_s=time.monotonic())
        task = asyncio.create_task(
            run_monitor(
                _FakeDrone(), monitor, lambda: link["up"], lambda e, **f: written.append((e, f)),
                engine=_FrozenEngine(), interval_s=0.02,  # type: ignore[arg-type]
            )
        )  # fmt: skip
        await asyncio.sleep(0.1)
        link["up"] = False
        await asyncio.sleep(0.4)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    asyncio.run(go())
    assert [e for e, _ in written] == ["onboard_action", "onboard_command_acknowledged"]


def test_a_report_the_backend_refuses_for_good_is_dropped_and_does_not_block_the_monitor() -> None:
    from sim.onboard_monitor import OnboardMonitor
    from sim.onboard_run import run_monitor

    class Refused(Exception):
        """What httpx raises for a 422: it carries the response."""

        response = type("R", (), {"status_code": 422})()

    approval = experiment_approval(wait_s=0.1)
    policy = load_policy(approval, now_s=approval["approved_s"], max_age_s=3600.0)
    written: list[tuple[str, dict[str, Any]]] = []
    attempts: list[int] = []
    link = {"up": True}

    async def report(actions: list[OnboardAction]) -> None:
        attempts.append(len(actions))
        raise Refused("422")

    async def go() -> None:
        import time

        monitor = OnboardMonitor("uav1", policy, started_s=time.monotonic())
        task = asyncio.create_task(
            run_monitor(
                _FakeDrone(), monitor, lambda: link["up"], lambda e, **f: written.append((e, f)),
                engine=_FrozenEngine(), report=report, interval_s=0.02, retry_s=0.02,  # type: ignore[arg-type]
            )
        )  # fmt: skip
        await asyncio.sleep(0.1)
        link["up"] = False
        await asyncio.sleep(0.3)
        link["up"] = True
        await asyncio.sleep(0.5)
        assert not task.done()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    asyncio.run(go())
    assert attempts == [1]  # tried once; a 4xx will not change by asking again
    assert "onboard_report_rejected" in [e for e, _ in written]


class _Flaky(_FakeDrone):
    """A vehicle whose LAND is refused `refusals` times, then accepted."""

    def __init__(self, refusals: int) -> None:
        super().__init__()
        self.calls = 0
        outer = self

        async def land() -> None:
            outer.calls += 1
            if outer.calls <= refusals:
                raise RuntimeError("COMMAND_DENIED")

        self.action.land = land  # type: ignore[method-assign]


def _run_with(drone: _FakeDrone) -> tuple[list[tuple[str, dict[str, Any]]], list[OnboardAction]]:
    from sim.onboard_monitor import OnboardMonitor
    from sim.onboard_run import run_monitor

    approval = experiment_approval(wait_s=0.1)
    policy = load_policy(approval, now_s=approval["approved_s"], max_age_s=3600.0)
    written: list[tuple[str, dict[str, Any]]] = []
    reported: list[OnboardAction] = []
    link = {"up": True}

    async def report(actions: list[OnboardAction]) -> None:
        reported.extend(actions)

    async def go() -> None:
        import time

        monitor = OnboardMonitor("uav1", policy, started_s=time.monotonic(), land_retry_s=0.05)
        task = asyncio.create_task(
            run_monitor(
                drone, monitor, lambda: link["up"], lambda e, **f: written.append((e, f)),
                engine=_FrozenEngine(), report=report, interval_s=0.02,  # type: ignore[arg-type]
            )
        )  # fmt: skip
        await asyncio.sleep(0.1)
        link["up"] = False
        await asyncio.sleep(1.0)
        link["up"] = True
        await asyncio.sleep(0.3)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    asyncio.run(go())
    return written, reported


def test_a_land_refused_twice_is_called_three_times_and_reported_once_as_acknowledged() -> None:
    drone = _Flaky(refusals=2)
    written, reported = _run_with(drone)
    assert drone.calls == 3
    assert [e for e, _ in written].count("onboard_command_failed") == 2
    assert [a.outcome for a in reported] == ["acknowledged"]


def test_a_land_refused_every_time_is_called_three_times_and_reported_once_as_failed() -> None:
    drone = _Flaky(refusals=99)
    _, reported = _run_with(drone)
    assert drone.calls == 3
    assert [a.outcome for a in reported] == ["failed"]
