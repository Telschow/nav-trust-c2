"""HTTP and WebSocket interface to the Hub (FastAPI).

    uvicorn: python -m c2.server --db logs/audit.sqlite --port 8000

There is no authentication: the operator name in a decision is whatever the client sends.
Bind to localhost only. Browsers are held to the same origin (see `cross_site_reason`), so a
web page the operator happens to open cannot approve a command or read the vehicles.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import ipaddress
import json
import logging
import math
import time
from collections.abc import AsyncIterator, Callable, Mapping
from dataclasses import asdict
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from fastapi import Body, FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from c2.audit import AuditLog
from c2.contingency import COM_DL_LOSS_T_S
from c2.fleet import FleetState
from c2.gate import CommandGate, Executor
from c2.hub import (
    AlreadyDecided,
    DuplicateRecommendation,
    ExpiredRecommendation,
    Hub,
    HubError,
    InvalidOperator,
    InvalidOutcome,
    InvalidPolicy,
    NoLink,
    OutsidePolicy,
    SupersededRecommendation,
    UnknownPolicy,
    UnknownRecommendation,
    UnknownVehicle,
)
from c2.messages import (
    Decision,
    Outcome,
    decision_to_dict,
    navtrust_from_dict,
    recommendation_from_dict,
    recommendation_to_dict,
)
from c2.progress import SectorProgress, geo_to_local
from c2.recommender import Recommender
from navtrust.calibration import GREEN_BOUND
from navtrust.types import TrustState

_STATUS = {
    UnknownRecommendation: 404,
    AlreadyDecided: 409,
    DuplicateRecommendation: 409,
    UnknownVehicle: 422,
    NoLink: 422,
    ExpiredRecommendation: 410,
    SupersededRecommendation: 410,
    InvalidPolicy: 422,
    UnknownPolicy: 422,
    OutsidePolicy: 422,
    InvalidOutcome: 422,
    InvalidOperator: 422,
}


def _without_non_finite(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {k: _without_non_finite(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_without_non_finite(v) for v in value]
    return value


def _json(message: dict[str, Any]) -> str:
    """WebSocket JSON that a browser can always parse: a NaN would be a syntax error there, and
    every later snapshot would be dropped (issue 161). The fields the console reads are refused
    at ingest; a free-form one (an onboard report's extras) goes out as null rather than closing
    every console's socket."""
    try:
        return json.dumps(message, allow_nan=False)
    except ValueError:
        return json.dumps(_without_non_finite(message), allow_nan=False)


def _authority(value: str) -> tuple[str, int | None] | None:
    """(host, port) of a Host header or an origin URL, lower-cased; None if unparsable."""
    try:
        parts = urlsplit(value if "://" in value else f"//{value}")
        host, port = parts.hostname, parts.port
    except ValueError:
        return None
    return (host.rstrip("."), port) if host else None


def _is_loopback(host: str) -> bool:
    if host == "localhost" or host.endswith(".localhost"):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _cannot_be_rebound(host: str) -> bool:
    """A web page can point a DNS name it controls at this machine (DNS rebinding), and public
    names always contain a dot. Loopback names, IP literals and single-label names cannot."""
    if _is_loopback(host) or "." not in host:
        return True
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return False
    return True


def cross_site_reason(origin: str | None, host: str | None) -> str | None:
    """Why a request must be refused, or None.

    There is no login, so the browser is the risk: a page on another site, or one that rebinds
    its own DNS name to this machine, could otherwise create and approve a recommendation (the
    gate would execute it) or read live positions over the WebSocket, which CORS does not cover.
    Non-browser clients (the replay feed, the scripted operator, curl) send no Origin.
    """
    target = _authority(host) if host else None
    if host is not None and (target is None or not _cannot_be_rebound(target[0])):
        return "unexpected Host header"
    if origin is None:
        return None
    source = _authority(origin) if origin != "null" else None
    if source is None:
        return "cross-origin request"
    if _is_loopback(source[0]) or source == target:
        return None
    return "cross-origin request"


def create_app(
    hub: Hub,
    *,
    fleet: FleetState | None = None,
    recommender: Recommender | None = None,
    gate: CommandGate | None = None,
    progress: SectorProgress | None = None,
    console_dir: str | Path | None = None,
    sweep_interval_s: float = 0.5,
    allow_external_recommendations: bool = False,
) -> FastAPI:
    """recommender needs fleet; gate (command execution) needs an approved decision; progress
    (which sectors are flown) needs fleet and the area origin. The hub is swept every
    sweep_interval_s so a vehicle that goes silent is marked NO_LINK even when nothing arrives.
    allow_external_recommendations adds `POST /recommendations` for tests and demos; the operator
    is otherwise only ever asked about what the recommender proposed (issue 157)."""

    @contextlib.asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        async def sweep_forever() -> None:
            while True:
                try:
                    hub.sweep()
                except Exception:  # a failing subscriber must not end link detection
                    logging.getLogger(__name__).exception("hub sweep failed; will retry")
                await asyncio.sleep(sweep_interval_s)

        task = asyncio.create_task(sweep_forever())
        try:
            yield
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    if recommender is not None:
        # every id carries the run's id, so a restarted backend cannot repeat one (issue 159)
        recommender.use_session(hub.session_id or hub.start_session())

    app = FastAPI(title="nav-trust-c2 backend", lifespan=lifespan)

    @app.middleware("http")
    async def same_origin_only(request: Request, call_next: Any) -> Response:
        reason = cross_site_reason(request.headers.get("origin"), request.headers.get("host"))
        if reason is not None:
            return JSONResponse({"detail": reason}, status_code=403)
        response: Response = await call_next(request)
        return response

    if recommender is not None:

        def tell_recommender(event: dict[str, Any]) -> None:
            if event["type"] != "decision":
                return
            data = event["data"]
            rec = hub.recommendation(data["recommendation_id"])
            if rec is not None:
                recommender.on_decision(
                    Decision(
                        data["recommendation_id"],
                        Outcome(data["outcome"]),
                        data["decided_s"],
                        data["operator"],
                    ),
                    rec.vehicle_id,
                )

        hub.subscribe(tell_recommender)

    def bad_request(err: Exception) -> HTTPException:
        return HTTPException(status_code=422, detail=f"{type(err).__name__}: {err}")

    @app.post("/navtrust", status_code=204)
    async def post_navtrust(body: dict[str, Any] = Body(...)) -> None:  # noqa: B008
        try:
            msg = navtrust_from_dict(body)
        except (KeyError, ValueError, TypeError) as err:
            raise bad_request(err) from err
        hub.ingest_navtrust(msg)
        if recommender is not None and fleet is not None:
            for rec in recommender.observe(msg, fleet):
                hub.add_recommendation(rec)

    @app.post("/policy", status_code=201)
    async def post_policy(body: dict[str, Any] = Body(...)) -> dict[str, Any]:  # noqa: B008
        """The operator approves, before the mission, what a vehicle may do alone (ADR 0004)."""
        try:
            policy = {"entries": body["entries"], "wait_s": body["wait_s"]}
            return hub.approve_policy(policy, body["operator"], max_wait_s=COM_DL_LOSS_T_S)
        except HubError as err:
            raise HTTPException(_STATUS[type(err)], err.code) from err
        except (KeyError, ValueError, TypeError) as err:
            raise bad_request(err) from err

    @app.post("/onboard-actions", status_code=204)
    async def post_onboard_action(body: dict[str, Any] = Body(...)) -> None:  # noqa: B008
        """A vehicle reports what it did on its own once the link is back."""
        try:
            hub.report_onboard_action(body)
        except HubError as err:
            raise HTTPException(_STATUS[type(err)], err.code) from err
        except (KeyError, ValueError, TypeError) as err:
            raise bad_request(err) from err

    @app.post("/positions", status_code=204)
    async def post_position(body: dict[str, Any] = Body(...)) -> None:  # noqa: B008
        try:
            hub.ingest_position(
                str(body["vehicle_id"]),
                float(body["lat_deg"]),
                float(body["lon_deg"]),
                float(body["alt_m"]),
            )
        except (KeyError, ValueError, TypeError) as err:
            raise bad_request(err) from err
        origin = hub.origin
        if fleet is not None and origin is not None:
            vehicle = str(body["vehicle_id"])
            local = geo_to_local(
                origin["lat_deg"], origin["lon_deg"], float(body["lat_deg"]), float(body["lon_deg"])
            )
            fleet.positions[vehicle] = local
            if progress is not None:
                latest = hub.latest_trust(vehicle)
                trusted = latest is not None and latest.state is TrustState.GREEN
                fleet.done_sector_ids |= progress.observe(local, float(body["alt_m"]), trusted)

    @app.post("/origin", status_code=204)
    async def post_origin(body: dict[str, Any] = Body(...)) -> None:  # noqa: B008
        try:
            hub.set_origin(float(body["lat_deg"]), float(body["lon_deg"]))
        except (KeyError, ValueError, TypeError) as err:
            raise bad_request(err) from err

    @app.post("/source", status_code=204)
    async def post_source(body: dict[str, Any] = Body(...)) -> None:  # noqa: B008
        try:
            hub.set_source(str(body["label"]))
        except (KeyError, ValueError, TypeError) as err:
            raise bad_request(err) from err

    if allow_external_recommendations:

        @app.post("/recommendations", status_code=201)
        async def post_recommendation(
            body: dict[str, Any] = Body(...),  # noqa: B008
        ) -> dict[str, Any]:
            try:
                rec = hub.add_external_recommendation(recommendation_from_dict(body))
            except HubError as err:
                raise HTTPException(_STATUS[type(err)], err.code) from err
            except (KeyError, ValueError, TypeError) as err:
                raise bad_request(err) from err
            return recommendation_to_dict(rec)

    @app.post("/decisions")
    async def post_decision(body: dict[str, Any] = Body(...)) -> dict[str, Any]:  # noqa: B008
        try:
            outcome = Outcome(body["outcome"])
            decision = hub.decide(
                body["recommendation_id"], outcome, body["operator"], body.get("note", "")
            )
        except HubError as err:
            raise HTTPException(_STATUS[type(err)], err.code) from err
        except (KeyError, ValueError, TypeError) as err:
            raise bad_request(err) from err
        response = decision_to_dict(decision)
        if gate is not None and decision.outcome is Outcome.APPROVED:
            result = await gate.execute(decision.recommendation_id)
            response["execution"] = {
                "executed": result.executed,
                "reason": result.reason,
                "actions": result.actions,
            }
        return response

    @app.get("/fleet")
    async def get_fleet() -> dict[str, Any]:
        if fleet is None:
            return {"origin": hub.origin, "assignment": {}, "done": []}
        return {
            "origin": hub.origin,
            "done": sorted(fleet.done_sector_ids),
            "assignment": {
                v: [
                    {"id": s.id, "west": s.west, "south": s.south, "east": s.east, "north": s.north}
                    for s in secs
                ]
                for v, secs in sorted(fleet.assignment.items())
            },
        }

    @app.get("/calibration")
    async def get_calibration() -> dict[str, Any]:
        return asdict(GREEN_BOUND)

    @app.get("/state")
    async def get_state() -> dict[str, Any]:
        return hub.state()

    @app.get("/audit")
    async def get_audit(
        kind: str | None = None, vehicle_id: str | None = None
    ) -> list[dict[str, Any]]:
        return [
            {
                "id": e.id,
                "t_s": e.t_s,
                "kind": e.kind,
                "vehicle_id": e.vehicle_id,
                "payload": e.payload,
            }
            for e in hub.audit.events(kind, vehicle_id)
        ]

    @app.websocket("/ws")
    async def ws(websocket: WebSocket) -> None:
        # the http middleware does not see WebSocket handshakes, and CORS does not apply to them
        if cross_site_reason(websocket.headers.get("origin"), websocket.headers.get("host")):
            await websocket.close(code=1008)  # policy violation
            return
        await websocket.accept()
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        unsubscribe = hub.subscribe(queue.put_nowait)  # endpoints run on the event loop
        try:
            state = hub.state()
            # server_s at the top level like every other message: the console derives its clock
            # offset from it, and without it the header showed T+NaN:NaN until the first event
            await websocket.send_text(
                _json({"type": "state", "server_s": state["server_s"], "data": state})
            )
            while True:
                await websocket.send_text(_json(await queue.get()))
        except WebSocketDisconnect:
            pass
        finally:
            unsubscribe()

    if console_dir is not None and Path(console_dir).is_dir():
        # mounted last so it never shadows the API routes above
        app.mount("/", StaticFiles(directory=console_dir, html=True), name="console")

    return app


ExecutorFactory = Callable[[argparse.Namespace, FleetState], Executor]
"""Builds the executor the gate sends approved commands to, for the fleet the backend manages. The
backend knows only `dryrun`; a launcher that has an executor of its own (sim/backend.py, MAVSDK)
registers it by name, so the backend never imports the simulator package (issue 177)."""


def parse_args(
    executors: Mapping[str, ExecutorFactory], argv: list[str] | None = None
) -> argparse.Namespace:
    """The backend's command line; `executors` are the extra executors a launcher registered."""
    p = argparse.ArgumentParser(description="nav-trust-c2 backend")
    p.add_argument("--db", default="logs/audit.sqlite")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument(
        "--link-timeout",
        type=float,
        default=2.0,
        help="seconds without a report before a vehicle is NO_LINK (proposal: 2)",
    )
    p.add_argument(
        "--ack-timeout",
        type=float,
        default=5.0,
        help="seconds a vehicle has to answer a command before it is audited as not acknowledged "
        "(proposal: 5)",
    )
    p.add_argument(
        "--retask-ack-timeout",
        type=float,
        default=None,
        help="seconds each vehicle has to answer a re-task (default: the same as --ack-timeout; "
        "set it from measured re-task times, see issue 77)",
    )
    p.add_argument("--console", default="console/dist", help="built console to serve at /")
    p.add_argument(
        "--source",
        help="label for where the data comes from, e.g. 'REPLAY DEMO' (default: live)",
    )
    p.add_argument("--vehicles", type=int, default=3)
    p.add_argument("--spacing", type=float, default=100.0, help="survey lane spacing, m")
    p.add_argument("--width", type=float, default=1000.0)
    p.add_argument("--height", type=float, default=1000.0)
    p.add_argument(
        "--origin",
        nargs=2,
        type=float,
        metavar=("LAT", "LON"),
        help="home of vehicle 1 (default: ask the simulator; use this when fly_fleet is running)",
    )
    p.add_argument(
        "--executor",
        choices=["dryrun", *executors],
        default="dryrun",
        help="dryrun only logs approved commands; mavsdk sends them to fly_fleet's vehicles "
        "(start the backend with `python -m sim.backend` to have it)",
    )
    return p.parse_args(argv)


def build_app_from_args(
    args: argparse.Namespace, executors: Mapping[str, ExecutorFactory]
) -> FastAPI:
    """The whole backend for a command line: audit log, hub, fleet, recommender, gate, console."""
    from c2.allocator import assign, split_area
    from c2.dryrun import DryRunExecutor
    from c2.recommender import Recommender

    start = time.monotonic()
    clock = lambda: time.monotonic() - start  # noqa: E731
    hub = Hub(AuditLog(args.db), clock, link_timeout_s=args.link_timeout)
    hub.start_session()
    if args.source:
        hub.set_source(args.source)
    ids = [f"uav{i}" for i in range(1, args.vehicles + 1)]
    sectors = split_area(args.width, args.height, args.vehicles)
    fleet = FleetState(
        assign(sectors, ids),
        positions={v: (0.0, 5.0 * i) for i, v in enumerate(ids)},  # spawn spacing of run_sitl.sh
    )
    factories: dict[str, ExecutorFactory] = {"dryrun": lambda _args, _fleet: DryRunExecutor()}
    factories.update(executors)
    executor = factories[args.executor](args, fleet)
    app = create_app(
        hub,
        fleet=fleet,
        recommender=Recommender(clock, link_ok=hub.is_reachable),
        gate=CommandGate(
            hub,
            fleet,
            executor,
            ack_timeout_s=args.ack_timeout,
            retask_ack_timeout_s=args.retask_ack_timeout,
        ),
        progress=SectorProgress(sectors, swath_half_width_m=args.spacing / 2),
        console_dir=args.console,
    )
    return app


def main(executors: Mapping[str, ExecutorFactory] | None = None) -> None:
    import uvicorn

    extra = executors or {}
    args = parse_args(extra)
    uvicorn.run(build_app_from_args(args, extra), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
