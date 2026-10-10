"""The calibrated position bound the trust engine reports while a vehicle is GREEN.

The estimator's own accuracy figure (about 0.15 m) is not a bound: in the development recordings
the true error was within it in only 30.8% of GREEN reports (median 0.57 m, 95th percentile
2.4 m, maximum 2.9 m). So the engine reports a bound measured against Gazebo ground truth instead.

    horizontal_bound_m = bound_m        the distance the true error stayed within
    confidence         = coverage       the share of reports for which it did, as claimed

Calibrated on the development set, checked on the held-out set (both: eval/recordings and
eval/heldout/recordings). `tests/test_calibration.py` recomputes every number here from those
recordings, so they cannot drift from the data. What this is and is not:

- Simulation only: PX4 SITL in Gazebo, one vehicle model, survey speeds of 5 to 12 m/s. The error
  grows with speed (nominal flights reach about 3 m at 12 m/s), so the bound is for that range.
- It is the error of the vehicle's own reported position, in GREEN, not a statement about
  anything else, and it says nothing about states other than GREEN (the bound is unknown there).
- Coverage 0.99 is the claim; the measured coverage on each set is recorded below.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BoundCalibration:
    bound_m: float
    coverage: float  # claimed
    development_reports: int
    development_coverage: float  # measured on the data the bound was chosen on
    heldout_reports: int
    heldout_coverage: float  # measured on data it was not chosen on
    source: str


GREEN_BOUND = BoundCalibration(
    bound_m=3.0,
    coverage=0.99,
    development_reports=4040,
    development_coverage=1.0,
    heldout_reports=5308,
    heldout_coverage=0.9972,
    source="PX4 SITL in Gazebo, one vehicle, 5 to 12 m/s; ground truth from Gazebo",
)
