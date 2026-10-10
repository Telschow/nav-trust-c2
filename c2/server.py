"""HTTP and WebSocket interface to the Hub (FastAPI).

    uvicorn: python -m c2.server --db logs/audit.sqlite --port 8000

There is no authentication: the operator name in a decision is whatever the client sends.
Bind to localhost only.
"""

from __future__ import annotations

import argparse
import asyncio
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

from c2.audit import AuditLog
from c2.fleet import FleetState
from c2.gate import CommandGate
from c2.hub import (
    AlreadyDecided,
    DuplicateRecommendation,
    ExpiredRecommendation,
    Hub,
    HubError,
    InvalidOutcome,
    UnknownRecommendation,
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
    ExpiredRecommendation: 410,
    InvalidOutcome: 422,
}


def create_app(
    hub: Hub,
    *,
    fleet: FleetState | None = None,
    recommender: Recommender | None = None,
    gate: CommandGate | None = None,
    progress: SectorProgress | None = None,
    console_dir: str | Path | None = None,
) -> FastAPI:
    """recommender needs fleet; gate (command execution) needs an approved decision; progress
    (which sectors are flown) needs fleet and the area origin."""
    app = FastAPI(title="nav-trust-c2 backend")

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

    @app.post("/recommendations", status_code=201)
    async def post_recommendation(body: dict[str, Any] = Body(...)) -> dict[str, Any]:  # noqa: B008
        try:
            rec = recommendation_from_dict(body)
            hub.add_recommendation(rec)
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
            return {"origin": hub.origin, "assignment": {}}
        return {
            "origin": hub.origin,
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
        await websocket.accept()
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        unsubscribe = hub.subscribe(queue.put_nowait)  # endpoints run on the event loop
        try:
            state = hub.state()
            # server_s at the top level like every other message: the console derives its clock
            # offset from it, and without it the header showed T+NaN:NaN until the first event
            await websocket.send_json(
                {"type": "state", "server_s": state["server_s"], "data": state}
            )
            while True:
                await websocket.send_json(await queue.get())
        except WebSocketDisconnect:
            pass
        finally:
            unsubscribe()

    if console_dir is not None and Path(console_dir).is_dir():
        # mounted last so it never shadows the API routes above
        app.mount("/", StaticFiles(directory=console_dir, html=True), name="console")

    return app


def main() -> None:
    import uvicorn

    from c2.allocator import assign, split_area
    from c2.dryrun import DryRunExecutor
    from c2.recommender import Recommender

    p = argparse.ArgumentParser(description="nav-trust-c2 backend")
    p.add_argument("--db", default="logs/audit.sqlite")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--console", default="console/dist", help="built console to serve at /")
    p.add_argument(
        "--source",
        help="label for where the data comes from, e.g. 'REPLAY DEMO' (default: live)",
    )
    p.add_argument("--vehicles", type=int, default=3)
    p.add_argument("--width", type=float, default=1000.0)
    p.add_argument("--height", type=float, default=1000.0)
    p.add_argument(
        "--executor",
        choices=["dryrun", "mavsdk"],
        default="dryrun",
        help="mavsdk sends approved commands to fly_fleet's vehicles; dryrun only logs them",
    )
    args = p.parse_args()
    start = time.monotonic()
    clock = lambda: time.monotonic() - start  # noqa: E731
    hub = Hub(AuditLog(args.db), clock)
    if args.source:
        hub.set_source(args.source)
    ids = [f"uav{i}" for i in range(1, args.vehicles + 1)]
    sectors = split_area(args.width, args.height, args.vehicles)
    fleet = FleetState(
        assign(sectors, ids),
        positions={v: (0.0, 5.0 * i) for i, v in enumerate(ids)},  # spawn spacing of run_sitl.sh
    )
    if args.executor == "mavsdk":
        from sim.executor import MavsdkExecutor
        from sim.fly_fleet import home_of

        origin = asyncio.run(home_of(1))
        executor: Any = MavsdkExecutor(
            origin,
            spacing_m=100.0,
            altitude_m=30.0,
            speed_m_s=10.0,
            initial={v: list(secs) for v, secs in fleet.assignment.items()},
        )
    else:
        executor = DryRunExecutor()
    app = create_app(
        hub,
        fleet=fleet,
        recommender=Recommender(clock),
        gate=CommandGate(hub, fleet, executor),
        progress=SectorProgress(sectors),
        console_dir=args.console,
    )
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
