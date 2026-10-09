"""The consistency detector over the committed recordings.

Default thresholds are proposals. The asserted numbers were measured on these recordings
(4 nominal runs, one run each of off / wrong / stuck) and bound this data only.
"""

from pathlib import Path

import pytest

from navtrust.consistency import Consistency, ConsistencyConfig, ConsistencyDetector
from navtrust.recording import Recording, load_recording
from navtrust.replay import replay_consistency

DATA = Path(__file__).parent / "data"
NO_CONSISTENCY_FAULT = [
    "nominal-1",
    "nominal-2",
    "nominal-3",
    "nominal-4",
    "jamming_zone-1",
    "wrong_zone-1",
]


def load(name: str) -> Recording:
    return load_recording(DATA / f"{name}.jsonl")


def inconsistent_count(name: str, config: ConsistencyConfig | None = None) -> int:
    reports = replay_consistency(load(name), ConsistencyDetector(config))
    return sum(r.status is Consistency.INCONSISTENT for r in reports)


@pytest.mark.parametrize("name", NO_CONSISTENCY_FAULT)
def test_no_false_alerts_without_a_consistency_fault(name: str) -> None:
    """Includes the GNSS-off and wrong-fix zone runs: those are availability faults and
    must not be reported as inconsistency."""
    assert inconsistent_count(name) == 0


def test_stuck_position_is_flagged_quickly_and_stays_flagged() -> None:
    rec = load("stuck_zone-1")
    reports = replay_consistency(rec, ConsistencyDetector())
    fault = rec.first("gnss_enter")
    assert fault is not None
    first = next(r for r in reports if r.status is Consistency.INCONSISTENT)
    assert 0 < first.stamp_s - fault["t_s"] <= 5.0  # measured 3.3 s
    assert all(r.status is Consistency.INCONSISTENT for r in reports if r.stamp_s >= first.stamp_s)
    assert first.max_ratio is not None and first.max_ratio >= 1.0


def test_flag_is_raised_only_after_the_fault_starts() -> None:
    rec = load("stuck_zone-1")
    fault = rec.first("gnss_enter")
    assert fault is not None
    early = [
        r
        for r in replay_consistency(rec, ConsistencyDetector())
        if r.stamp_s < fault["t_s"] and r.status is Consistency.INCONSISTENT
    ]
    assert early == []


@pytest.mark.parametrize("threshold", [0.5, 0.8, 1.0, 1.5])
def test_separation_holds_across_a_band_of_thresholds(threshold: float) -> None:
    """Not a tuning result: it shows the default is not on the edge of what works here."""
    cfg = ConsistencyConfig(ratio_threshold=threshold)
    assert all(inconsistent_count(n, cfg) == 0 for n in NO_CONSISTENCY_FAULT)
    assert inconsistent_count("stuck_zone-1", cfg) > 0
