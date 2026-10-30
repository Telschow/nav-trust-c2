"""Backend logic: latest trust per vehicle, recommendations, operator decisions, audit.

No web framework here, so it is tested directly. Every state change is written to the audit
log; a rejected decision attempt is logged too.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from c2.audit import AuditLog
from c2.contingency import policy_sha256, validate_policy
from c2.messages import (
    Decision,
    Outcome,
    Recommendation,
    decision_to_dict,
    navtrust_to_dict,
    recommendation_to_dict,
)
from navtrust.types import NavTrust, ReasonCode, TrustState

Event = dict[str, Any]

POLICY_MAX_AGE_S = 4 * 3600.0  # proposal: how long a vehicle may rely on an approved policy


class LinkState(StrEnum):
    """Whether the backend is hearing a vehicle. Says nothing about its navigation."""

    LINK_OK = "LINK_OK"
    NO_LINK = "NO_LINK"


class HubError(Exception):
    """Base class; `code` is a stable machine-readable reason."""

    code = "error"


class UnknownRecommendation(HubError):
    code = "unknown_recommendation"


class AlreadyDecided(HubError):
    code = "already_decided"


class ExpiredRecommendation(HubError):
    code = "expired"


class InvalidPolicy(HubError):
    code = "invalid_policy"


class UnknownPolicy(HubError):
    code = "unknown_policy"


class SupersededRecommendation(HubError):
    code = "superseded"


class InvalidOutcome(HubError):
    code = "invalid_outcome"


class InvalidOperator(HubError):
    code = "invalid_operator"


class DuplicateRecommendation(HubError):
    code = "duplicate_recommendation"


@dataclass
class _Outage:
    """One stretch of a vehicle having no link, kept until the first trust report after it."""

    detected_s: float
    trust_at_loss: tuple[TrustState, ReasonCode | None] | None
    ended_s: float | None = None
    duration_s: float = 0.0
    changes: list[dict[str, Any]] = field(default_factory=list)


class Hub:
    def __init__(
        self, audit: AuditLog, clock: Callable[[], float], link_timeout_s: float = 2.0
    ) -> None:
        """link_timeout_s: a vehicle silent for longer than this is NO_LINK (proposal: four report
        intervals at the default 0.5 s feed rate). The server's own clock, not the feed's."""
        self._audit = audit
        self.audit = audit
        self._clock = clock
        self._link_timeout_s = link_timeout_s
        self._last_report_s: dict[str, float] = {}
        self._link: dict[str, LinkState] = {}
        self._outage: dict[str, _Outage] = {}
        self._onboard_actions: list[tuple[float, dict[str, Any]]] = []  # (server_s, report)
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
        self._note_report(msg.vehicle_id)
        previous = self._trust.get(msg.vehicle_id)
        self._trust[msg.vehicle_id] = msg
        outage = self._outage.get(msg.vehicle_id)
        if outage is not None and (previous is None or _situation(previous) != _situation(msg)):
            outage.changes.append(
                {
                    "server_s": self._clock(),
                    "state": msg.state.value,
                    "reason": msg.reason.value if msg.reason else None,
                }
            )
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
        if outage is not None and outage.ended_s is not None:
            self._reconcile(msg.vehicle_id, outage, msg)

    def ingest_position(
        self, vehicle_id: str, lat_deg: float, lon_deg: float, alt_m: float
    ) -> None:
        """Latest position for the map. High rate, so it is published but not audited."""
        if not (-90 <= lat_deg <= 90 and -180 <= lon_deg <= 180):
            raise ValueError("latitude or longitude out of range")
        self._note_report(vehicle_id)
        pos = {"lat_deg": lat_deg, "lon_deg": lon_deg, "alt_m": alt_m, "stamp_s": self._clock()}
        self._positions[vehicle_id] = pos
        self._publish({"type": "position", "data": {"vehicle_id": vehicle_id, **pos}})

    def is_reachable(self, vehicle_id: str) -> bool:
        """Whether the backend can hear a vehicle now. Computed from the age of its last report,
        so it does not wait for a sweep. A vehicle never heard from is not known to be lost."""
        last_s = self._last_report_s.get(vehicle_id)
        return last_s is None or not self._is_silent(self._clock() - last_s)

    def latest_trust(self, vehicle_id: str) -> NavTrust | None:
        return self._trust.get(vehicle_id)

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

    def approve_policy(
        self, policy: dict[str, Any], operator: str, max_wait_s: float
    ) -> dict[str, Any]:
        """Record the operator's approval, before the mission, of a contingency policy (ADR 0004).

        The approval is an audited row; the vehicle accepts the policy only with that row's id and
        the policy's hash, and only up to POLICY_MAX_AGE_S. max_wait_s: PX4's data-link-loss time,
        so a policy no vehicle would accept is refused here and not at the vehicle."""
        if not isinstance(operator, str) or not operator.strip():
            raise InvalidOperator(repr(operator))
        try:
            validate_policy(policy, max_wait_s)
        except (ValueError, TypeError, AttributeError) as err:
            raise InvalidPolicy(str(err)) from err
        sha = policy_sha256(policy)
        now = self._clock()
        row = self._audit.append(
            now,
            "policy_approved",
            None,
            {"operator": operator.strip(), "policy": policy, "sha256": sha,
             "max_age_s": POLICY_MAX_AGE_S},
        )  # fmt: skip
        return {
            "audit_id": row.id,
            "approved_s": now,
            "sha256": sha,
            "max_age_s": POLICY_MAX_AGE_S,
            "policy": policy,
        }

    def report_onboard_action(self, report: dict[str, Any]) -> None:
        """A vehicle says what it did on its own, citing the policy it did it under. Accepted only
        if that policy approval is in the audit log with the same hash; audited either way."""
        vehicle_id = str(report["vehicle_id"])
        approved = [
            e
            for e in self._audit.events("policy_approved")
            if e.id == report.get("policy_audit_id")
            and e.payload["sha256"] == report.get("policy_sha256")
        ]
        if not approved:
            self._audit.append(
                self._clock(),
                "rejected_onboard_action",
                vehicle_id,
                {**report, "rejected_because": UnknownPolicy.code},
            )
            raise UnknownPolicy(str(report.get("policy_audit_id")))
        self._note_report(vehicle_id)  # hearing from the vehicle at all
        self._audit.append(self._clock(), "onboard_action", vehicle_id, report)
        self._onboard_actions.append((self._clock(), report))
        self._publish({"type": "onboard_action", "data": report})

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
            # A decision is only an operator approval if it names the operator (C2-01).
            if not isinstance(operator, str) or not operator.strip():
                raise InvalidOperator(repr(operator))
            rec = self._recs.get(recommendation_id)
            if rec is None:
                raise UnknownRecommendation(recommendation_id)
            existing = self._decisions.get(recommendation_id)
            if existing is not None:
                if existing.outcome is Outcome.EXPIRED:
                    raise ExpiredRecommendation(recommendation_id)
                if existing.outcome is Outcome.SUPERSEDED:
                    raise SupersededRecommendation(recommendation_id)
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
        """Mark vehicles silent past the timeout NO_LINK, and recommendations past their expiry
        EXPIRED (each once). Returns the newly expired decisions."""
        now = self._clock()
        for vehicle_id, last_s in self._last_report_s.items():
            if self._link[vehicle_id] is LinkState.LINK_OK and self._is_silent(now - last_s):
                self._set_link(vehicle_id, LinkState.NO_LINK, now - last_s)
        expired = []
        for rec in self._recs.values():
            if rec.id not in self._decisions and now > rec.expires_s:
                heard = self.is_reachable(rec.vehicle_id)
                decision = Decision(rec.id, Outcome.EXPIRED, now, "system", vehicle_heard=heard)
                self._record(decision, rec.vehicle_id)
                expired.append(decision)
        return expired

    def _note_report(self, vehicle_id: str) -> None:
        """Any report from a vehicle (trust or position) counts as hearing from it."""
        now = self._clock()
        silence_s = now - self._last_report_s.get(vehicle_id, now)
        self._link.setdefault(vehicle_id, LinkState.LINK_OK)
        if self._link[vehicle_id] is LinkState.LINK_OK and self._is_silent(silence_s):
            self._set_link(vehicle_id, LinkState.NO_LINK, silence_s)  # an outage nobody swept
        self._last_report_s[vehicle_id] = now
        if self._link[vehicle_id] is LinkState.NO_LINK:
            self._set_link(vehicle_id, LinkState.LINK_OK, silence_s)

    def _is_silent(self, age_s: float) -> bool:
        """Strictly older than the timeout: a report exactly at the limit is still a live link."""
        return age_s > self._link_timeout_s

    def _set_link(self, vehicle_id: str, state: LinkState, last_report_age_s: float) -> None:
        """Record a link change. last_report_age_s: how old the vehicle's last report was when this
        happened, so for LINK_OK it is the length of the silence that just ended."""
        previous = self._link[vehicle_id]
        self._link[vehicle_id] = state
        if state is LinkState.NO_LINK:
            pending = self._outage.get(vehicle_id)
            if pending is not None:  # gone again before a trust report closed the last outage
                pending.ended_s = None
            else:
                latest = self._trust.get(vehicle_id)
                self._outage[vehicle_id] = _Outage(
                    self._clock(), _situation(latest) if latest is not None else None
                )
        elif vehicle_id in self._outage:
            self._outage[vehicle_id].ended_s = self._clock()
            self._outage[vehicle_id].duration_s = last_report_age_s
        self._audit.append(
            self._clock(),
            "link_change",
            vehicle_id,
            {
                "state": state,
                "previous_state": previous,
                "last_report_age_s": last_report_age_s,
                "link_timeout_s": self._link_timeout_s,
            },
        )
        self._publish(
            {
                "type": "link",
                "data": {
                    "vehicle_id": vehicle_id,
                    "state": state,
                    "last_report_age_s": last_report_age_s,
                },
            }
        )

    def _reconcile(self, vehicle_id: str, outage: _Outage, latest: NavTrust) -> None:
        """The first trust report after an outage: close what the outage made stale and say what
        changed. A recommendation raised before the outage is superseded if the vehicle's trust
        state or reason is no longer what it was; the recommender raises a new one if needed."""
        del self._outage[vehicle_id]
        # with no earlier trust report there is nothing to say has changed
        changed = outage.trust_at_loss is not None and outage.trust_at_loss != _situation(latest)
        superseded: list[str] = []
        if changed:
            for rec in list(self._recs.values()):
                if (
                    rec.vehicle_id == vehicle_id
                    and rec.id not in self._decisions
                    and rec.created_s <= outage.detected_s
                ):
                    self._record(
                        Decision(
                            rec.id,
                            Outcome.SUPERSEDED,
                            self._clock(),
                            "system",
                            note="the situation changed while the link was down",
                        ),
                        vehicle_id,
                    )
                    superseded.append(rec.id)
        summary = {
            "vehicle_id": vehicle_id,
            "duration_s": outage.duration_s,
            "trust": navtrust_to_dict(latest),
            "trust_changes": outage.changes,
            "onboard_actions": [
                r
                for at_s, r in self._onboard_actions
                if r["vehicle_id"] == vehicle_id and at_s >= outage.detected_s
            ],
            "superseded": superseded,
        }
        self._audit.append(self._clock(), "outage_summary", vehicle_id, summary)
        self._publish({"type": "outage_summary", "data": summary})

    def _record(self, decision: Decision, vehicle_id: str) -> None:
        self._decisions[decision.recommendation_id] = decision
        self._audit.append(self._clock(), "decision", vehicle_id, decision_to_dict(decision))
        self._publish({"type": "decision", "data": decision_to_dict(decision)})

    # --- queries -------------------------------------------------------------------------

    def state(self) -> dict[str, Any]:
        self.sweep()
        now = self._clock()
        return {
            "server_s": now,
            "source": self._source,
            "origin": self._origin,
            "positions": {v: {"vehicle_id": v, **p} for v, p in sorted(self._positions.items())},
            "vehicles": {v: navtrust_to_dict(m) for v, m in sorted(self._trust.items())},
            "links": {
                v: {
                    "vehicle_id": v,
                    "state": self._link[v],
                    "last_report_age_s": now - self._last_report_s[v],
                }
                for v in sorted(self._link)
            },
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


def _situation(msg: NavTrust) -> tuple[TrustState, ReasonCode | None]:
    """What a recommendation was raised about: the trust state and its reason."""
    return (msg.state, msg.reason)
