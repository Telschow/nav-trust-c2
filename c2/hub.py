"""Backend logic: latest trust per vehicle, recommendations, operator decisions, audit.

No web framework here, so it is tested directly. Every state change is written to the audit
log; a rejected decision attempt is logged too.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from c2.audit import AuditLog
from c2.messages import (
    Decision,
    Outcome,
    Recommendation,
    decision_to_dict,
    navtrust_to_dict,
    recommendation_to_dict,
)
from navtrust.types import NavTrust

Event = dict[str, Any]


class HubError(Exception):
    """Base class; `code` is a stable machine-readable reason."""

    code = "error"


class UnknownRecommendation(HubError):
    code = "unknown_recommendation"


class AlreadyDecided(HubError):
    code = "already_decided"


class ExpiredRecommendation(HubError):
    code = "expired"


class InvalidOutcome(HubError):
    code = "invalid_outcome"


class DuplicateRecommendation(HubError):
    code = "duplicate_recommendation"


class Hub:
    def __init__(self, audit: AuditLog, clock: Callable[[], float]) -> None:
        self._audit = audit
        self.audit = audit
        self._clock = clock
        self._trust: dict[str, NavTrust] = {}
        self._recs: dict[str, Recommendation] = {}
        self._decisions: dict[str, Decision] = {}
        self._subscribers: list[Callable[[Event], None]] = []
        self._positions: dict[str, dict[str, float]] = {}
        self._origin: dict[str, float] | None = None
        self._source = "live"

    # --- subscriptions -------------------------------------------------------------------

    def subscribe(self, callback: Callable[[Event], None]) -> Callable[[], None]:
        self._subscribers.append(callback)
        return lambda: self._subscribers.remove(callback)

    def _publish(self, event: Event) -> None:
        event = {**event, "server_s": self._clock()}  # lets a client run expiry countdowns
        for callback in list(self._subscribers):
            callback(event)

    # --- inputs --------------------------------------------------------------------------

    def ingest_navtrust(self, msg: NavTrust) -> None:
        # Trust arrives continuously in any real session, so this is what closes recommendations
        # that expired unanswered (and lets the recommender issue them again). Without it nothing
        # would ever mark them expired unless a client happened to ask for the state.
        self.sweep()
        previous = self._trust.get(msg.vehicle_id)
        self._trust[msg.vehicle_id] = msg
        if previous is None or (previous.state, previous.reason) != (msg.state, msg.reason):
            self._audit.append(
                self._clock(),
                "navtrust_change",
                msg.vehicle_id,
                {
                    **navtrust_to_dict(msg),
                    "previous_state": previous.state.value if previous else None,
                },
            )
        self._publish({"type": "navtrust", "data": navtrust_to_dict(msg)})

    def ingest_position(
        self, vehicle_id: str, lat_deg: float, lon_deg: float, alt_m: float
    ) -> None:
        """Latest position for the map. High rate, so it is published but not audited."""
        if not (-90 <= lat_deg <= 90 and -180 <= lon_deg <= 180):
            raise ValueError("latitude or longitude out of range")
        pos = {"lat_deg": lat_deg, "lon_deg": lon_deg, "alt_m": alt_m, "stamp_s": self._clock()}
        self._positions[vehicle_id] = pos
        self._publish({"type": "position", "data": {"vehicle_id": vehicle_id, **pos}})

    def set_origin(self, lat_deg: float, lon_deg: float) -> None:
        """Geographic position of the area origin (south-west corner of the sector grid)."""
        if not (-90 <= lat_deg <= 90 and -180 <= lon_deg <= 180):
            raise ValueError("latitude or longitude out of range")
        self._origin = {"lat_deg": lat_deg, "lon_deg": lon_deg}
        self._publish({"type": "origin", "data": self._origin})

    def set_source(self, label: str) -> None:
        """Say where the data comes from ('live', or e.g. 'REPLAY DEMO'), so the console can
        never present replayed data as a live flight."""
        if not label.strip():
            raise ValueError("label must not be empty")
        self._source = label.strip()
        self._publish({"type": "source", "data": {"label": self._source}})

    @property
    def origin(self) -> dict[str, float] | None:
        return self._origin

    def add_recommendation(self, rec: Recommendation) -> None:
        if rec.id in self._recs:
            raise DuplicateRecommendation(rec.id)
        self._recs[rec.id] = rec
        self._audit.append(
            self._clock(), "recommendation", rec.vehicle_id, recommendation_to_dict(rec)
        )
        self._publish({"type": "recommendation", "data": recommendation_to_dict(rec)})

    def decide(
        self, recommendation_id: str, outcome: Outcome, operator: str, note: str = ""
    ) -> Decision:
        now = self._clock()
        attempt = {
            "recommendation_id": recommendation_id,
            "outcome": outcome.value,
            "operator": operator,
            "note": note,
        }
        self.sweep()
        try:
            if outcome not in (Outcome.APPROVED, Outcome.DENIED):
                raise InvalidOutcome(outcome.value)
            rec = self._recs.get(recommendation_id)
            if rec is None:
                raise UnknownRecommendation(recommendation_id)
            existing = self._decisions.get(recommendation_id)
            if existing is not None:
                if existing.outcome is Outcome.EXPIRED:
                    raise ExpiredRecommendation(recommendation_id)
                raise AlreadyDecided(recommendation_id)
        except HubError as err:
            self._audit.append(
                now, "rejected_decision", None, {**attempt, "rejected_because": err.code}
            )
            raise
        decision = Decision(recommendation_id, outcome, now, operator, note)
        self._record(decision, rec.vehicle_id)
        return decision

    def sweep(self) -> list[Decision]:
        """Mark recommendations past their expiry as EXPIRED (once). Returns the new ones."""
        now = self._clock()
        expired = []
        for rec in self._recs.values():
            if rec.id not in self._decisions and now > rec.expires_s:
                decision = Decision(rec.id, Outcome.EXPIRED, now, "system")
                self._record(decision, rec.vehicle_id)
                expired.append(decision)
        return expired

    def _record(self, decision: Decision, vehicle_id: str) -> None:
        self._decisions[decision.recommendation_id] = decision
        self._audit.append(self._clock(), "decision", vehicle_id, decision_to_dict(decision))
        self._publish({"type": "decision", "data": decision_to_dict(decision)})

    # --- queries -------------------------------------------------------------------------

    def state(self) -> dict[str, Any]:
        self.sweep()
        return {
            "server_s": self._clock(),
            "source": self._source,
            "origin": self._origin,
            "positions": {v: {"vehicle_id": v, **p} for v, p in sorted(self._positions.items())},
            "vehicles": {v: navtrust_to_dict(m) for v, m in sorted(self._trust.items())},
            "open_recommendations": [
                recommendation_to_dict(r)
                for r in self._recs.values()
                if r.id not in self._decisions
            ],
        }

    def decision_for(self, recommendation_id: str) -> Decision | None:
        return self._decisions.get(recommendation_id)

    def recommendation(self, recommendation_id: str) -> Recommendation | None:
        return self._recs.get(recommendation_id)

    def now(self) -> float:
        return self._clock()
