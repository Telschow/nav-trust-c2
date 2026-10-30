"""The shape of a contingency policy (ADR 0004), shared by the backend that records its approval
and the vehicle that relies on it, so that the backend never approves what a vehicle would refuse.

Pure Python. The only action is LAND and the only link condition is NO_LINK.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from navtrust.types import ReasonCode

LINK_CONDITIONS = ("NO_LINK",)
ACTIONS = ("LAND",)
POLICY_MAX_AGE_S = 4 * 3600.0  # proposal: how long a vehicle may rely on an approved policy


def land_on_inconsistent_position(wait_s: float) -> dict[str, Any]:
    """The contingency of ADR 0004: LAND when the position is inconsistent and the link is down
    for longer than wait_s."""
    return {
        "entries": [{"reason": "INCONSISTENT_INNOVATION", "link": "NO_LINK", "action": "LAND"}],
        "wait_s": wait_s,
    }


def policy_sha256(policy: dict[str, Any]) -> str:
    """Hash of the policy in a canonical form, so key order and layout do not matter."""
    canonical = json.dumps(policy, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_policy(policy: dict[str, Any], max_wait_s: float) -> None:
    """Raise ValueError unless the policy is one a vehicle may rely on. max_wait_s is exclusive:
    PX4's data-link-loss time, so its own failsafe has not started when the vehicle acts."""
    wait_s = float(policy.get("wait_s", 0))
    if not 0 < wait_s < max_wait_s:
        raise ValueError(f"wait {wait_s} s must be above 0 and below {max_wait_s} s")
    for raw in policy.get("entries", []):
        reason, link, action = raw.get("reason"), raw.get("link"), raw.get("action")
        if reason not in {r.value for r in ReasonCode}:
            raise ValueError(f"unknown reason {reason!r}")
        if link not in LINK_CONDITIONS:
            raise ValueError(f"unknown link condition {link!r}")
        if action not in ACTIONS:
            raise ValueError(f"action {action!r} is not allowed: only LAND")
