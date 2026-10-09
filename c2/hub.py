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

    # --- subscriptions -------------------------------------------------------------------

    def subscribe(self, callback: Callable[[Event], None]) -> Callable[[], None]:
        self._subscribers.append(callback)
        return lambda: self._subscribers.remove(callback)

    def _publish(self, event: Event) -> None:
        for callback in list(self._subscribers):
            callback(event)

    # --- inputs --------------------------------------------------------------------------

    def ingest_navtrust(self, msg: NavTrust) -> None:
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
            "vehicles": {v: navtrust_to_dict(m) for v, m in sorted(self._trust.items())},
            "open_recommendations": [
                recommendation_to_dict(r)
                for r in self._recs.values()
                if r.id not in self._decisions
            ],
        }

    def decision_for(self, recommendation_id: str) -> Decision | None:
        return self._decisions.get(recommendation_id)
