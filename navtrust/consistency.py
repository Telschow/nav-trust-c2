"""Consistency detector: does the GNSS data the estimator is receiving agree with it?

Per ADR 0001 this is the second detector. It watches the estimator's innovation test ratios
(innovation divided by its gate, so 1.0 is where the estimator itself rejects a measurement)
and flags a window in which too many samples are high. It can only judge GPS data that
exists: it says nothing about a lost receiver (the availability detector's job), and with
no GPS measurements the ratios simply stop moving.

Not implemented: BIAS_DRIFT. There is no gradual-drift recording to develop it against.

Pure Python, no simulator dependency.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import StrEnum


class Consistency(StrEnum):
    UNKNOWN = "UNKNOWN"  # too few usable samples in the window
    CONSISTENT = "CONSISTENT"
    INCONSISTENT = "INCONSISTENT"


@dataclass(frozen=True)
class ConsistencyConfig:
    """All values are proposals. ratio_threshold = 1.0 is the estimator's own gate, chosen
    for that reason and not fitted to the recordings."""

    ratio_threshold: float = 1.0
    window_s: float = 5.0
    enter_fraction: float = 0.5  # flag when at least this share of the window is above
    clear_fraction: float = 0.2  # clear when the share falls to this or below
    min_samples: int = 3

    def __post_init__(self) -> None:
        if self.ratio_threshold <= 0 or self.window_s <= 0 or self.min_samples < 1:
            raise ValueError("ratio_threshold and window_s must be > 0, min_samples >= 1")
        if not 0.0 <= self.clear_fraction < self.enter_fraction <= 1.0:
            raise ValueError("need 0 <= clear_fraction < enter_fraction <= 1")


@dataclass(frozen=True)
class ConsistencyReport:
    stamp_s: float
    status: Consistency
    fraction_above: float | None  # share of window samples above the threshold
    samples: int
    max_ratio: float | None  # largest statistic in the window


class ConsistencyDetector:
    def __init__(self, config: ConsistencyConfig | None = None) -> None:
        self._cfg = config or ConsistencyConfig()
        self._window: deque[tuple[float, float]] = deque()  # (t_s, statistic)
        self._flagged = False
        self._last_t_s: float | None = None

    def update(self, t_s: float, pos_horiz_ratio: float | None, vel_ratio: float | None) -> None:
        """One estimator status sample. Missing ratios (estimator not fusing that data) are
        ignored; a sample with neither is skipped."""
        self._check_order(t_s)
        values = [v for v in (pos_horiz_ratio, vel_ratio) if v is not None]
        if any(v < 0 for v in values):
            raise ValueError("test ratios must be >= 0")
        if values:
            self._window.append((t_s, max(values)))

    def report(self, t_s: float) -> ConsistencyReport:
        self._check_order(t_s)
        while self._window and self._window[0][0] <= t_s - self._cfg.window_s:
            self._window.popleft()
        n = len(self._window)
        if n < self._cfg.min_samples:
            self._flagged = False
            return ConsistencyReport(t_s, Consistency.UNKNOWN, None, n, None)
        above = sum(1 for _, v in self._window if v >= self._cfg.ratio_threshold)
        fraction = above / n
        if self._flagged:
            self._flagged = fraction > self._cfg.clear_fraction
        else:
            self._flagged = fraction >= self._cfg.enter_fraction
        status = Consistency.INCONSISTENT if self._flagged else Consistency.CONSISTENT
        return ConsistencyReport(t_s, status, fraction, n, max(v for _, v in self._window))

    def _check_order(self, t_s: float) -> None:
        if self._last_t_s is not None and t_s < self._last_t_s:
            raise ValueError("inputs must arrive in time order")
        self._last_t_s = t_s
