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
REPORT_RETRY_S = 1.0  # proposal: first pause before a report that failed is sent again
REPORT_RETRY_MAX_S = 30.0


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
    retry_s: float = REPORT_RETRY_S,
) -> None:
    """Feed the engine from the vehicle, poll the monitor, and LAND when it says so. Runs until
    cancelled. `write(event, **fields)` logs 'onboard_action', then 'onboard_command_acknowledged'
    or 'onboard_command_failed' for the LAND, and 'onboard_error' for anything that went wrong
    without stopping the monitor. `report`, if given, is called with the actions not yet told to
    the backend once the link is back; if it raises they are kept and tried again after a pause
    that doubles up to `REPORT_RETRY_MAX_S`, unless the backend answered 4xx, which is logged as
    'onboard_report_rejected' and not repeated (see `report_actions`)."""
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

    async def supervised(name: str, stream: Callable[[], Awaitable[None]]) -> None:
        """A telemetry stream that ends or fails is logged and started again; the monitor must
        not stop because one of its inputs did."""
        while True:
            try:
                await stream()
            except Exception as err:
                write("onboard_error", task=name, error=repr(err))
            await asyncio.sleep(interval_s)

    retry = {"at": 0.0, "pause": retry_s}

    async def tell_backend(t: float) -> None:
        if report is None or t < retry["at"]:
            return
        unreported = monitor.take_unreported()
        if not unreported:
            return
        try:
            await report(unreported)
        except Exception as err:
            status = getattr(getattr(err, "response", None), "status_code", None)
            if isinstance(status, int) and 400 <= status < 500:
                # the backend read it and said no (a 422 from the policy check): asking again
                # changes nothing and would hold up everything queued behind it
                write("onboard_report_rejected", status=status, actions=len(unreported))
                return
            monitor.requeue(unreported)
            write("onboard_error", task="report", error=repr(err))
            retry["at"] = t + retry["pause"]
            retry["pause"] = min(retry["pause"] * 2, REPORT_RETRY_MAX_S)
        else:
            retry["pause"] = retry_s

    async def decide() -> None:
        while True:
            try:
                t = clock()
                if link_up():
                    monitor.c2_heard(t)
                    await tell_backend(t)
                monitor.trust(t, engine.report(t))
                action = monitor.poll(t)
                if action is not None:
                    # the action's t_s is the vehicle's clock; the recorder stamps its own t_s, and
                    # a field of that name would overwrite it (recordings need t_s non-decreasing)
                    fields = asdict(action)
                    write("onboard_action", vehicle_clock_s=fields.pop("t_s"), **fields)
                    try:
                        await drone.action.land()
                    except Exception as err:
                        write("onboard_command_failed", error=repr(err))
                    else:
                        write("onboard_command_acknowledged")
            except Exception as err:
                write("onboard_error", task="decide", error=repr(err))
            await asyncio.sleep(interval_s)

    await asyncio.gather(supervised("fixes", fixes), supervised("estimator", estimator), decide())
