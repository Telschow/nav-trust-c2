"""Availability detector: is GNSS present, degraded, lost, or is our input stale?

Per ADR 0001 this is one of two detectors. It looks only at the receiver's reported fix type
and the estimator's reported position accuracy. It cannot see a receiver that reports a good
fix with a wrong position; that is the consistency detector's job.

Pure Python, no simulator dependency. Times are seconds on any monotonic clock, as long as
all inputs and reports use the same one.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

# MAVSDK / MAVLink GPS_FIX_TYPE names
_GOOD = {"FIX_3D", "FIX_DGPS", "RTK_FLOAT", "RTK_FIXED"}
_DEGRADED = {"FIX_2D"}
_LOST = {"NO_GPS", "NO_FIX"}


class Availability(StrEnum):
    OK = "OK"
    DEGRADED = "DEGRADED"
    LOST = "LOST"
    STALE = "STALE"


@dataclass(frozen=True)
class AvailabilityConfig:
    """All values are proposals until measured on more recordings."""

    stale_after_s: float = 3.0  # no input of any kind for this long -> STALE
    recover_after_s: float = 2.0  # fix must look good this long before OK is reported again

    def __post_init__(self) -> None:
        if self.stale_after_s <= 0 or self.recover_after_s < 0:
            raise ValueError("stale_after_s must be > 0 and recover_after_s >= 0")


@dataclass(frozen=True)
class AvailabilityReport:
    stamp_s: float
    status: Availability
    since_s: float  # how long the reported status has held
    horizontal_bound_m: float | None  # last estimator accuracy; None until one was received
    # True while the fix already looks good and the previous non-OK status is only being held
    # until recover_after_s has passed. Callers must not count this time as outage time.
    recovering: bool = False
    input_age_s: float | None = None  # time since any input arrived; None before the first


def classify_fix(fix_type: str) -> Availability:
    if fix_type in _GOOD:
        return Availability.OK
    if fix_type in _DEGRADED:
        return Availability.DEGRADED
    if fix_type in _LOST:
        return Availability.LOST
    raise ValueError(f"unknown fix type {fix_type!r}")


class AvailabilityDetector:
    def __init__(self, config: AvailabilityConfig | None = None) -> None:
        self._cfg = config or AvailabilityConfig()
        self._fix: Availability | None = None
        self._bound: float | None = None
        self._last_input_s: float | None = None
        self._reported = Availability.STALE
        self._reported_since_s: float | None = None
        self._ok_since_s: float | None = None

    def update_fix(self, t_s: float, fix_type: str) -> None:
        self._fix = classify_fix(fix_type)
        self._touch(t_s)

    def update_estimator(self, t_s: float, pos_horiz_accuracy_m: float | None) -> None:
        """An estimator status sample. It also counts as a sign of life for staleness."""
        if pos_horiz_accuracy_m is not None:
            if pos_horiz_accuracy_m < 0:
                raise ValueError("pos_horiz_accuracy_m must be >= 0")
            self._bound = pos_horiz_accuracy_m
        self._touch(t_s)

    def report(self, t_s: float) -> AvailabilityReport:
        raw = self._raw(t_s)
        if raw is Availability.OK and self._reported is not Availability.OK:
            # hold the previous non-OK status until the fix has looked good long enough
            if self._ok_since_s is None:
                self._ok_since_s = t_s
            if t_s - self._ok_since_s >= self._cfg.recover_after_s:
                self._set(Availability.OK, self._ok_since_s)
        else:
            self._ok_since_s = None
            if raw is not self._reported:
                self._set(raw, t_s)
        if self._reported_since_s is None:
            self._reported_since_s = t_s
        return AvailabilityReport(
            stamp_s=t_s,
            status=self._reported,
            since_s=t_s - self._reported_since_s,
            horizontal_bound_m=self._bound,
            recovering=raw is Availability.OK and self._reported is not Availability.OK,
            input_age_s=None if self._last_input_s is None else t_s - self._last_input_s,
        )

    def _raw(self, t_s: float) -> Availability:
        if self._last_input_s is None or t_s - self._last_input_s > self._cfg.stale_after_s:
            return Availability.STALE
        return self._fix if self._fix is not None else Availability.STALE

    def _touch(self, t_s: float) -> None:
        if self._last_input_s is not None and t_s < self._last_input_s:
            raise ValueError("inputs must arrive in time order")
        self._last_input_s = t_s

    def _set(self, status: Availability, since_s: float) -> None:
        self._reported = status
        self._reported_since_s = since_s
