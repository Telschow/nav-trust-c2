"""Builds story.json for the "believed vs real" clip (issue 184) from two recorded runs.

The runs are the pair behind ADR 0003: the same frozen-position fault with no action, and with a
LAND approved 15 s after the fault. Every number the clip shows comes from here, not from the
scene code. Ground truth is evaluation-only data; the clip is a replay of recordings and says so.

    python tools/story/build_story.py [out.json]
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXPERIMENTS = ROOT / "tests/replay/data/experiments"
RUNS = {"none": "stuck-action-none.jsonl", "land": "stuck-action-land.jsonl"}
STEP_S = 0.5  # sampling of the tracks, simulation seconds
METRES_PER_DEG_LAT = 111_320.0


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def first(events: list[dict], name: str) -> dict | None:
    return next((e for e in events if e["event"] == name), None)


def track(events: list[dict], fault_t: float, end_t: float) -> dict:
    """Truth and reported tracks in metres east/north of home, time relative to the fault."""
    home = first(events, "home")
    assert home is not None
    lat0, lon0 = home["lat_deg"], home["lon_deg"]
    cos_lat = math.cos(math.radians(lat0))
    truth = [e for e in events if e["event"] == "truth"]
    reported = [e for e in events if e["event"] == "position"]

    def at(series: list[dict], t: float) -> dict:
        return min(series, key=lambda e: abs(e["t_s"] - t))

    rows = []
    n = int((end_t - (-8.0)) / STEP_S) + 1
    for i in range(n):
        rel = -8.0 + i * STEP_S
        t = fault_t + rel
        a, p = at(truth, t), at(reported, t)
        rows.append(
            {
                "t": round(rel, 2),
                "truth": [round(a["east_m"], 1), round(a["north_m"], 1), round(a["alt_m"], 1)],
                "reported": [
                    round((p["lon_deg"] - lon0) * METRES_PER_DEG_LAT * cos_lat, 1),
                    round((p["lat_deg"] - lat0) * METRES_PER_DEG_LAT, 1),
                ],
            }
        )
    return {"rows": rows}


def build() -> dict:
    out: dict = {"runs": {}}
    for key, name in RUNS.items():
        path = EXPERIMENTS / name
        events = load(path)
        fault = first(events, "gnss_enter")
        assert fault is not None
        action = first(events, "operator_action")
        truth = [e for e in events if e["event"] == "truth"]
        end_t = truth[-1]["t_s"]
        t = track(events, fault["t_s"], end_t - fault["t_s"])
        # farthest point from the start, as the ADR measures it
        far = max(math.hypot(e["east_m"], e["north_m"]) for e in truth)
        touch = next((e for e in truth if e["t_s"] > fault["t_s"] and e["alt_m"] < 0.5), None)
        t["farthest_from_start_m"] = round(far)
        t["fault_t_s"] = fault["t_s"]
        t["approved_rel_s"] = round(action["t_s"] - fault["t_s"], 1) if action else None
        t["touchdown_rel_s"] = round(touch["t_s"] - fault["t_s"], 1) if touch else None
        t["end_rel_s"] = round(end_t - fault["t_s"], 1)
        t["source"] = f"tests/replay/data/experiments/{name}"
        t["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        out["runs"][key] = t
    return out


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("src") / "story.json"
    out.write_text(json.dumps(build(), separators=(",", ":")))
    runs = json.loads(out.read_text())["runs"]
    for key, r in runs.items():
        print(key, f"{r['farthest_from_start_m']} m", "approved", r["approved_rel_s"])


if __name__ == "__main__":
    main()
