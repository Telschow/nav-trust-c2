"""Read run recordings (JSON lines) written by sim/record_run.py.

Pure Python, no simulator dependency, so CI can replay recordings without Gazebo.
Schema 1: the first line is a `header` record; every record has `t_s` (seconds since the
start of the recording) and `event`. Events: header, connected, home, plan, zone,
position, gps_info, estimator_status, gnss_enter, gnss_exit, inject_failed, armed,
mission_started, mission_progress, mission_finished, landed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA = 1


@dataclass(frozen=True)
class Recording:
    header: dict[str, Any]
    records: list[dict[str, Any]]

    def of(self, event: str) -> list[dict[str, Any]]:
        return [r for r in self.records if r["event"] == event]

    def first(self, event: str) -> dict[str, Any] | None:
        return next((r for r in self.records if r["event"] == event), None)


def load_recording(path: Path) -> Recording:
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    if not records or records[0].get("event") != "header":
        raise ValueError(f"{path}: first record must be a header")
    if records[0].get("schema") != SCHEMA:
        raise ValueError(f"{path}: unsupported schema {records[0].get('schema')!r}")
    times = [r["t_s"] for r in records]
    if times != sorted(times):
        raise ValueError(f"{path}: t_s is not non-decreasing")
    return Recording(header=records[0], records=records[1:])
