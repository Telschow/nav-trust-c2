"""Fleet-level mission completion (M-04) from three-vehicle recordings (sim/record_fleet.py).

Mission completion is the share of the survey area that was actually flown by any vehicle, from
Gazebo ground truth. The same loss is recorded with the operator approving the re-task and with
the operator denying it, so the table shows what the re-task changes, not only a number.

The operator is scripted: the approval delay is a scenario parameter (reported in the table),
not a measured human time. The target is a proposal.

    python -m eval.fleet            writes eval/fleet/results.json and results.md
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path
from typing import Any

from c2.allocator import split_area
from eval.coverage import covered_fraction
from navtrust.recording import load_recording

ROOT = Path(__file__).resolve().parent.parent
RECORDINGS = ROOT / "eval" / "fleet" / "recordings"
OUT = ROOT / "eval" / "fleet"
TARGET = 0.90  # proposal (spec 1.5): at least 90% of the area covered after a single-vehicle loss


def _r4(x: float) -> float:
    return round(x, 4)


def run_metrics(path: Path) -> dict[str, Any]:
    rec = load_recording(path)
    h = rec.header
    area = h["area"]
    swath = float(area["spacing_m"]) / 2  # proposal: half the lane spacing, as in eval/coverage.py
    vehicles: list[str] = h["vehicles"]
    sectors = split_area(area["width_m"], area["height_m"], len(vehicles))
    truth = rec.of("truth")
    audit = [r["row"] for r in rec.of("audit")]
    lost = h["fault"]["vehicle"]
    lost_sector = sectors[vehicles.index(lost)]  # the initial assignment is in vehicle order

    def sector_cover(s: Any) -> float:
        rect = (s.west, s.south, s.east, s.north)
        return _r4(covered_fraction(truth, rect, swath))

    whole = (0.0, 0.0, float(area["width_m"]), float(area["height_m"]))
    created = next(
        (a["payload"]["created_s"] for a in audit if a["kind"] == "recommendation"), None
    )
    decided = next((a["payload"]["decided_s"] for a in audit if a["kind"] == "decision"), None)
    executed = next((a["t_s"] for a in audit if a["kind"] == "command_executed"), None)
    stop = rec.first("recording_stopped")

    # backend latency: the lost vehicle's RED report reaches the hub, the recommendation exists
    reds = [a["t_s"] for a in audit if a["kind"] == "navtrust_change" and a["vehicle_id"] == lost
            and a["payload"]["state"] == "RED"]  # fmt: skip
    recs = [a["t_s"] for a in audit if a["kind"] == "recommendation" and a["vehicle_id"] == lost]
    red_to_rec = None
    if recs:
        before = [t for t in reds if t <= recs[0]]
        red_to_rec = round(recs[0] - max(before), 3) if before else None

    # operator load: recommendations plus decisions per 10 minutes of flight (first to last airborne sample)
    airborne = [t["t_s"] for t in truth if t["alt_m"] >= 5.0]
    flight_s = (max(airborne) - min(airborne)) if airborne else None
    decisions = sum(
        1 for a in audit if a["kind"] == "decision" and a["payload"]["outcome"] != "EXPIRED"
    )
    n_recs = sum(1 for a in audit if a["kind"] == "recommendation")
    return {
        "recording": path.stem,
        "scenario": h["scenario"],
        "swath_half_width_m": swath,
        "operator": h["operator"]["policy"],
        "operator_delay_s": h["operator"]["delay_s"],
        "lost_vehicle": lost,
        "lost_sector": lost_sector.id,
        "area_covered": _r4(covered_fraction(truth, whole, swath)),
        "sector_covered": {s.id: sector_cover(s) for s in sectors},
        "lost_sector_covered": sector_cover(lost_sector),
        "recommendations": n_recs,
        "decisions": decisions,
        "red_to_recommendation_s": red_to_rec,
        "flight_s": None if flight_s is None else round(flight_s, 1),
        "alerts_plus_decisions_per_10_min": None
        if not flight_s
        else round((n_recs + decisions) / flight_s * 600, 2),
        "retask_executed": executed is not None,
        "decision_to_retask_s": None
        if decided is None or executed is None
        else round(executed - decided, 1),
        "alert_to_decision_s": None
        if created is None or decided is None
        else round(decided - created, 1),
        "stopped": None if stop is None else stop["reason"],
    }


def evaluate(recordings: Path = RECORDINGS) -> dict[str, Any]:
    runs = [run_metrics(p) for p in sorted(recordings.glob("*.jsonl"))]
    by: dict[str, list[dict[str, Any]]] = {}
    for m in runs:
        by.setdefault(m["scenario"], []).append(m)
    scenarios = {}
    for name, rs in sorted(by.items()):
        covers = [m["area_covered"] for m in rs]
        scenarios[name] = {
            "operator": rs[0]["operator"],
            "operator_delay_s": rs[0]["operator_delay_s"],
            "runs": len(rs),
            "area_covered_median": _r4(statistics.median(covers)),
            "area_covered_min": min(covers),
            "lost_sector_covered_median": _r4(
                statistics.median(m["lost_sector_covered"] for m in rs)
            ),
            "meets_target": sum(1 for c in covers if c >= TARGET),
            "runs_detail": rs,
        }
    return {"target_proposal": TARGET, "scenarios": scenarios}


def _ms(v: float | None) -> str:
    return "-" if v is None else f"{v * 1000:.0f}"


def _cell(v: float | None) -> str:
    return "-" if v is None else f"{v:.1f}"


def render_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Fleet mission completion",
        "",
        "Generated by `python -m eval.fleet` from the recordings in `eval/fleet/recordings`. Do not",
        "edit by hand: CI recomputes it and fails if it differs.",
        "",
        f"Target (proposal): at least {result['target_proposal']:.0%} of the survey area covered after"
        " the loss of one vehicle.",
        "",
        "| Scenario | Operator (scripted) | Runs | Area covered (median, min) | Lost vehicle's sector covered |"
        " Runs at or above target |",
        "|---|---|---|---|---|---|",
    ]
    for name, s in result["scenarios"].items():
        op = f"{s['operator']}, after {s['operator_delay_s']:g} s"
        lines.append(
            f"| {name} | {op} | {s['runs']} | {s['area_covered_median']:.0%} ({s['area_covered_min']:.0%})"
            f" | {s['lost_sector_covered_median']:.0%} | {s['meets_target']} of {s['runs']} |"
        )
    lines += [
        "",
        "## Per run",
        "",
        "| Recording | Area covered | S1 | S2 | S3 | Lost vehicle | Recommendations | Re-task executed |"
        " RED to recommendation, ms | Alert to decision, s | Decision to re-task, s | Alerts plus decisions per 10 min |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for s in result["scenarios"].values():
        for m in s["runs_detail"]:
            sc = m["sector_covered"]
            lines.append(
                f"| {m['recording']} | {m['area_covered']:.0%} | {sc['S1']:.0%} | {sc['S2']:.0%} |"
                f" {sc['S3']:.0%} | {m['lost_vehicle']} ({m['lost_sector']}) | {m['recommendations']} |"
                f" {'yes' if m['retask_executed'] else 'no'} | {_ms(m['red_to_recommendation_s'])} |"
                f" {_cell(m['alert_to_decision_s'])} | {_cell(m['decision_to_retask_s'])} |"
                f" {_cell(m['alerts_plus_decisions_per_10_min'])} |"
            )
    lines += [
        "",
        "## How to read this",
        "",
        "- **Area covered**: share of the whole survey rectangle within half the lane spacing of any",
        "  vehicle's true track while airborne (Gazebo ground truth, `eval/coverage.py`). The swath is",
        "  a proposal, not a sensor model.",
        "- **Scripted operator**: answers every recommendation after a fixed delay. The delay is a",
        "  parameter of the scenario, not a human response time; the usability sessions measure that.",
        "- **Alert to decision**: from the recommendation to the decision, on the backend's clock.",
        "- **RED to recommendation**: from the backend ingesting the lost vehicle's RED report to the",
        "  recommendation existing, on the backend's clock. It excludes the engine's report interval (the",
        "  engine publishes twice a second, so up to 0.5 s by design, not measured here) and delivery to",
        "  the console. The proposal target is 2 s (C2-02).",
        "- **Alerts plus decisions per 10 min**: recommendations raised plus decisions answered (not",
        "  expired), per 10 minutes from the first to the last airborne sample. The operator is scripted,",
        "  so this counts the system's demands, not a human's effort.",
        "",
        "## Limits",
        "",
        "- One loss pattern (a long GNSS outage that makes PX4 land one vehicle), three vehicles, one",
        "  area, few runs. A result at or above the target is not a guarantee for other patterns.",
        "- Sector completion is tracked by the backend from the vehicles' own reported positions while",
        "  they are trusted; the table is measured against ground truth, not against that tracking.",
        "- Everything is simulation (PX4 SITL in Gazebo).",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    result = evaluate()
    if not result["scenarios"]:
        print("no fleet recordings in", RECORDINGS, file=sys.stderr)
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "results.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    (OUT / "results.md").write_text(render_markdown(result), encoding="utf-8")
    print(f"wrote {OUT / 'results.json'} and {OUT / 'results.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
