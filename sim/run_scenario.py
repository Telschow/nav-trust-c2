"""Record one run of a scenario (scenarios/<name>.yaml) with ground truth.

    python -m sim.run_scenario stuck_position --run 2
    python -m sim.run_scenario --list          # "name runs" per scenario, for scripts

Recordings go to eval/recordings/<name>-<run>.jsonl. Needs a running simulator with one vehicle
and `gz` (so ground truth is recorded); see sim/record_all.sh for the whole set.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from sim.scenario import Scenario, load_all

SCENARIOS = Path("scenarios")
RECORDINGS = Path("eval/recordings")


def record_argv(s: Scenario, run: int, out_dir: Path) -> list[str]:
    """Arguments for sim.record_run.main that fly this scenario."""
    v = s.survey
    argv = [
        "--scenario", s.name,
        "--out", str(out_dir / f"{s.recording_name(run)}.jsonl"),
        "--width", str(v.width_m),
        "--height", str(v.height_m),
        "--spacing", str(v.spacing_m),
        "--altitude", str(v.altitude_m),
        "--speed", str(v.speed_m_s),
        "--max-duration", str(s.max_duration_s),
    ]  # fmt: skip
    if s.fault:
        z = s.fault.zone
        argv += ["--zone", str(z.west), str(z.south), str(z.east), str(z.north)]
        argv += ["--mode", s.fault.mode]
        if s.fault.latch:
            argv.append("--latch-fault")
    if s.link_cut:
        c = s.link_cut
        argv += ["--link-cut-after", c.after, "--link-cut-delay", str(c.delay_s)]
        if c.duration_s is not None:
            argv += ["--link-cut-duration", str(c.duration_s)]
        argv += ["--link-cut-direction", c.direction]
    return argv


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Record one run of a scenario")
    p.add_argument("name", nargs="?")
    p.add_argument("--run", type=int, default=1)
    p.add_argument("--list", action="store_true")
    p.add_argument("--scenarios", type=Path, default=SCENARIOS)
    p.add_argument("--out", type=Path, default=RECORDINGS)
    args = p.parse_args(argv)

    scenarios = load_all(args.scenarios)
    if args.list:
        for s in scenarios:
            print(s.name, s.runs)
        return
    chosen = next((s for s in scenarios if s.name == args.name), None)
    if chosen is None:
        raise SystemExit(f"unknown scenario {args.name!r}; have {[s.name for s in scenarios]}")
    if not 1 <= args.run <= chosen.runs:
        raise SystemExit(f"{chosen.name} has runs 1..{chosen.runs}, not {args.run}")

    from sim import record_run  # imports the simulator stack, so only when recording

    record_run.main(record_argv(chosen, args.run, args.out))


if __name__ == "__main__":
    main()
