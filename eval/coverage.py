"""How much of a survey area a vehicle actually covered, from ground truth.

The area is the rectangle the run was asked to survey (the header's survey width and height, in
the frame of the vehicle's home). A grid cell counts as covered when its centre lies within
`swath_half_width_m` of the vehicle's true track while it was airborne. The track is the
straight line between consecutive ground-truth samples. Needs ground truth; None without it.

The swath half-width is a proposal: the survey lanes are `spacing_m` apart, so half the spacing
covers the area exactly when every lane is flown. It is not a sensor model.
"""

from __future__ import annotations

import math

from navtrust.recording import Recording

AIRBORNE_ALT_M = 5.0  # proposal: below this the vehicle is taking off or landing, not surveying


def _distance_to_segment(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
    dx, dy = bx - ax, by - ay
    length2 = dx * dx + dy * dy
    f = 0.0 if length2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length2))
    return math.hypot(px - (ax + f * dx), py - (ay + f * dy))


def area_coverage(
    rec: Recording, swath_half_width_m: float | None = None, cell_m: float = 10.0
) -> float | None:
    """Fraction of the survey rectangle covered, in [0, 1]; None without truth or a survey."""
    header = rec.header
    survey = header.get("survey")
    truth = [t for t in rec.of("truth") if t["alt_m"] >= AIRBORNE_ALT_M]
    if not survey or len(truth) < 2:
        return None
    width, height = float(survey["width_m"]), float(survey["height_m"])
    half = swath_half_width_m if swath_half_width_m is not None else survey["spacing_m"] / 2
    cols, rows = max(1, round(width / cell_m)), max(1, round(height / cell_m))
    segments = [
        (a["east_m"], a["north_m"], b["east_m"], b["north_m"])
        for a, b in zip(truth, truth[1:], strict=False)
        if b["t_s"] - a["t_s"] < 5.0  # a gap this long is a gap in the data, not a straight flight
    ]
    covered = 0
    for i in range(cols):
        for j in range(rows):
            cx, cy = (i + 0.5) * width / cols, (j + 0.5) * height / rows
            if any(_distance_to_segment(cx, cy, *s) <= half for s in segments):
                covered += 1
    return covered / (cols * rows)
