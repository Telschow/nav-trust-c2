"""Is a recording complete? The simulator scripts skip complete ones and throw the rest away.

A recording is complete if it has a header, ends the way a finished run does (the recorder's
`recording_stopped`, or `landed` when the mission ran to its end), and has ground-truth samples if
its header says ground truth was on. A file cut short by a failed run or a killed script, or one
whose Gazebo stream gave nothing, is not.

    python3 -m sim.recording_check FILE        # exit 0 if complete, 1 and a reason if not
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ENDINGS = ("recording_stopped", "landed")


def incomplete_reason(path: Path) -> str | None:
    """Why the recording is not complete, or None if it is."""
    try:
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line]
        records = [json.loads(line) for line in lines]
    except (OSError, ValueError):
        return "unreadable"
    if not records or records[0].get("event") != "header":
        return "no header"
    if records[-1].get("event") not in ENDINGS:
        return f"no proper end (last event {records[-1].get('event')!r})"
    if records[0].get("ground_truth") and not any(r.get("event") == "truth" for r in records):
        return "ground truth was on but no ground truth was recorded"
    return None


def is_complete(path: Path) -> bool:
    return incomplete_reason(path) is None


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: python3 -m sim.recording_check FILE", file=sys.stderr)
        return 2
    reason = incomplete_reason(Path(argv[0]))
    if reason is not None:
        print(f"{argv[0]}: {reason}", file=sys.stderr)
    return 0 if reason is None else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
