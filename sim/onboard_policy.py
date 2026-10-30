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

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from navtrust.types import ReasonCode
from sim.failsafe_params import COM_DL_LOSS_T_S

LINK_CONDITIONS = ("NO_LINK",)  # the only condition a contingency can name (ADR 0004)
ACTIONS = ("LAND",)  # the only action in v1


class PolicyRejected(Exception):
    """The vehicle will not rely on this policy."""


def policy_sha256(policy: dict[str, Any]) -> str:
    """Hash of the policy in a canonical form, so key order and layout do not matter."""
    canonical = json.dumps(policy, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


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


def _entry(raw: dict[str, Any]) -> PolicyEntry:
    reason, link, action = raw.get("reason"), raw.get("link"), raw.get("action")
    if reason not in {r.value for r in ReasonCode}:
        raise PolicyRejected(f"unknown reason {reason!r}")
    if link not in LINK_CONDITIONS:
        raise PolicyRejected(f"unknown link condition {link!r}")
    if action not in ACTIONS:
        raise PolicyRejected(f"action {action!r} is not allowed: only LAND")
    return PolicyEntry(str(reason), str(link), str(action))


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
    wait_s = float(policy.get("wait_s", 0))
    if not 0 < wait_s < COM_DL_LOSS_T_S:
        raise PolicyRejected(
            f"wait {wait_s} s must be above 0 and below COM_DL_LOSS_T {COM_DL_LOSS_T_S} s"
        )
    entries = tuple(_entry(e) for e in policy.get("entries", []))
    return Policy(entries, wait_s, audit_id, claimed, age_s, max_age_s)
