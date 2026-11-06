"""The vehicle-side monitor (issue 76, ADR 0004): act on a pre-approved contingency when the
operator cannot be reached.

The decision logic is pure and has no simulator dependency: it is told when the vehicle last
heard from the C2 (`c2_heard`), what the trust engine says (`trust`) and the time (`poll`), and
says when to LAND. The process that wires it to a vehicle is `sim/onboard_run.py`.

It acts only when all of these hold, and then only once (a LAND the vehicle refuses is tried
again, at most `MAX_LAND_ATTEMPTS` times in all and `LAND_RETRY_S` apart, and only while every
condition below still holds; the action is told to the backend once, with how it ended):

- the C2 has been heard before, and has been silent for longer than the policy's wait time;
- the vehicle's own trust state is RED and its reason matches a policy entry for NO_LINK;
- the trust report is recent (`TRUST_MAX_AGE_S`, a proposal), so a silent engine is not acted on;
- the policy approval is still young enough on the vehicle's own clock.

Otherwise it does nothing and keeps reporting. The inputs are PX4's own figures through
`TrustEngine` (ADR 0005, option c); the monitor's rule has not been calibrated against ground
truth, and no result may say it is.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, replace

from navtrust.types import NavTrust, TrustState
from sim.onboard_policy import Policy, PolicyEntry

TRUST_MAX_AGE_S = 2.0  # proposal: four report intervals at the default 0.5 s
MAX_LAND_ATTEMPTS = 3  # proposal: how many times a refused LAND is sent in all
LAND_RETRY_S = 1.0  # proposal: pause before a refused LAND is sent again


@dataclass(frozen=True)
class OnboardAction:
    """What the vehicle did on its own, with the policy it did it under."""

    vehicle_id: str
    t_s: float
    action: str
    reason: str
    link_down_s: float
    policy_audit_id: int
    policy_sha256: str
    outcome: str = "pending"  # then "acknowledged" (the vehicle accepted a LAND) or "failed"
    mission_id: str | None = None  # the mission the policy is bound to; None for an experiment
    report_id: str | None = (
        None  # the backend accepts a report with this id once; None for an experiment
    )


class OnboardMonitor:
    def __init__(
        self, vehicle_id: str, policy: Policy, started_s: float, land_retry_s: float = LAND_RETRY_S
    ) -> None:
        """started_s: the vehicle's clock when the policy was loaded."""
        self._vehicle_id = vehicle_id
        self._policy = policy
        self._started_s = started_s
        self._last_heard_s: float | None = None
        self._trust: NavTrust | None = None
        self._trust_at_s = float("-inf")
        self._land_retry_s = land_retry_s
        self._in_flight = False  # an action was returned and its result is not in yet
        self._settled = False  # acknowledged, or refused every time
        self._attempts = 0
        self._retry_at_s = float("-inf")
        self._refused: OnboardAction | None = None  # the last refused attempt, while retrying
        self._unreported: list[OnboardAction] = []

    def c2_heard(self, t_s: float) -> None:
        """Any contact from the C2 (a heartbeat, a command, an acknowledgement)."""
        self._last_heard_s = t_s

    def trust(self, t_s: float, report: NavTrust) -> None:
        self._trust, self._trust_at_s = report, t_s

    def poll(self, t_s: float) -> OnboardAction | None:
        """The action to take now, or None. Never returns a second action while one is awaiting
        its result (`land_result`), and none once it is settled."""
        if self._in_flight or self._settled or t_s < self._retry_at_s:
            return None
        found = self._authorised(t_s)
        if found is None:
            if self._refused is not None:  # no longer allowed to try again: say how it ended
                self._settle(replace(self._refused, outcome="failed"))
            return None
        entry, reason, down_s = found
        self._in_flight = True
        return OnboardAction(
            self._vehicle_id, t_s, entry.action, reason, down_s,
            self._policy.audit_id, self._policy.sha256,
            mission_id=self._policy.mission_id,
            report_id=uuid.uuid4().hex if self._policy.mission_id else None,
        )  # fmt: skip

    def land_result(self, action: OnboardAction, ok: bool, t_s: float) -> None:
        """Tell the monitor whether the vehicle accepted the action. A refusal is tried again after
        a pause unless it was the last attempt."""
        self._in_flight = False
        self._attempts += 1
        if ok:
            self._settle(replace(action, outcome="acknowledged"))
        elif self._attempts >= MAX_LAND_ATTEMPTS:
            self._settle(replace(action, outcome="failed"))
        else:
            self._refused = action
            self._retry_at_s = t_s + self._land_retry_s

    def _settle(self, action: OnboardAction) -> None:
        self._settled, self._refused = True, None
        self._unreported.append(action)

    def _authorised(self, t_s: float) -> tuple[PolicyEntry, str, float] | None:
        """The policy entry that allows acting now, the reason and how long the link has been
        down, or None if any condition fails."""
        if self._last_heard_s is None or self._trust is None:
            return None
        down_s = t_s - self._last_heard_s
        if down_s <= self._policy.wait_s:
            return None
        if t_s - self._trust_at_s > TRUST_MAX_AGE_S or self._trust.state is not TrustState.RED:
            return None
        reason = self._trust.reason.value if self._trust.reason else None
        entry = self._policy.matches(reason, "NO_LINK")
        if entry is None or reason is None:
            return None
        if not self._policy.valid_at(t_s, self._started_s):
            return None
        return entry, reason, down_s

    def requeue(self, actions: list[OnboardAction]) -> None:
        """Put actions back that could not be reported, ahead of any newer ones."""
        self._unreported = [*actions, *self._unreported]

    def take_unreported(self) -> list[OnboardAction]:
        """Settled actions not yet told to the backend. Call when the link is back, then report
        them."""
        out, self._unreported = self._unreported, []
        return out
