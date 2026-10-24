"""Time from GNSS loss to a controlled descent, measured from ground-truth altitude.

Evaluation only: the trust engine never sees ground truth. The recordings carry no flight-mode
events, so this measures what the vehicle did, not which PX4 mechanism did it.

Definitions (all thresholds are proposals):

- outage: a `gnss_enter` and the matching `gnss_exit`, or to the end of the run if none.
- descent confirmed: the first truth sample at least `DESCENT_CONFIRM_M` below the survey altitude,
  no later than `REACTION_WINDOW_S` after GNSS came back (a landing long after that is the mission
  ending, not a reaction to the outage).
- descent onset: the last level truth sample before that (within `LEVEL_TOLERANCE_M` of the survey
  altitude), so it is early by at most one truth sample interval. Seconds after the GNSS loss.
- touchdown: the first truth sample at or below `TOUCHDOWN_M`. Seconds after the GNSS loss.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from navtrust.recording import Recording, load_recording

DESCENT_CONFIRM_M = 1.0  # proposal
LEVEL_TOLERANCE_M = 0.3  # proposal
TOUCHDOWN_M = 0.5  # proposal
REACTION_WINDOW_S = 10.0  # proposal: how long after GNSS returns a descent still counts


@dataclass(frozen=True)
class OutageResult:
    start_s: float
    duration_s: float | None  # None if GNSS never came back
    descended: bool
    descent_onset_s: float | None
    touchdown_s: float | None


def measure_outages(recording: Recording) -> list[OutageResult]:
    cruise_m = float(recording.header["survey"]["altitude_m"])
    truth = [(r["t_s"], r["alt_m"]) for r in recording.of("truth")]
    exits = [r["t_s"] for r in recording.of("gnss_exit")]
    results = []
    for enter in recording.of("gnss_enter"):
        start_s = enter["t_s"]
        duration_s = next((t - start_s for t in exits if t > start_s), None)
        after = [(t, a) for t, a in truth if t >= start_s]
        until = start_s + duration_s + REACTION_WINDOW_S if duration_s is not None else None
        confirmed = next(
            (
                t
                for t, a in after
                if a <= cruise_m - DESCENT_CONFIRM_M and (until is None or t <= until)
            ),
            None,
        )
        onset = touchdown = None
        if confirmed is not None:
            level = [t for t, a in after if t < confirmed and a >= cruise_m - LEVEL_TOLERANCE_M]
            onset = (level[-1] if level else start_s) - start_s
            touchdown = next((t - start_s for t, a in after if a <= TOUCHDOWN_M), None)
        results.append(OutageResult(start_s, duration_s, confirmed is not None, onset, touchdown))
    return results


def _seconds(value: float | None, missing: str) -> str:
    return f"{value:.1f}" if value is not None else missing


def table(recordings: Path) -> str:
    """One row per GNSS-off outage, for every recording that injects `off`."""
    rows = [
        "| Recording | GNSS back after (s) | Descended | Onset (s) | Touchdown (s) |",
        "|---|---|---|---|---|",
    ]
    for path in sorted(recordings.glob("*.jsonl")):
        recording = load_recording(path)
        if recording.header.get("failure_mode") != "off":
            continue
        for o in measure_outages(recording):
            back = _seconds(o.duration_s, "never")
            onset = _seconds(o.descent_onset_s, "none")
            down = _seconds(o.touchdown_s, "none")
            rows.append(
                f"| {path.stem} | {back} | {'yes' if o.descended else 'no'} | {onset} | {down} |"
            )
    return "\n".join(rows)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Time from GNSS loss to a controlled descent")
    p.add_argument("--recordings", type=Path, default=Path("eval/recordings"))
    args = p.parse_args(argv)
    print(table(args.recordings))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
