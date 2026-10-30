"""Run the onboard monitor next to a simulated vehicle (issue 76).

`run_monitor` feeds a trust engine from the vehicle's own MAVLink stream, independent of the C2
link, and asks the `OnboardMonitor` what to do twice a second. When it says LAND it lands the
vehicle itself, straight through MAVSDK: the operator approved this before the mission, so it
does not pass the gate (ADR 0004). What the vehicle did is told to the backend afterwards with
`report_actions`.

NOT SHOWN BY ANY TEST HERE: `run_monitor` needs a simulator. The decision logic is tested without
one (tests/test_onboard_monitor.py, eval/onboard_replay.py). In the simulator the C2 link signal
is whatever the caller passes as `link_up`; `sim.record_run` passes the state of its link-cut
relay, so a result says what the monitor does given that cut, not that PX4 or a real radio lost
the C2. The trust inputs are PX4's own figures through the trust engine (ADR 0005).
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import asdict
from typing import TYPE_CHECKING, Any

from c2.contingency import land_on_inconsistent_position, policy_sha256
from navtrust.engine import TrustEngine
from sim.onboard_monitor import OnboardAction, OnboardMonitor

if TYPE_CHECKING:
    import httpx
    from mavsdk_grpc import System

POLL_INTERVAL_S = 0.5


def experiment_approval(wait_s: float, now_s: float | None = None) -> dict[str, Any]:
    """The approval record for a recorded experiment that has no operator: audit id 0, the
    ADR 0004 contingency (LAND on a position inconsistency with no link). It is the experiment's
    own record and says so in the header; it is not an operator approval."""
    policy = land_on_inconsistent_position(wait_s)
    when = time.time() if now_s is None else now_s
    return {"audit_id": 0, "approved_s": when, "sha256": policy_sha256(policy), "policy": policy}


def action_report(action: OnboardAction) -> dict[str, Any]:
    """The body of POST /onboard-actions (docs/ICD.md)."""
    return asdict(action)


async def report_actions(
    client: httpx.AsyncClient, backend: str, actions: list[OnboardAction]
) -> None:
    for action in actions:
        response = await client.post(f"{backend}/onboard-actions", json=action_report(action))
        response.raise_for_status()


async def run_monitor(
    drone: System,
    monitor: OnboardMonitor,
    link_up: Callable[[], bool],
    write: Callable[..., None],
    vehicle_id: str = "uav1",
    clock: Callable[[], float] = time.monotonic,
    engine: TrustEngine | None = None,
    report: Callable[[list[OnboardAction]], Awaitable[None]] | None = None,
    interval_s: float = POLL_INTERVAL_S,
) -> None:
    """Feed the engine from the vehicle, poll the monitor, and LAND when it says so. Runs until
    cancelled. `write(event, **fields)` logs 'onboard_action'. `report`, if given, is called with
    the actions not yet told to the backend once the link is back (see `report_actions`)."""
    from sim.record_run import parse_estimator_status  # imported here: record_run imports this

    engine = engine or TrustEngine(vehicle_id)

    async def fixes() -> None:
        async for info in drone.telemetry.gps_info():
            engine.update_fix(clock(), info.fix_type.name)

    async def estimator() -> None:
        async for msg in drone.mavlink_direct.message("ESTIMATOR_STATUS"):
            f = parse_estimator_status(msg.fields_json)
            engine.update_estimator(
                clock(), f.get("pos_horiz_accuracy"), f.get("pos_horiz_ratio"), f.get("vel_ratio")
            )

    async def decide() -> None:
        while True:
            t = clock()
            up = link_up()
            if up:
                monitor.c2_heard(t)
                if report is not None:
                    unreported = monitor.take_unreported()
                    if unreported:
                        await report(unreported)
            monitor.trust(t, engine.report(t))
            action = monitor.poll(t)
            if action is not None:
                write("onboard_action", **asdict(action))
                await drone.action.land()
            await asyncio.sleep(interval_s)

    await asyncio.gather(fixes(), estimator(), decide())
