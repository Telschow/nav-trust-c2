"""HTTP and WebSocket interface to the Hub (FastAPI).

    uvicorn: python -m c2.server --db logs/audit.sqlite --port 8000

There is no authentication: the operator name in a decision is whatever the client sends.
Bind to localhost only.
"""

from __future__ import annotations

import argparse
import asyncio
import time
from typing import Any

from fastapi import Body, FastAPI, HTTPException, WebSocket, WebSocketDisconnect

from c2.audit import AuditLog
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
    Outcome,
    decision_to_dict,
    navtrust_from_dict,
    recommendation_from_dict,
    recommendation_to_dict,
)

_STATUS = {
    UnknownRecommendation: 404,
    AlreadyDecided: 409,
    DuplicateRecommendation: 409,
    ExpiredRecommendation: 410,
    InvalidOutcome: 422,
}


def create_app(hub: Hub) -> FastAPI:
    app = FastAPI(title="nav-trust-c2 backend")

    def bad_request(err: Exception) -> HTTPException:
        return HTTPException(status_code=422, detail=f"{type(err).__name__}: {err}")

    @app.post("/navtrust", status_code=204)
    async def post_navtrust(body: dict[str, Any] = Body(...)) -> None:  # noqa: B008
        try:
            msg = navtrust_from_dict(body)
        except (KeyError, ValueError, TypeError) as err:
            raise bad_request(err) from err
        hub.ingest_navtrust(msg)

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
        return decision_to_dict(decision)

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
            await websocket.send_json({"type": "state", "data": hub.state()})
            while True:
                await websocket.send_json(await queue.get())
        except WebSocketDisconnect:
            pass
        finally:
            unsubscribe()

    return app


def main() -> None:
    import uvicorn

    p = argparse.ArgumentParser(description="nav-trust-c2 backend")
    p.add_argument("--db", default="logs/audit.sqlite")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    args = p.parse_args()
    start = time.monotonic()
    hub = Hub(AuditLog(args.db), lambda: time.monotonic() - start)
    uvicorn.run(create_app(hub), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
