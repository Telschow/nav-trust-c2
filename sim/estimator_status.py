"""The estimator health fields of an ESTIMATOR_STATUS message, picked out for recordings and for
the onboard monitor. Kept apart from `sim.record_run` so that nothing here needs the MAVSDK
package (the `sim` extra): the monitor's logic and its tests run without it (issue 163)."""

from __future__ import annotations

import json
from typing import Any

ESTIMATOR_FIELDS = (
    "vel_ratio",
    "pos_horiz_ratio",
    "pos_vert_ratio",
    "mag_ratio",
    "pos_horiz_accuracy",
    "pos_vert_accuracy",
    "flags",
)


def parse_estimator_status(fields_json: str) -> dict[str, Any]:
    """Pick the estimator health fields from an ESTIMATOR_STATUS message, dropping nulls."""
    fields = json.loads(fields_json)
    return {k: fields[k] for k in ESTIMATOR_FIELDS if fields.get(k) is not None}
