"""Evaluate the trust engine on the recordings in eval/recordings and write the results table.

    python -m eval.evaluate           write eval/results.json and eval/results.md
    python -m eval.evaluate --check   exit 1 if they differ from a fresh computation (CI)

Everything is computed from the recordings; nothing is typed in. Recordings are produced by
`make record-all` (simulator needed); evaluation itself needs no simulator.
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

from eval.expectations import check
from eval.freeze import engine_fingerprint
from eval.metrics import EvalConfig, RunMetrics, as_dict, run_metrics
from navtrust.calibration import GREEN_BOUND
from navtrust.recording import load_recording
from sim.scenario import Scenario, load_all

ROOT = Path(__file__).resolve().parent.parent
RECORDINGS = ROOT / "eval" / "recordings"
SCENARIOS = ROOT / "scenarios"
OUT = ROOT / "eval"
HELDOUT_RECORDINGS = "eval/heldout/recordings"
HELDOUT_SCENARIOS = "scenarios/heldout"
HELDOUT_OUT = "eval/heldout"


def _r(x: float | None) -> float | None:
    return None if x is None else round(x, 3)


def _r4(x: float) -> float:
    return round(x, 4)


def aggregate(scenario: Scenario, runs: list[RunMetrics]) -> dict[str, Any]:
    ttds = [m.ttd_s for m in runs if m.ttd_s is not None]
    faulted = [m for m in runs if m.detected is not None]
    hours = sum(m.duration_s for m in runs) / 3600.0
    false_eps = sum(m.false_alert_episodes for m in runs)
    mis = [m.misleading_s for m in runs if m.misleading_s is not None]
    greens = [m.max_error_green_m for m in runs if m.max_error_green_m is not None]
    areas = [m.area_covered for m in runs if m.area_covered is not None]
    at_det = [m.error_at_detection_m for m in runs if m.error_at_detection_m is not None]
    return {
        "class": scenario.scenario_class,
        "runs_expected": scenario.runs,
        "runs": len(runs),
        "detected": None if not faulted else sum(1 for m in faulted if m.detected),
        "faulted_runs": len(faulted),
        "ttd_median_s": _r(statistics.median(ttds)) if ttds else None,
        "ttd_min_s": _r(min(ttds)) if ttds else None,
        "ttd_max_s": _r(max(ttds)) if ttds else None,
        "false_alert_episodes": false_eps,
        "flight_hours": _r(hours),
        "false_alerts_per_hour": _r(false_eps / hours) if hours > 0 else None,
        "green_reports": sum(m.green_reports for m in runs),
        "bound_coverage": _r4(
            sum(m.green_within_bound for m in runs) / sum(m.green_reports for m in runs)
        )
        if sum(m.green_reports for m in runs)
        else None,
        "misleading_s_mean": _r(statistics.mean(mis)) if mis else None,
        "misleading_s_max": _r(max(mis)) if mis else None,
        "max_error_while_green_m": _r(max(greens)) if greens else None,
        "error_at_detection_median_m": _r(statistics.median(at_det)) if at_det else None,
        "error_at_detection_max_m": _r(max(at_det)) if at_det else None,
        "area_covered_median": _r4(statistics.median(areas)) if areas else None,
        "missions_finished": sum(1 for m in runs if m.mission_finished),
        "interruptions_mean": _r(statistics.mean(m.interruptions for m in runs)) if runs else None,
    }


def evaluate(recordings: Path, scenarios: Path, cfg: EvalConfig) -> dict[str, Any]:
    by_scenario: dict[str, list[RunMetrics]] = defaultdict(list)
    for path in sorted(recordings.glob("*.jsonl")):
        rec = load_recording(path)
        by_scenario[rec.header["scenario"]].append(run_metrics(path.stem, rec, cfg))
    result: dict[str, Any] = {
        "engine_sha256": engine_fingerprint(),
        "config": {
            "step_s": cfg.step_s,
            "misleading_error_m": cfg.misleading_error_m,
            "window_margin_s": cfg.window_margin_s,
        },
        "scenarios": {},
    }
    for s in load_all(scenarios):
        runs = by_scenario.get(s.name, [])
        result["scenarios"][s.name] = {
            "aggregate": aggregate(s, runs),
            "runs": [as_dict(m) for m in runs],
        }
    hours = sum(d["aggregate"]["flight_hours"] or 0.0 for d in result["scenarios"].values())
    episodes_total = sum(
        d["aggregate"]["false_alert_episodes"] for d in result["scenarios"].values()
    )
    reports_total = sum(d["aggregate"]["green_reports"] for d in result["scenarios"].values())
    within_total = sum(
        m["green_within_bound"] for d in result["scenarios"].values() for m in d["runs"]
    )
    result["overall"] = {
        "green_reports": reports_total,
        "bound_coverage": _r4(within_total / reports_total) if reports_total else None,
        "flight_hours": _r(hours),
        "false_alert_episodes": episodes_total,
        # with no events at all, the 95% upper bound on a Poisson rate is about 3 / exposure
        "false_alert_rate_upper_95_per_hour": _r(3.0 / hours)
        if episodes_total == 0 and hours > 0
        else None,
    }
    return result


def _cell(v: object, fmt: str = "{}") -> str:
    return "-" if v is None else fmt.format(v)


def render_markdown(
    result: dict[str, Any],
    title: str = "Evaluation results",
    where: str = "eval/recordings",
    expectations: bool = False,
) -> str:
    cfg = result["config"]
    lines = [
        f"# {title}",
        "",
        f"Generated by `python -m eval.evaluate` from the recordings in `{where}`. Do not edit",
        "by hand: CI recomputes it and fails if it differs.",
        "",
        f"Engine fingerprint (sha256 of the trust engine and recommender code): `{result['engine_sha256']}`",
        "",
        "| Scenario | Runs | Detected | Time to detect, s (median, min to max) | False alerts per flight hour |"
        f" GREEN while more than {cfg['misleading_error_m']:g} m off, s (mean, max) |"
        " Error at alert, m (median, max) | Displayed bound held, GREEN reports | Missions finished |"
        " Area covered (median) | Interruptions per run |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for name, data in result["scenarios"].items():
        a = data["aggregate"]
        det = "-" if a["detected"] is None else f"{a['detected']} of {a['faulted_runs']}"
        ttd = (
            "-"
            if a["ttd_median_s"] is None
            else f"{a['ttd_median_s']:.1f} ({a['ttd_min_s']:.1f} to {a['ttd_max_s']:.1f})"
        )
        mis = (
            "-"
            if a["misleading_s_mean"] is None
            else f"{a['misleading_s_mean']:.1f} ({a['misleading_s_max']:.1f})"
        )
        err = (
            "-"
            if a["error_at_detection_median_m"] is None
            else f"{a['error_at_detection_median_m']:.1f} ({a['error_at_detection_max_m']:.1f})"
        )
        runs = (
            f"{a['runs']}"
            if a["runs"] == a["runs_expected"]
            else f"{a['runs']} of {a['runs_expected']}"
        )
        lines.append(
            f"| {name} | {runs} | {det} | {ttd} | {_cell(a['false_alerts_per_hour'], '{:.2f}')}"
            f" ({a['false_alert_episodes']} in {_cell(a['flight_hours'], '{:.2f}')} h) | {mis} | {err}"
            f" | {_cell(a['bound_coverage'], '{:.1%}')} ({a['green_reports']})"
            f" | {a['missions_finished']} of {a['runs']} | {_cell(a['area_covered_median'], '{:.0%}')}"
            f" | {_cell(a['interruptions_mean'], '{:.1f}')} |"
        )
    lines += [
        "",
        "## Per run",
        "",
        "| Recording | Started, s | Fault at, s | TTD, s | Worst state | RED after, s | False alerts |"
        " GREEN while off, s | Max error while GREEN, m | Error at alert, m | Waypoints reached | Area covered | Landed |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for data in result["scenarios"].values():
        for m in data["runs"]:
            reached = "-" if m["waypoints_reached"] is None else f"{m['waypoints_reached']:.0%}"
            lines.append(
                f"| {m['recording']} | {m['started_s']:.1f} | {_cell(m['fault_start_s'], '{:.1f}')} |"
                f" {_cell(m['ttd_s'], '{:.1f}')} | {m['worst_state']} | {_cell(m['red_after_fault_s'], '{:.1f}')} |"
                f" {m['false_alert_episodes']} |"
                f" {_cell(m['misleading_s'], '{:.1f}')} | {_cell(m['max_error_green_m'], '{:.1f}')} |"
                f" {_cell(m['error_at_detection_m'], '{:.1f}')} | {reached} | {_cell(m['area_covered'], '{:.0%}')} | {'yes' if m['landed'] else 'no'} |"
            )
    if expectations:
        lines += [
            "",
            "## Pre-declared expectations",
            "",
            "Written before any held-out run was recorded (`eval/expectations.py`, explained in",
            "`docs/validation/heldout-protocol.md`). Not met means not met: the engine was not retuned.",
            "",
            "| | Expectation | Result | Detail |",
            "|---|---|---|---|",
        ]
        lines += [
            f"| {o.id} | {o.statement} | {'met' if o.met else 'NOT MET'} | {o.detail} |"
            for o in check(result)
        ]
    overall = result["overall"]
    if overall["bound_coverage"] is not None:
        lines += [
            "",
            f"The displayed bound held in {overall['bound_coverage']:.2%} of {overall['green_reports']} GREEN reports "
            f"over all runs (NT-03 asks for at least 95%; the claim is {GREEN_BOUND.coverage:.0%}, bound "
            f"{GREEN_BOUND.bound_m:g} m). So {1 - overall['bound_coverage']:.2%} of GREEN reports were "
            "misleading in the spec's sense (true error above the displayed bound).",
        ]
    if overall["false_alert_rate_upper_95_per_hour"] is not None:
        lines += [
            "",
            f"No false alert in {overall['flight_hours']:.2f} flight hours over all runs. That does not mean the",
            "rate is zero: with no events the 95% upper bound on the rate is about "
            f"{overall['false_alert_rate_upper_95_per_hour']:.1f} per hour (3 divided by the exposure).",
        ]
    lines += [
        "",
        "## How to read this",
        "",
        "- **Time to detect**: from the moment the fault starts to the first report that is not GREEN.",
        "  It includes the receiver and telemetry delay between the injection and the fix changing.",
        "- **False alerts**: non-GREEN episodes that start outside every fault window, per hour of",
        f"  flight after the engine's first GREEN. A window ends {cfg['window_margin_s']:g} s after the fault does.",
        f"- **GREEN while more than {cfg['misleading_error_m']:g} m off**: seconds in which the engine said GREEN while the",
        "  true horizontal error of the vehicle's own position exceeded the threshold (ground truth from",
        "  Gazebo). The threshold is a proposal.",
        "- **Error at alert**: true horizontal error at the first non-GREEN report after the fault began.",
        "  A small value is not a mistake: for a frozen position the estimate keeps dead-reckoning for a",
        "  few seconds and only then follows the frozen fix, so the alert comes before the error grows.",
        "- **Displayed bound held**: the share of GREEN reports in which the true error was within the",
        "  bound the console displays (navtrust/calibration.py). The estimator's own accuracy figure",
        "  (about 0.15 m) was not a valid bound; even nominal flights are a few metres off at survey",
        "  speed, and a time shift does not explain it.",
        "- **Area covered**: share of the survey rectangle within half the lane spacing of the vehicle's\n  true track while airborne (ground truth; `eval/coverage.py`). The swath is a proposal, not a\n  sensor model.\n- **Interruptions per run**: recommendations the recommender raises, assuming two other healthy",
        "  vehicles; recommendations are not repeated.",
        "",
        "## Limits",
        "",
        "- Few runs per scenario in one simulator (PX4 SITL, Gazebo) with PX4's own GPS failure model.",
        "  Medians and maxima over 2 to 4 runs are not statistics; a clean row is not a guarantee.",
        "- The engine and its thresholds were developed on earlier recordings of the same kind, so this",
        "  is not independent validation.",
        "- Operators are not simulated: no scenario includes a decision, so mission completion shows",
        "  what the vehicle does unaided, not what the console achieves.",
        "- All thresholds (detector and evaluation) are proposals.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Evaluate the trust engine on the recordings")
    p.add_argument("--recordings", type=Path, default=RECORDINGS)
    p.add_argument("--scenarios", type=Path, default=SCENARIOS)
    p.add_argument("--out", type=Path, default=OUT)
    p.add_argument("--check", action="store_true", help="compare with the committed files")
    p.add_argument(
        "--heldout",
        action="store_true",
        help="the held-out set: scenarios/heldout, eval/heldout/recordings, eval/heldout/results.*",
    )
    args = p.parse_args(argv)
    title, where = "Evaluation results", "eval/recordings"
    if args.heldout:
        args.recordings = ROOT / HELDOUT_RECORDINGS
        args.scenarios = ROOT / HELDOUT_SCENARIOS
        args.out = ROOT / HELDOUT_OUT
        title, where = "Held-out validation results", HELDOUT_RECORDINGS

    result = evaluate(args.recordings, args.scenarios, EvalConfig())
    json_text = json.dumps(result, indent=2) + "\n"
    md_text = render_markdown(result, title, where, expectations=args.heldout)
    json_path, md_path = args.out / "results.json", args.out / "results.md"
    if args.check:
        same = (
            json_path.exists()
            and md_path.exists()
            and json_path.read_text(encoding="utf-8") == json_text
            and md_path.read_text(encoding="utf-8") == md_text
        )
        print("results are up to date" if same else "results differ: run `make eval` and commit")
        return 0 if same else 1
    json_path.write_text(json_text, encoding="utf-8")
    md_path.write_text(md_text, encoding="utf-8")
    print(f"wrote {json_path} and {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
