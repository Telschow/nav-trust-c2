"""Per-run metrics from one recording. Pure Python; every number is computed from the data.

Definitions (all thresholds are proposals, see EvalConfig):

- started: the first report the engine makes as GREEN. Before it the engine has seen no data, so
  nothing before it counts as an alert or as misleading trust.
- fault window: from the first `gnss_enter` to the matching `gnss_exit` plus a margin, or to the
  end of the run for a fault that never clears. An alert episode that begins inside a window is a
  true alert; one that begins outside every window is a false alert.
- time to detect (TTD): fault start to the first report that is not GREEN.
- misleading trust: seconds in which the engine reported GREEN while the true horizontal error
  of the estimated position exceeded `misleading_error_m`. Needs ground truth.
- error at detection: true horizontal error at the first non-GREEN report after the fault began.
- interruptions: recommendations the recommender raises over the run, with two other vehicles
  assumed GREEN. Recommendations are not repeated, so this counts episodes, not nagging.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from c2.allocator import assign, split_area
from c2.fleet import FleetState
from c2.recommender import Recommender
from navtrust.engine import TrustEngine
from navtrust.recording import Recording
from navtrust.replay import replay_engine
from navtrust.types import NavTrust, TrustState
from sim.survey import GeoPoint, geo_to_local


@dataclass(frozen=True)
class EvalConfig:
    step_s: float = 0.5
    misleading_error_m: float = 10.0  # proposal
    window_margin_s: float = 5.0  # proposal: how long after a fault ends an alert still counts


@dataclass(frozen=True)
class RunMetrics:
    recording: str
    started_s: float
    duration_s: float  # from the first GREEN to the end of the recording
    fault_start_s: float | None
    detected: bool | None  # None for a run without a fault
    ttd_s: float | None
    false_alert_episodes: int
    false_alert_s: float
    misleading_s: float | None  # None without ground truth
    max_error_green_m: float | None
    error_at_detection_m: float | None
    mission_finished: bool
    waypoints_reached: float | None  # fraction of the mission's waypoints
    landed: bool
    interruptions: int


def position_errors(rec: Recording) -> list[tuple[float, float]]:
    """(time, true horizontal error in metres) at each position estimate, empty without truth.

    The true position is interpolated linearly to the estimate's time. Matching the nearest
    sample instead leaves up to half a sample interval of timing error, about 5 m at 10 m/s,
    which would look like vehicle error. The estimate is the vehicle's own reported position in
    the frame of its home, which is the world origin for vehicle 1 (see sim/ground_truth.py)."""
    truth, positions, home = rec.of("truth"), rec.of("position"), rec.first("home")
    if len(truth) < 2 or not positions or home is None:
        return []
    origin = GeoPoint(home["lat_deg"], home["lon_deg"])
    out: list[tuple[float, float]] = []
    j = 0
    for p in positions:
        t = p["t_s"]
        while j + 1 < len(truth) and truth[j + 1]["t_s"] <= t:
            j += 1
        a = truth[j]
        b = truth[j + 1] if j + 1 < len(truth) else None
        if a["t_s"] > t:
            continue  # before the first truth sample
        if a["t_s"] == t:
            east, north = a["east_m"], a["north_m"]
        elif b is None:
            continue  # after the last truth sample: holding the last position would add error
        else:
            if b["t_s"] - a["t_s"] > 1.0:
                continue  # a gap in the truth: do not invent a position across it
            f = (t - a["t_s"]) / (b["t_s"] - a["t_s"])
            east = a["east_m"] + f * (b["east_m"] - a["east_m"])
            north = a["north_m"] + f * (b["north_m"] - a["north_m"])
        est = geo_to_local(origin, GeoPoint(p["lat_deg"], p["lon_deg"]))
        out.append((t, math.hypot(est.east_m - east, est.north_m - north)))
    return out


def error_at(errors: list[tuple[float, float]], t_s: float) -> float | None:
    if not errors:
        return None
    t, e = min(errors, key=lambda x: abs(x[0] - t_s))
    return e if abs(t - t_s) <= 1.0 else None


def fault_windows(rec: Recording, end_s: float, margin_s: float) -> list[tuple[float, float]]:
    enters = [e["t_s"] for e in rec.of("gnss_enter")]
    exits = [e["t_s"] for e in rec.of("gnss_exit")]
    windows = []
    for i, start in enumerate(enters):
        stop = exits[i] + margin_s if i < len(exits) else end_s
        windows.append((start, stop))
    return windows


def episodes(reports: list[NavTrust], started_s: float, step_s: float) -> list[tuple[float, float]]:
    """(start, duration) of each run of non-GREEN reports after startup."""
    out: list[tuple[float, float]] = []
    current: float | None = None
    for r in reports:
        if r.stamp_s < started_s:
            continue
        bad = r.state is not TrustState.GREEN
        if bad and current is None:
            current = r.stamp_s
        elif not bad and current is not None:
            out.append((current, r.stamp_s - current))
            current = None
    if current is not None:
        out.append((current, reports[-1].stamp_s + step_s - current))
    return out


def count_interruptions(reports: list[NavTrust]) -> int:
    now = [0.0]
    recommender = Recommender(lambda: now[0])
    fleet = FleetState(
        assign(split_area(900.0, 900.0, 3), ["uav1", "uav2", "uav3"]),
        positions={"uav1": (0.0, 0.0), "uav2": (0.0, 5.0), "uav3": (0.0, 10.0)},
    )
    for v in ("uav2", "uav3"):
        recommender.observe(NavTrust(v, 0.0, TrustState.GREEN, None, 0.15, 1.0), fleet)
    total = 0
    for r in reports:
        now[0] = r.stamp_s
        total += len(recommender.observe(r, fleet))
    return total


def run_metrics(name: str, rec: Recording, cfg: EvalConfig) -> RunMetrics:
    reports = replay_engine(rec, TrustEngine("uav1"), cfg.step_s)
    end_s = rec.records[-1]["t_s"]
    started = next((r.stamp_s for r in reports if r.state is TrustState.GREEN), end_s)
    windows = fault_windows(rec, end_s, cfg.window_margin_s)
    fault_start = windows[0][0] if windows else None

    ttd: float | None = None
    if fault_start is not None:
        first = next(
            (
                r.stamp_s
                for r in reports
                if r.stamp_s >= fault_start and r.state is not TrustState.GREEN
            ),
            None,
        )
        ttd = None if first is None else first - fault_start

    eps = episodes(reports, started, cfg.step_s)
    false_eps = [(s, d) for s, d in eps if not any(a <= s <= b for a, b in windows)]

    errors = position_errors(rec)
    misleading: float | None = None
    max_green: float | None = None
    if errors:
        misleading = 0.0
        max_green = 0.0
        for r in reports:
            if r.stamp_s < started or r.state is not TrustState.GREEN:
                continue
            e = error_at(errors, r.stamp_s)
            if e is None:
                continue
            max_green = max(max_green, e)
            if e > cfg.misleading_error_m:
                misleading += cfg.step_s
    err_at_detection = (
        error_at(errors, fault_start + ttd) if fault_start is not None and ttd is not None else None
    )

    progress = rec.of("mission_progress")
    reached = None
    if progress and progress[-1]["total"]:
        reached = progress[-1]["current"] / progress[-1]["total"]

    return RunMetrics(
        recording=name,
        started_s=started,
        duration_s=end_s - started,
        fault_start_s=fault_start,
        detected=None if fault_start is None else ttd is not None,
        ttd_s=ttd,
        false_alert_episodes=len(false_eps),
        false_alert_s=sum(d for _, d in false_eps),
        misleading_s=misleading,
        max_error_green_m=max_green,
        error_at_detection_m=err_at_detection,
        mission_finished=rec.first("mission_finished") is not None,
        waypoints_reached=reached,
        landed=rec.first("landed") is not None,
        interruptions=count_interruptions(reports),
    )


def as_dict(m: RunMetrics) -> dict[str, Any]:
    return {k: (round(v, 3) if isinstance(v, float) else v) for k, v in m.__dict__.items()}
