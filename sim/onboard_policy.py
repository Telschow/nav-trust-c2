"""The contingency policy the operator approved before the mission (ADR 0004), as read on board.

A policy is a list of entries, each pairing a trust reason with a link condition and an action,
and a wait time. The only action is LAND. It travels with the audit row id and the SHA-256 of
the approval; the vehicle accepts it only if the hash matches, it is not older than a fixed
maximum age, and the wait is positive and shorter than PX4's data-link-loss time, so that PX4's
own failsafe has not started when the vehicle acts. This is integrity of the record, not
authentication (ADR 0004, item 5): anyone who can edit both the policy and its hash can forge it.

Pure Python, no simulator dependency.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from c2.contingency import policy_sha256, validate_policy
from sim.failsafe_params import COM_DL_LOSS_T_S

__all__ = ["Policy", "PolicyEntry", "PolicyRejected", "load_policy", "policy_sha256"]


class PolicyRejected(Exception):
    """The vehicle will not rely on this policy."""


@dataclass(frozen=True)
class PolicyEntry:
    reason: str
    link: str
    action: str


@dataclass(frozen=True)
class Policy:
    entries: tuple[PolicyEntry, ...]
    wait_s: float
    audit_id: int
    sha256: str
    age_at_load_s: float
    max_age_s: float

    def matches(self, reason: str | None, link: str) -> PolicyEntry | None:
        """The entry that authorises an action for this reason and link condition, if any."""
        if reason is None:
            return None
        return next((e for e in self.entries if e.reason == reason and e.link == link), None)

    def valid_at(self, local_s: float, loaded_local_s: float) -> bool:
        """Whether the approval is still young enough, on the vehicle's own clock."""
        return self.age_at_load_s + (local_s - loaded_local_s) <= self.max_age_s


def load_policy(approval: dict[str, Any], now_s: float, max_age_s: float) -> Policy:
    """Check an approval record and return the policy, or raise PolicyRejected.

    approval: {audit_id, approved_s, sha256, policy}. now_s is on the clock approved_s was
    stamped with (the backend's); the age is measured from there.
    """
    try:
        policy = approval["policy"]
        audit_id, approved_s, claimed = (
            int(approval["audit_id"]),
            float(approval["approved_s"]),
            approval["sha256"],
        )
    except (KeyError, TypeError, ValueError) as err:
        raise PolicyRejected(f"no approval record: {err!r}") from err
    if claimed != policy_sha256(policy):
        raise PolicyRejected("hash does not match the approval record")
    age_s = now_s - approved_s
    if age_s < 0:
        raise PolicyRejected("approval is dated in the future")
    if age_s > max_age_s:
        raise PolicyRejected(f"approval expired ({age_s:.0f} s old, limit {max_age_s:.0f} s)")
    try:
        validate_policy(policy, COM_DL_LOSS_T_S)
    except ValueError as err:
        raise PolicyRejected(str(err)) from err
    entries = tuple(PolicyEntry(e["reason"], e["link"], e["action"]) for e in policy["entries"])
    return Policy(entries, float(policy["wait_s"]), audit_id, claimed, age_s, max_age_s)
