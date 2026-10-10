"""Trust engine: combines the availability and consistency detectors into a NavTrust message.

ADR 0001. Mapping (all thresholds are proposals, see EngineConfig):

    detector finding                 state                 reason
    availability LOST / DEGRADED     AMBER, RED after      GNSS_LOSS (LOST only for RED)
                                     red_after_s lost
    availability STALE               AMBER, RED after      STALE
                                     red_after_s stale
    consistency INCONSISTENT         RED at once           INCONSISTENT_INNOVATION

The state is the worst of the findings. When several apply, the reason follows the order
GNSS_LOSS, then STALE, then INCONSISTENT_INNOVATION: a missing receiver explains more than a
frozen estimate. Hysteresis lives in the detectors (recovery hold, Schmitt trigger); the
engine adds none of its own.

Bound and confidence: in GREEN the engine reports the calibrated bound and the coverage it was
measured to have (calibration.py); the estimator's own accuracy figure is not a bound and is not
used. In every other state the bound is unknown (infinity) and confidence is 0. Headroom is how far
a GREEN vehicle is from an alert; it is 0 outside GREEN.

Pure Python, no simulator dependency.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from navtrust.availability import (
    Availability,
    AvailabilityConfig,
    AvailabilityDetector,
    AvailabilityReport,
)
from navtrust.calibration import GREEN_BOUND, BoundCalibration
from navtrust.consistency import (
    Consistency,
    ConsistencyConfig,
    ConsistencyDetector,
    ConsistencyReport,
)
from navtrust.types import NavTrust, ReasonCode, TrustState

_RANK = {TrustState.GREEN: 0, TrustState.AMBER: 1, TrustState.RED: 2}


@dataclass(frozen=True)
class EngineConfig:
    """All values are proposals."""

    red_after_s: float = 5.0  # LOST or STALE for this long escalates AMBER to RED
    # Position bound and its coverage while GREEN, measured against ground truth
    # (see calibration.py)
    calibration: BoundCalibration = GREEN_BOUND
    # Normal inputs arrive about once a second; freshness headroom only starts to shrink after this
    freshness_grace_s: float = 1.5
    availability: AvailabilityConfig = field(default_factory=AvailabilityConfig)
    consistency: ConsistencyConfig = field(default_factory=ConsistencyConfig)

    def __post_init__(self) -> None:
        if self.red_after_s < 0:
            raise ValueError("red_after_s must be >= 0")


class TrustEngine:
    def __init__(self, vehicle_id: str, config: EngineConfig | None = None) -> None:
        self._id = vehicle_id
        self._cfg = config or EngineConfig()
        self._availability = AvailabilityDetector(self._cfg.availability)
        self._consistency = ConsistencyDetector(self._cfg.consistency)
        self.last_availability: AvailabilityReport | None = None
        self.last_consistency: ConsistencyReport | None = None

    def update_fix(self, t_s: float, fix_type: str) -> None:
        self._availability.update_fix(t_s, fix_type)

    def update_estimator(
        self,
        t_s: float,
        pos_horiz_accuracy_m: float | None,
        pos_horiz_ratio: float | None,
        vel_ratio: float | None,
    ) -> None:
        self._availability.update_estimator(t_s, pos_horiz_accuracy_m)
        self._consistency.update(t_s, pos_horiz_ratio, vel_ratio)

    def report(self, t_s: float) -> NavTrust:
        avail = self._availability.report(t_s)
        cons = self._consistency.report(t_s)
        self.last_availability, self.last_consistency = avail, cons

        state, reason = self._decide(avail, cons)
        green = state is TrustState.GREEN
        return NavTrust(
            vehicle_id=self._id,
            stamp_s=t_s,
            state=state,
            reason=reason,
            horizontal_bound_m=self._cfg.calibration.bound_m if green else math.inf,
            confidence=self._cfg.calibration.coverage if green else 0.0,
            headroom=self._headroom(avail, cons) if green else 0.0,
        )

    def _headroom(self, avail: AvailabilityReport, cons: ConsistencyReport) -> float:
        """How far a GREEN vehicle is from an alert, 0 to 1. Not a probability.

        The smaller of two margins: the worst recent innovation test ratio against the estimator's
        own rejection gate, and how long the inputs have been silent against the stale limit."""
        margins = [1.0]
        if cons.max_ratio is not None:
            margins.append(1.0 - min(1.0, cons.max_ratio / self._cfg.consistency.ratio_threshold))
        if avail.input_age_s is not None:
            grace = self._cfg.freshness_grace_s
            span = max(self._cfg.availability.stale_after_s - grace, 1e-9)
            margins.append(1.0 - min(1.0, max(0.0, avail.input_age_s - grace) / span))
        return max(0.0, min(margins))

    def _decide(
        self, avail: AvailabilityReport, cons: ConsistencyReport
    ) -> tuple[TrustState, ReasonCode | None]:
        findings: list[tuple[TrustState, ReasonCode]] = []
        # Time spent only waiting to be sure the fix is back is not outage time.
        aged = avail.since_s >= self._cfg.red_after_s and not avail.recovering
        if avail.status in (Availability.LOST, Availability.DEGRADED):
            escalate = avail.status is Availability.LOST and aged
            findings.append(
                (TrustState.RED if escalate else TrustState.AMBER, ReasonCode.GNSS_LOSS)
            )
        elif avail.status is Availability.STALE:
            findings.append((TrustState.RED if aged else TrustState.AMBER, ReasonCode.STALE))
        if cons.status is Consistency.INCONSISTENT:
            findings.append((TrustState.RED, ReasonCode.INCONSISTENT_INNOVATION))

        if not findings:
            return TrustState.GREEN, None
        state = max((s for s, _ in findings), key=_RANK.__getitem__)
        order = [ReasonCode.GNSS_LOSS, ReasonCode.STALE, ReasonCode.INCONSISTENT_INNOVATION]
        reason = min((r for _, r in findings), key=order.index)
        return state, reason
