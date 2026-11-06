"""The shape of a contingency policy (ADR 0004), shared by the backend that records its approval
and the vehicle that relies on it, so that the backend never approves what a vehicle would refuse.

Pure Python. The only action is LAND and the only link condition is NO_LINK.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from navtrust.types import ReasonCode

LINK_CONDITIONS = ("NO_LINK",)
ACTIONS = ("LAND",)
POLICY_MAX_AGE_S = 4 * 3600.0  # proposal: how long a vehicle may rely on an approved policy
COM_DL_LOSS_T_S = 10  # proposal: PX4's default, seconds without a ground station before its
# data-link-loss failsafe starts. A contingency's wait must stay below it, so PX4's hold and its
# own action have not begun (ADR 0004). The simulated vehicles are set to it.


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


def validate_binding(policy: dict[str, Any]) -> None:
    """Raise ValueError unless the policy names the mission and the vehicles it covers (ADR 0004
    item 5, amended 2026-11-06). Both are inside the hashed content."""
    mission = policy.get("mission_id")
    if not isinstance(mission, str) or not mission.strip():
        raise ValueError("a policy needs a mission_id")
    vehicles = policy.get("vehicles")
    if not isinstance(vehicles, list) or not vehicles:
        raise ValueError("a policy needs a list of vehicles")
    if not all(isinstance(v, str) and v.strip() for v in vehicles) or len(set(vehicles)) != len(
        vehicles
    ):
        raise ValueError("vehicles must be distinct, non-blank ids")


@dataclass(frozen=True)
class PolicyEntry:
    reason: str
    link: str
    action: str


def policy_entries(policy: dict[str, Any]) -> tuple[PolicyEntry, ...]:
    return tuple(PolicyEntry(e["reason"], e["link"], e["action"]) for e in policy["entries"])


def matching_entry(
    entries: Iterable[PolicyEntry], reason: str | None, link: str
) -> PolicyEntry | None:
    """The entry that authorises an action for this reason and link condition, if any. The one
    answer to "is this within the policy", for the vehicle that acts and the backend that checks."""
    if reason is None:
        return None
    return next((e for e in entries if e.reason == reason and e.link == link), None)
