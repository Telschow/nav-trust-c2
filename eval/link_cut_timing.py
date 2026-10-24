"""Time from a link cut to PX4's reaction and to touchdown, measured from a recording.

Evaluation only. The mode changes come from the `flight_mode` events the recorder writes for
runs with a link cut; touchdown comes from ground-truth altitude (needs `gz`). Times are seconds
after the `link_cut` event. If the recorder could not hear the vehicle after the cut, the mode
list will be empty and that is the finding, not a zero.

    python -m eval.link_cut_timing eval/lost_link/recordings
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from eval.blind_land import TOUCHDOWN_M
from navtrust.recording import Recording, load_recording


@dataclass(frozen=True)
class LinkCutTiming:
    cut_s: float
    mode_changes: list[tuple[str, float]]  # (new mode, seconds after the cut)
    touchdown_after_s: float | None


def measure_link_cut(recording: Recording) -> LinkCutTiming | None:
    cut = recording.first("link_cut")
    if cut is None:
        return None
    cut_s = cut["t_s"]
    changes = [
        (r["mode"], r["t_s"] - cut_s) for r in recording.of("flight_mode") if r["t_s"] > cut_s
    ]
    touchdown = next(
        (
            r["t_s"] - cut_s
            for r in recording.of("truth")
            if r["t_s"] > cut_s and r["alt_m"] <= TOUCHDOWN_M
        ),
        None,
    )
    return LinkCutTiming(cut_s, changes, touchdown)


def table(recordings: Path) -> str:
    rows = [
        "| Recording | Cut at (s) | Mode changes after the cut | Touchdown (s after) |",
        "|---|---|---|---|",
    ]
    for path in sorted(recordings.glob("*.jsonl")):
        timing = measure_link_cut(load_recording(path))
        if timing is None:
            continue
        modes = ", ".join(f"{m} +{s:.1f}" for m, s in timing.mode_changes) or "none heard"
        down = f"{timing.touchdown_after_s:.1f}" if timing.touchdown_after_s is not None else "none"
        rows.append(f"| {path.stem} | {timing.cut_s:.1f} | {modes} | {down} |")
    return "\n".join(rows)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Time from a link cut to PX4's reaction")
    p.add_argument("recordings", type=Path, nargs="?", default=Path("eval/lost_link/recordings"))
    print(table(p.parse_args(argv).recordings))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
