"""Recompute the bound calibration from the recordings (navtrust/calibration.py holds the result).

    python -m eval.calibrate                 print errors and coverage on both sets

The numbers in navtrust/calibration.py are checked against this by tests/test_calibration.py.
"""

from __future__ import annotations

from pathlib import Path

from eval.metrics import EvalConfig, green_samples, position_errors
from navtrust.engine import TrustEngine
from navtrust.recording import load_recording
from navtrust.replay import replay_engine
from navtrust.types import TrustState

ROOT = Path(__file__).resolve().parent.parent
DEVELOPMENT = ROOT / "eval" / "recordings"
HELDOUT = ROOT / "eval" / "heldout" / "recordings"


def green_errors(directory: Path, cfg: EvalConfig | None = None) -> list[float]:
    """True horizontal error of every GREEN report after startup, over all recordings."""
    cfg = cfg or EvalConfig()
    out: list[float] = []
    for path in sorted(directory.glob("*.jsonl")):
        rec = load_recording(path)
        reports = replay_engine(rec, TrustEngine("uav1"), cfg.step_s)
        started = next((r.stamp_s for r in reports if r.state is TrustState.GREEN), None)
        if started is not None:
            out += [e for e, _ in green_samples(reports, started, position_errors(rec))]
    return out


def coverage(errors: list[float], bound_m: float) -> float:
    return sum(1 for e in errors if e <= bound_m) / len(errors)


def percentile(errors: list[float], p: float) -> float:
    s = sorted(errors)
    return s[min(len(s) - 1, int(p * len(s)))]


def main() -> None:
    for name, directory in (("development", DEVELOPMENT), ("held-out", HELDOUT)):
        if not any(directory.glob("*.jsonl")):
            print(f"{name}: no recordings")
            continue
        e = green_errors(directory)
        print(
            f"{name}: {len(e)} GREEN reports; error median {percentile(e, 0.5):.2f} m, "
            f"95th {percentile(e, 0.95):.2f}, 99th {percentile(e, 0.99):.2f}, max {max(e):.2f}"
        )
        for b in (2.5, 3.0, 3.5):
            print(f"    within {b} m: {coverage(e, b):.2%}")


if __name__ == "__main__":
    main()
