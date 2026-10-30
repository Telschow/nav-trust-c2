"""Replay recorded runs through the onboard monitor (issue 76). Evaluation only.

The C2 link signal is the recording's own `link_cut` and `link_restore` events, so this shows
when the monitor's rule fires given a cut, not that PX4 treats the cut as a lost link. The trust
inputs are PX4's own figures run through the trust engine (ADR 0005, option c); the monitor's rule
is not calibrated against ground truth, and nothing here says it is.

    python -m eval.onboard_replay eval/lost_link/recordings
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from c2.contingency import policy_sha256
from navtrust.engine import TrustEngine
from navtrust.recording import load_recording
from navtrust.replay import replay_engine
from sim.onboard_monitor import OnboardMonitor
from sim.onboard_policy import load_policy

POLICY_DOC: dict[str, Any] = {
    "entries": [{"reason": "INCONSISTENT_INNOVATION", "link": "NO_LINK", "action": "LAND"}],
    "wait_s": 5.0,  # proposal: below COM_DL_LOSS_T (10 s)
}
MAX_AGE_S = 4 * 3600.0


@dataclass(frozen=True)
class ReplayResult:
    cut_s: float | None  # when the recording's link was cut
    action_s: float | None  # when the monitor would have acted, None if it would not


def replay(path: Path) -> ReplayResult:
    recording = load_recording(path)
    policy = load_policy(
        {
            "audit_id": 0,
            "approved_s": 0.0,
            "sha256": policy_sha256(POLICY_DOC),
            "policy": POLICY_DOC,
        },
        now_s=0.0,
        max_age_s=MAX_AGE_S,
    )
    monitor = OnboardMonitor("uav1", policy, started_s=0.0)
    cut = recording.first("link_cut")
    restore = recording.first("link_restore")
    cut_s = float(cut["t_s"]) if cut else None
    restore_s = float(restore["t_s"]) if restore else None
    for report in replay_engine(recording, TrustEngine("uav1")):
        t = report.stamp_s
        link_up = cut_s is None or t < cut_s or (restore_s is not None and t >= restore_s)
        if link_up:
            monitor.c2_heard(t)
        monitor.trust(t, report)
        action = monitor.poll(t)
        if action is not None:
            return ReplayResult(cut_s, action.t_s)
    return ReplayResult(cut_s, None)


def table(directory: Path) -> str:
    rows = [
        "| Recording | Link cut at (s) | Monitor acts at (s) | After the cut (s) |",
        "|---|---:|---:|---:|",
    ]
    for path in sorted(directory.glob("*.jsonl")):
        r = replay(path)
        cut = f"{r.cut_s:.1f}" if r.cut_s is not None else "no cut"
        act = f"{r.action_s:.1f}" if r.action_s is not None else "no action"
        after = (
            f"{r.action_s - r.cut_s:.1f}" if r.action_s is not None and r.cut_s is not None else ""
        )
        rows.append(f"| {path.stem} | {cut} | {act} | {after} |")
    return "\n".join(rows) + "\n"


def main() -> None:
    p = argparse.ArgumentParser(description="Replay recordings through the onboard monitor")
    p.add_argument("recordings", type=Path)
    print(table(p.parse_args().recordings), end="")


if __name__ == "__main__":
    main()
