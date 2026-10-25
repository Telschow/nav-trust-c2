"""Where and how fast a vehicle was when it touched down, from the ground truth in a recording.

Evaluation only. Distances are metres from the first truth sample. The speed is the horizontal
displacement between the first truth sample at or below `LOW_ALT_M` and the touchdown sample,
divided by the time between them, so it is a mean over that window and the window is reported.
A window of zero length gives no speed. Touchdown is the first truth sample at or below
`TOUCHDOWN_M` after the link cut, or after the first sample when the run has no cut.

    python -m eval.touchdown_state eval/lost_link/recordings
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from eval.blind_land import TOUCHDOWN_M
from navtrust.recording import Recording, load_recording

LOW_ALT_M = 3.0  # proposal: ADR 0003 quotes the speed "when below 3 m altitude"


@dataclass(frozen=True)
class TouchdownState:
    farthest_m: float
    touchdown_from_start_m: float
    speed_m_s: float | None
    window_s: float


def _horizontal(a: dict[str, Any], b: dict[str, Any]) -> float:
    return math.hypot(b["east_m"] - a["east_m"], b["north_m"] - a["north_m"])


def measure_touchdown(recording: Recording) -> TouchdownState | None:
    truth = recording.of("truth")
    if not truth:
        return None
    cut = recording.first("link_cut")
    after = cut["t_s"] if cut else truth[0]["t_s"] - 1.0
    down = next(
        (i for i, r in enumerate(truth) if r["t_s"] > after and r["alt_m"] <= TOUCHDOWN_M), None
    )
    if down is None:
        return None
    low = next(i for i, r in enumerate(truth) if r["t_s"] > after and r["alt_m"] <= LOW_ALT_M)
    window = truth[down]["t_s"] - truth[low]["t_s"]
    speed = _horizontal(truth[low], truth[down]) / window if window > 0 else None
    return TouchdownState(
        farthest_m=max(_horizontal(truth[0], r) for r in truth),
        touchdown_from_start_m=_horizontal(truth[0], truth[down]),
        speed_m_s=speed,
        window_s=window,
    )


def table(recordings: Path) -> str:
    rows = [
        "| Recording | Farthest from start (m) | Touchdown from start (m) "
        "| Horizontal speed below 3 m (m/s) | Window (s) |",
        "|---|---:|---:|---:|---:|",
    ]
    for path in sorted(recordings.glob("*.jsonl")):
        state = measure_touchdown(load_recording(path))
        if state is None:
            rows.append(f"| {path.stem} | no touchdown | | | |")
            continue
        speed = f"{state.speed_m_s:.1f}" if state.speed_m_s is not None else "none"
        rows.append(
            f"| {path.stem} | {state.farthest_m:.0f} | {state.touchdown_from_start_m:.0f} "
            f"| {speed} | {state.window_s:.1f} |"
        )
    return "\n".join(rows)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Position and speed at touchdown, from ground truth")
    p.add_argument("recordings", type=Path, nargs="?", default=Path("eval/lost_link/recordings"))
    print(table(p.parse_args(argv).recordings))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
