"""The vehicle-side monitor (issue 76, ADR 0004): act on a pre-approved contingency when the
operator cannot be reached.

The decision logic is pure and has no simulator dependency: it is told when the vehicle last
heard from the C2 (`c2_heard`), what the trust engine says (`trust`) and the time (`poll`), and
says when to LAND. The process that wires it to a vehicle is `sim/onboard_run.py`.

It acts only when all of these hold, and then only once:

- the C2 has been heard before, and has been silent for longer than the policy's wait time;
- the vehicle's own trust state is RED and its reason matches a policy entry for NO_LINK;
- the trust report is recent (`TRUST_MAX_AGE_S`, a proposal), so a silent engine is not acted on;
- the policy approval is still young enough on the vehicle's own clock.

Otherwise it does nothing and keeps reporting. The inputs are PX4's own figures through
`TrustEngine` (ADR 0005, option c); the monitor's rule has not been calibrated against ground
truth, and no result may say it is.
"""

from __future__ import annotations

from dataclasses import dataclass

from navtrust.types import NavTrust, TrustState
from sim.onboard_policy import Policy

TRUST_MAX_AGE_S = 2.0  # proposal: four report intervals at the default 0.5 s


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


class OnboardMonitor:
    def __init__(self, vehicle_id: str, policy: Policy, started_s: float) -> None:
        """started_s: the vehicle's clock when the policy was loaded."""
        self._vehicle_id = vehicle_id
        self._policy = policy
        self._started_s = started_s
        self._last_heard_s: float | None = None
        self._trust: NavTrust | None = None
        self._trust_at_s = float("-inf")
        self._acted = False
        self._unreported: list[OnboardAction] = []

    def c2_heard(self, t_s: float) -> None:
        """Any contact from the C2 (a heartbeat, a command, an acknowledgement)."""
        self._last_heard_s = t_s

    def trust(self, t_s: float, report: NavTrust) -> None:
        self._trust, self._trust_at_s = report, t_s

    def poll(self, t_s: float) -> OnboardAction | None:
        """The action to take now, or None. Never returns a second action."""
        if self._acted or self._last_heard_s is None or self._trust is None:
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
        self._acted = True
        action = OnboardAction(
            self._vehicle_id, t_s, entry.action, reason, down_s,
            self._policy.audit_id, self._policy.sha256,
        )  # fmt: skip
        self._unreported.append(action)
        return action

    def take_unreported(self) -> list[OnboardAction]:
        """Actions not yet told to the backend. Call when the link is back, then report them."""
        out, self._unreported = self._unreported, []
        return out
