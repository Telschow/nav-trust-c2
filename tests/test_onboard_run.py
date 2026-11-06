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


def test_the_monitor_runs_without_the_simulator_packages(monkeypatch: pytest.MonkeyPatch) -> None:
    """An install without the `sim` extra has no mavsdk_grpc, and the monitor's logic and this
    test must not need it (issue 163): the estimator stream is read through a module that does not
    import it."""
    import sys

    from sim.onboard_monitor import OnboardMonitor
    from sim.onboard_run import run_monitor

    monkeypatch.setitem(sys.modules, "mavsdk_grpc", None)  # importing it now raises ImportError
    monkeypatch.delitem(sys.modules, "sim.record_run", raising=False)
    heard: list[tuple[float | None, ...]] = []

    class Engine(_FrozenEngine):
        def update_estimator(self, t: float, *vals: Any) -> None:
            heard.append(vals)

    class Message:
        fields_json = json.dumps(
            {"pos_horiz_accuracy": 0.9, "pos_horiz_ratio": 2.0, "vel_ratio": 1.0}
        )

    class Once(_Silent):
        def __aiter__(self) -> "Once":
            return self

        async def __anext__(self) -> Any:
            if heard:
                await asyncio.sleep(3600)
            return Message()

    drone = _FakeDrone()
    drone.mavlink_direct.message = lambda name: Once()  # type: ignore[method-assign]
    approval = experiment_approval(wait_s=0.1)
    policy = load_policy(approval, now_s=approval["approved_s"], max_age_s=3600.0)

    async def go() -> None:
        import time

        monitor = OnboardMonitor("uav1", policy, started_s=time.monotonic())
        task = asyncio.create_task(
            run_monitor(
                drone, monitor, lambda: True, lambda e, **f: None,
                engine=Engine(), interval_s=0.02,  # type: ignore[arg-type]
            )
        )  # fmt: skip
        await asyncio.sleep(0.2)
        failed = task.done()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        assert not failed

    asyncio.run(go())
    assert heard == [(0.9, 2.0, 1.0)]


BOUND_POLICY = {
    "entries": [{"reason": "INCONSISTENT_INNOVATION", "link": "NO_LINK", "action": "LAND"}],
    "wait_s": 5.0,
    "mission_id": "m1",
    "vehicles": ["uav1"],
}


def _delivery(**over: Any) -> dict[str, Any]:
    return {
        "audit_id": 7, "approved_s": 1000.0, "sha256": policy_sha256(BOUND_POLICY),
        "max_age_s": 14400.0, "policy": BOUND_POLICY, "server_s": 1060.0, **over,
    }  # fmt: skip


def _fetch(handler: Any, mission_id: str = "m1", vehicle_id: str = "uav1") -> Any:
    httpx = pytest.importorskip("httpx")
    from sim.onboard_run import fetch_policy

    async def go() -> Any:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await fetch_policy(client, "http://backend", mission_id, vehicle_id)

    return asyncio.run(go())


def test_the_vehicle_pulls_its_policy_and_ages_it_on_the_backends_clock() -> None:
    httpx = pytest.importorskip("httpx")
    paths: list[str] = []

    def handler(request: Any) -> Any:
        paths.append(request.url.path)
        return httpx.Response(200, json=_delivery())

    policy = _fetch(handler)
    assert paths == ["/policy/m1/uav1"]
    assert policy.audit_id == 7 and policy.mission_id == "m1"
    assert policy.age_at_load_s == 60.0 and policy.max_age_s == 14400.0


def test_a_refused_pull_leaves_the_vehicle_without_a_policy() -> None:
    httpx = pytest.importorskip("httpx")
    from sim.onboard_policy import PolicyRejected

    with pytest.raises(PolicyRejected, match="outside_binding"):
        _fetch(lambda r: httpx.Response(422, json={"detail": "outside_binding"}))


def test_an_unreachable_backend_leaves_the_vehicle_without_a_policy() -> None:
    httpx = pytest.importorskip("httpx")
    from sim.onboard_policy import PolicyRejected

    def handler(request: Any) -> Any:
        raise httpx.ConnectError("down")

    with pytest.raises(PolicyRejected, match="could not fetch"):
        _fetch(handler)


def test_a_delivered_policy_for_another_vehicle_is_refused() -> None:
    httpx = pytest.importorskip("httpx")
    from sim.onboard_policy import PolicyRejected

    with pytest.raises(PolicyRejected, match="vehicle"):
        _fetch(lambda r: httpx.Response(200, json=_delivery()), vehicle_id="uav9")


def test_a_bound_policys_action_is_reported_with_its_mission() -> None:
    from navtrust.types import NavTrust, ReasonCode, TrustState
    from sim.onboard_monitor import OnboardMonitor

    policy = load_policy(_delivery(), 1060.0, 14400.0, "m1", "uav1")
    monitor = OnboardMonitor("uav1", policy, started_s=0.0)
    monitor.c2_heard(0.0)
    report = NavTrust("uav1", 10.0, TrustState.RED, ReasonCode.INCONSISTENT_INNOVATION, 0.0, 1.0)
    monitor.trust(10.0, report)
    action = monitor.poll(10.0)
    assert action is not None and action.mission_id == "m1"
    assert action_report(action)["mission_id"] == "m1"


def _run_bound(handler: Any, link: dict[str, bool], seconds: float) -> tuple[Any, list[Any]]:
    httpx = pytest.importorskip("httpx")
    from sim.onboard_run import run_bound_monitor

    drone, written = _FakeDrone(), []

    async def go() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            task = asyncio.create_task(
                run_bound_monitor(
                    client, "http://backend", drone, "m1", "uav1", lambda: link["up"],
                    lambda e, **f: written.append((e, f)),
                    engine=_FrozenEngine(), interval_s=0.02,
                )
            )  # fmt: skip
            await asyncio.sleep(seconds)
            link["up"] = True
            await asyncio.sleep(0.2)
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    asyncio.run(go())
    return drone, written


def test_a_refused_pull_starts_no_monitor_and_is_recorded() -> None:
    httpx = pytest.importorskip("httpx")
    drone, written = _run_bound(
        lambda r: httpx.Response(422, json={"detail": "outside_binding"}), {"up": False}, 0.3
    )
    assert drone.landed == 0
    assert [e for e, _ in written] == ["onboard_policy_refused"]


def test_a_delivered_policy_runs_the_monitor_and_the_report_carries_the_mission() -> None:
    httpx = pytest.importorskip("httpx")
    reports: list[dict[str, Any]] = []
    policy = {**BOUND_POLICY, "wait_s": 0.1}

    def handler(request: Any) -> Any:
        if request.method == "GET":
            return httpx.Response(200, json=_delivery(policy=policy, sha256=policy_sha256(policy)))
        reports.append(json.loads(request.content))
        return httpx.Response(204)

    link = {"up": True}

    async def cut_link() -> None:
        await asyncio.sleep(0.1)
        link["up"] = False

    httpx_mod = httpx

    async def go() -> Any:
        from sim.onboard_run import run_bound_monitor

        drone, written = _FakeDrone(), []
        async with httpx_mod.AsyncClient(transport=httpx_mod.MockTransport(handler)) as client:
            task = asyncio.create_task(
                run_bound_monitor(
                    client, "http://backend", drone, "m1", "uav1", lambda: link["up"],
                    lambda e, **f: written.append((e, f)),
                    engine=_FrozenEngine(), interval_s=0.02,
                )
            )  # fmt: skip
            cutter = asyncio.create_task(cut_link())
            await asyncio.sleep(0.6)
            link["up"] = True
            await asyncio.sleep(0.2)
            task.cancel()
            await asyncio.gather(task, cutter, return_exceptions=True)
        return drone, written

    drone, written = asyncio.run(go())
    assert drone.landed == 1
    assert written[0][0] == "onboard_policy_loaded"
    assert written[0][1]["policy_audit_id"] == 7 and written[0][1]["mission_id"] == "m1"
    assert [r["mission_id"] for r in reports] == ["m1"]
