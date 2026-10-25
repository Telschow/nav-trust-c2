"""ICD messages beyond NavTrust (see docs/ICD.md, a proposal). Pure Python."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from navtrust.types import NavTrust, ReasonCode, TrustState


class Command(StrEnum):
    HOLD = "HOLD"
    RTL = "RTL"
    LAND = "LAND"


class Outcome(StrEnum):
    APPROVED = "APPROVED"
    DENIED = "DENIED"
    EXPIRED = "EXPIRED"
    SUPERSEDED = (
        "SUPERSEDED"  # closed by the backend: the situation changed while the link was down
    )


@dataclass(frozen=True)
class SectorMove:
    sector_id: str
    to_vehicle: str


@dataclass(frozen=True)
class Recommendation:
    id: str
    vehicle_id: str
    created_s: float
    expires_s: float
    reason: ReasonCode
    command: Command | None
    sector_moves: tuple[SectorMove, ...]
    rationale: str

    def __post_init__(self) -> None:
        if self.expires_s <= self.created_s:
            raise ValueError("expires_s must be after created_s")
        if self.command is None and not self.sector_moves:
            raise ValueError("a recommendation needs a command or sector moves")


@dataclass(frozen=True)
class Decision:
    recommendation_id: str
    outcome: Outcome
    decided_s: float
    operator: str
    note: str = field(default="")
    # EXPIRED only: whether the vehicle could be heard at that moment (None: not an expiry)
    vehicle_heard: bool | None = None


def navtrust_to_dict(msg: NavTrust) -> dict[str, Any]:
    """JSON-safe form: an unknown (infinite) bound becomes null."""
    return {
        "vehicle_id": msg.vehicle_id,
        "stamp_s": msg.stamp_s,
        "state": msg.state.value,
        "reason": msg.reason.value if msg.reason else None,
        "horizontal_bound_m": None
        if math.isinf(msg.horizontal_bound_m)
        else msg.horizontal_bound_m,
        "confidence": msg.confidence,
        "headroom": msg.headroom,
    }


def navtrust_from_dict(d: dict[str, Any]) -> NavTrust:
    bound = d["horizontal_bound_m"]
    return NavTrust(
        vehicle_id=d["vehicle_id"],
        stamp_s=float(d["stamp_s"]),
        state=TrustState(d["state"]),
        reason=ReasonCode(d["reason"]) if d["reason"] else None,
        horizontal_bound_m=math.inf if bound is None else float(bound),
        confidence=float(d["confidence"]),
        headroom=float(d.get("headroom", 0.0)),
    )


def recommendation_to_dict(r: Recommendation) -> dict[str, Any]:
    return {
        "id": r.id,
        "vehicle_id": r.vehicle_id,
        "created_s": r.created_s,
        "expires_s": r.expires_s,
        "reason": r.reason.value,
        "command": r.command.value if r.command else None,
        "sector_moves": [
            {"sector_id": m.sector_id, "to_vehicle": m.to_vehicle} for m in r.sector_moves
        ],
        "rationale": r.rationale,
    }


def recommendation_from_dict(d: dict[str, Any]) -> Recommendation:
    return Recommendation(
        id=d["id"],
        vehicle_id=d["vehicle_id"],
        created_s=float(d["created_s"]),
        expires_s=float(d["expires_s"]),
        reason=ReasonCode(d["reason"]),
        command=Command(d["command"]) if d.get("command") else None,
        sector_moves=tuple(SectorMove(m["sector_id"], m["to_vehicle"]) for m in d["sector_moves"]),
        rationale=d["rationale"],
    )


def decision_to_dict(d: Decision) -> dict[str, Any]:
    out: dict[str, Any] = {
        "recommendation_id": d.recommendation_id,
        "outcome": d.outcome.value,
        "decided_s": d.decided_s,
        "operator": d.operator,
        "note": d.note,
    }
    if d.vehicle_heard is not None:
        out["vehicle_heard"] = d.vehicle_heard
    return out
