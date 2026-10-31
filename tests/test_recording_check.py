"""When is a recording complete? The scripts skip complete ones and discard the rest."""

import json
from pathlib import Path
from typing import Any

import pytest

from sim.recording_check import incomplete_reason, is_complete

HEADER = {"t_s": 0.0, "event": "header", "schema": 1, "ground_truth": True}
TRUTH = {"t_s": 1.0, "event": "truth", "vehicle": "uav1", "east_m": 0, "north_m": 0, "alt_m": 0}


def write(tmp_path: Path, *records: dict[str, Any]) -> Path:
    path = tmp_path / "run.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    return path


def test_a_run_that_was_stopped_is_complete(tmp_path: Path) -> None:
    stop = {"t_s": 9.0, "event": "recording_stopped", "reason": "max_duration"}
    assert is_complete(write(tmp_path, HEADER, TRUTH, stop))


def test_a_mission_that_finished_normally_is_complete_without_a_stop_event(tmp_path: Path) -> None:
    assert is_complete(write(tmp_path, HEADER, TRUTH, {"t_s": 9.0, "event": "landed"}))


def test_a_run_cut_short_is_not_complete(tmp_path: Path) -> None:
    path = write(tmp_path, HEADER, TRUTH, {"t_s": 5.0, "event": "position"})
    assert not is_complete(path)
    assert "end" in str(incomplete_reason(path))


def test_ground_truth_that_was_asked_for_but_never_recorded_is_not_complete(tmp_path: Path) -> None:
    stop = {"t_s": 9.0, "event": "recording_stopped", "reason": "max_duration"}
    path = write(tmp_path, HEADER, stop)
    assert not is_complete(path)
    assert "ground truth" in str(incomplete_reason(path))


def test_a_run_made_without_ground_truth_needs_none(tmp_path: Path) -> None:
    stop = {"t_s": 9.0, "event": "recording_stopped", "reason": "disarmed"}
    assert is_complete(write(tmp_path, {**HEADER, "ground_truth": False}, stop))


@pytest.mark.parametrize(
    ("field", "value", "event"),
    [
        ("zone", {"west": 0, "east": 1, "south": 0, "north": 1}, "gnss_enter"),
        ("operator_action", {"action": "land", "delay_s": 5.0}, "operator_action"),
        ("link_cut", {"delay_s": 40.0}, "link_cut"),
    ],
)
def test_a_scheduled_fault_that_never_happened_is_not_complete(
    tmp_path: Path, field: str, value: dict[str, Any], event: str
) -> None:
    """A slow simulator can end the run before the vehicle reaches the zone."""
    stop = {"t_s": 9.0, "event": "recording_stopped", "reason": "max_duration"}
    header = {**HEADER, field: value}
    path = write(tmp_path, header, TRUTH, stop)
    assert not is_complete(path)
    assert event in str(incomplete_reason(path))
    assert is_complete(write(tmp_path, header, TRUTH, {"t_s": 5.0, "event": event}, stop))


@pytest.mark.parametrize("content", ["", "not json\n", '{"event": "position"}\n'])
def test_an_empty_or_headerless_file_is_not_complete(tmp_path: Path, content: str) -> None:
    path = tmp_path / "bad.jsonl"
    path.write_text(content, encoding="utf-8")
    assert not is_complete(path)


def test_a_missing_file_is_not_complete(tmp_path: Path) -> None:
    assert not is_complete(tmp_path / "nope.jsonl")


def test_every_committed_recording_that_ends_is_complete() -> None:
    """The check must not reject recordings the project already relies on."""
    root = Path(__file__).resolve().parent.parent
    for directory in ("eval/recordings", "eval/lost_link/recordings", "eval/heldout/recordings"):
        for path in sorted((root / directory).glob("*.jsonl")):
            assert is_complete(path), f"{path.name}: {incomplete_reason(path)}"
