"""Measure the link_loss scenario family from ground truth (issue 75). Evaluation only.

One row per recording in eval/lost_link/recordings, from the `truth` samples (Gazebo's real
position) and the events the recorder wrote. The trust engine never sees ground truth. All
thresholds are proposals.

- outcome: `landed` if the true altitude reached the ground (`TOUCHDOWN_M`) after the vehicle had
  been airborne, `held` if it did not and the last flight mode was HOLD, else `flying` at the end
  of the run.
- fault: the first of the GNSS fault (`gnss_enter`) and the link cut (`link_cut`).
- last trusted position: the true position at the last GREEN trust report before trust was first
  lost at or after the fault. If the engine never left GREEN there is no loss of trust, so the true
  position at the fault is used. The trust inputs are PX4's own figures (ADR 0005).
- distance: horizontal metres from the last trusted position to touchdown, or to the last sample
  if the vehicle did not land.
- controlled stop: landed with a horizontal speed below 3 m altitude of at most
  `CONTROLLED_SPEED_M_S` (as in eval.frozen_matrix). The time is from the fault to touchdown.
- survey area: east 0 to the survey width, north 0 to its height from the first truth sample,
  plus `SURVEY_MARGIN_M`. The figure is how far outside that box the vehicle got, 0 if it stayed in.
- authority: for each flight mode PX4 entered after the fault (other than MISSION and UNKNOWN),
  the authority it ran under, read from the recording's own events: a scripted `operator_action`
  or an `onboard_action` (a pre-authorised policy) in the 5 s before it, else a PX4 failsafe.

    python -m eval.link_loss eval/lost_link/recordings
    python -m eval.link_loss eval/lost_link/recordings --write eval/lost_link/results.md
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from eval.blind_land import TOUCHDOWN_M
from eval.frozen_matrix import CONTROLLED_SPEED_M_S
from eval.touchdown_state import measure_touchdown
from navtrust.engine import TrustEngine
from navtrust.recording import Recording, load_recording
from navtrust.replay import replay_engine
from navtrust.types import NavTrust, TrustState

SURVEY_MARGIN_M = 50.0  # proposal
AIRBORNE_M = 3.0
ATTRIBUTION_WINDOW_S = 5.0  # a mode change this soon after a command is that command's
IGNORED_MODES = ("MISSION", "UNKNOWN")


@dataclass(frozen=True)
class Row:
    name: str
    outcome: str
    distance_m: float
    touchdown_speed_m_s: float | None
    stop_after_fault_s: float | None  # None: no controlled stop
    outside_survey_m: float
    authority: str


def touchdown(truth: list[dict[str, Any]]) -> tuple[float, float, float] | None:
    """(t_s, east_m, north_m) of the first ground sample after the vehicle was airborne."""
    airborne_from = next((r["t_s"] for r in truth if r["alt_m"] > AIRBORNE_M), None)
    if airborne_from is None:
        return None
    down = next((r for r in truth if r["t_s"] > airborne_from and r["alt_m"] <= TOUCHDOWN_M), None)
    return None if down is None else (down["t_s"], down["east_m"], down["north_m"])


def last_trusted_time(reports: list[NavTrust], fault_s: float) -> float:
    """Time of the last GREEN report before trust was first lost at or after the fault; the
    fault time itself if trust was never lost."""
    lost = next(
        (r.stamp_s for r in reports if r.stamp_s >= fault_s and r.state is not TrustState.GREEN),
        None,
    )
    if lost is None:
        return fault_s
    green = [r.stamp_s for r in reports if r.stamp_s < lost and r.state is TrustState.GREEN]
    return green[-1] if green else fault_s


def survey_excess_m(truth: list[dict[str, Any]], survey: dict[str, float]) -> float:
    """How far outside the survey area plus its margin the vehicle got, at the worst."""
    west, south = -SURVEY_MARGIN_M, -SURVEY_MARGIN_M
    east, north = survey["width_m"] + SURVEY_MARGIN_M, survey["height_m"] + SURVEY_MARGIN_M
    worst = 0.0
    for r in truth:
        dx = max(west - r["east_m"], r["east_m"] - east, 0.0)
        dy = max(south - r["north_m"], r["north_m"] - north, 0.0)
        worst = max(worst, math.hypot(dx, dy))
    return worst


def authorities(records: list[dict[str, Any]], fault_s: float) -> list[str]:
    """Which authority each flight mode entered after the fault ran under, in order, once each."""
    commands = [(r["t_s"], k) for r in records if (k := _AUTHORITY.get(r["event"])) is not None]
    out: list[str] = []
    for r in records:
        if r["event"] != "flight_mode" or r["t_s"] <= fault_s or r["mode"] in IGNORED_MODES:
            continue
        by = next(
            (k for t, k in reversed(commands) if 0 <= r["t_s"] - t <= ATTRIBUTION_WINDOW_S),
            "PX4 failsafe",
        )
        entry = f"{by}: {r['mode']}"
        if entry not in out:
            out.append(entry)
    return out


_AUTHORITY = {"operator_action": "operator approval", "onboard_action": "pre-authorised policy"}


def _first_fault_s(recording: Recording) -> float:
    times = [e["t_s"] for kind in ("gnss_enter", "link_cut") if (e := recording.first(kind))]
    return float(min(times)) if times else 0.0


def _nearest(truth: list[dict[str, Any]], t_s: float) -> dict[str, Any]:
    return min(truth, key=lambda r: abs(r["t_s"] - t_s))


def measure_run(recording: Recording) -> Row:
    truth = recording.of("truth")
    fault_s = _first_fault_s(recording)
    reports = replay_engine(recording, TrustEngine("uav1"))
    reference = _nearest(truth, last_trusted_time(reports, fault_s))
    down = touchdown(truth)
    end = (down[1], down[2]) if down else (truth[-1]["east_m"], truth[-1]["north_m"])
    modes = [r["mode"] for r in recording.of("flight_mode")]
    outcome = "landed" if down else "held" if modes and modes[-1] == "HOLD" else "flying"
    state = measure_touchdown(recording) if down else None
    speed = state.speed_m_s if state is not None else None
    controlled = down is not None and speed is not None and speed <= CONTROLLED_SPEED_M_S
    return Row(
        name=str(recording.header.get("scenario", "")),
        outcome=outcome,
        distance_m=math.hypot(end[0] - reference["east_m"], end[1] - reference["north_m"]),
        touchdown_speed_m_s=speed,
        stop_after_fault_s=down[0] - fault_s if down is not None and controlled else None,
        outside_survey_m=survey_excess_m(truth, recording.header["survey"]),
        authority=", ".join(authorities(recording.records, fault_s)) or "none",
    )


def table(directory: Path) -> str:
    rows = [
        "| Recording | Outcome | Distance from last trusted position (m) "
        "| Speed below 3 m (m/s) | Fault to controlled stop (s) | Outside survey area + margin (m) "
        "| Authority of each action |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for path in sorted(directory.glob("*.jsonl")):
        r = measure_run(load_recording(path))
        speed = f"{r.touchdown_speed_m_s:.1f}" if r.touchdown_speed_m_s is not None else "none"
        stop = f"{r.stop_after_fault_s:.0f}" if r.stop_after_fault_s is not None else "none"
        outside = f"{r.outside_survey_m:.0f}" if r.outside_survey_m > 0 else "0"
        rows.append(
            f"| {path.stem} | {r.outcome} | {r.distance_m:.0f} | {speed} | {stop} | {outside} "
            f"| {r.authority} |"
        )
    return "\n".join(rows) + "\n"


def main() -> None:
    p = argparse.ArgumentParser(description="The link_loss family from ground truth (issue 75)")
    p.add_argument("recordings", type=Path)
    p.add_argument("--write", type=Path, help="write the table to this file")
    args = p.parse_args()
    out = table(args.recordings)
    if args.write:
        args.write.write_text(out, encoding="utf-8")
    else:
        print(out, end="")


if __name__ == "__main__":
    main()
