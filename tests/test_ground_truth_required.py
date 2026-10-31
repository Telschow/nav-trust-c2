"""A run that asked for ground truth and got none must fail, not pass quietly."""

from pathlib import Path

import pytest

pytest.importorskip("mavsdk_grpc")

from sim.record_run import GroundTruthMissing, _EventLog, ensure_ground_truth  # noqa: E402


def test_a_run_with_no_ground_truth_samples_fails_when_it_asked_for_them(tmp_path: Path) -> None:
    log = _EventLog(tmp_path / "run.jsonl", None)
    log.write("position", lat_deg=1.0)
    with pytest.raises(GroundTruthMissing, match="no ground truth"):
        ensure_ground_truth(log, requested=True)
    log.close()


def test_a_run_with_ground_truth_passes_and_one_that_did_not_ask_is_not_checked(
    tmp_path: Path,
) -> None:
    log = _EventLog(tmp_path / "run.jsonl", None)
    log.write("truth", vehicle="uav1")
    ensure_ground_truth(log, requested=True)
    ensure_ground_truth(_EventLog(tmp_path / "other.jsonl", None), requested=False)
    log.close()
