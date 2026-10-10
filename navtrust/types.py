"""Message types for the trust engine output (spec section 2.2, `NavTrust`).

Types only. No detection logic exists yet; the engine arrives in milestone M1b.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class TrustState(StrEnum):
    GREEN = "GREEN"
    AMBER = "AMBER"
    RED = "RED"


class ReasonCode(StrEnum):
    GNSS_LOSS = "GNSS_LOSS"
    INCONSISTENT_INNOVATION = "INCONSISTENT_INNOVATION"
    BIAS_DRIFT = "BIAS_DRIFT"
    STALE = "STALE"


@dataclass(frozen=True)
class NavTrust:
    vehicle_id: str
    stamp_s: float
    state: TrustState
    reason: ReasonCode | None
    horizontal_bound_m: float
    confidence: float
    headroom: float = 0.0  # 0 at an alert condition, 1 far from any; 0 outside GREEN

    def __post_init__(self) -> None:
        if self.horizontal_bound_m < 0:
            raise ValueError("horizontal_bound_m must be >= 0")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be in [0, 1]")
        if not 0.0 <= self.headroom <= 1.0:
            raise ValueError("headroom must be in [0, 1]")
