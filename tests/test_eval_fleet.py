"""The fleet results table must be what the recordings produce (`python -m eval.fleet`), and the
fleet metrics must behave on a small synthetic run."""

import json
from pathlib import Path

import pytest

from eval.fleet import OUT, RECORDINGS, evaluate, render_markdown, run_metrics


def synthetic(path: Path, tracks: dict[str, list[tuple[float, float]]]) -> Path:
    rows: list[dict[str, object]] = [
        {
            "t_s": 0.0,
            "event": "header",
            "schema": 1,
            "scenario": "synthetic",
            "area": {"width_m": 600.0, "height_m": 300.0, "spacing_m": 100.0},
            "vehicles": ["uav1", "uav2", "uav3"],
            "fault": {"vehicle": "uav2", "mode": "off", "zone": [0, 0, 1, 1]},
            "operator": {"policy": "deny", "delay_s": 15.0},
        },
    ]
    for v, pts in tracks.items():
        for i, (e, n) in enumerate(pts):
            rows.append(
                {
                    "t_s": float(i),
                    "event": "truth",
                    "vehicle": v,
                    "east_m": e,
                    "north_m": n,
                    "alt_m": 30.0,
                }  # fmt: skip
            )
    rows.append({"t_s": 1000.0, "event": "recording_stopped", "reason": "all_landed"})
    rows[1:] = sorted(rows[1:], key=lambda r: float(str(r["t_s"])))
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return path


def lane(north: float) -> list[tuple[float, float]]:
    return [(float(e), north) for e in range(0, 601, 5)]


def test_a_lost_sector_left_unflown_lowers_area_covered(tmp_path: Path) -> None:
    # uav1 flies S1's two lanes, uav3 flies S3's; nobody flies S2's lanes at 100 and 200 except
    # that the lane at 100 is also S1's north edge and the lane at 200 is S3's south edge
    p = synthetic(
        tmp_path / "x.jsonl", {"uav1": lane(0.0) + lane(100.0), "uav3": lane(200.0) + lane(300.0)}
    )
    m = run_metrics(p)
    assert m["area_covered"] == pytest.approx(
        1.0, abs=0.01
    )  # the swath of the shared lanes covers S2
    p2 = synthetic(tmp_path / "y.jsonl", {"uav1": lane(0.0), "uav3": lane(300.0)})
    m2 = run_metrics(p2)
    assert m2["sector_covered"]["S2"] == 0.0 and m2["area_covered"] < 0.8
    assert m2["retask_executed"] is False and m2["alert_to_decision_s"] is None


def test_committed_fleet_table_matches_the_recordings() -> None:
    if not any(RECORDINGS.glob("*.jsonl")):
        pytest.skip("no fleet recordings yet")
    result = evaluate()
    assert (OUT / "results.json").read_text(encoding="utf-8") == json.dumps(result, indent=2) + "\n"
    assert (OUT / "results.md").read_text(encoding="utf-8") == render_markdown(result)


def test_every_committed_run_is_a_complete_flight() -> None:
    """A run cut off by the time limit would understate what the fleet covers."""
    stopped = {m["recording"]: m["stopped"] for m in
               (run_metrics(p) for p in sorted(RECORDINGS.glob("*.jsonl")))}  # fmt: skip
    assert all(v == "all_landed" for v in stopped.values()), stopped
