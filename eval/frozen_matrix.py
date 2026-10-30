"""The frozen-position experiment of ADR 0003 repeated over actions, cruise speeds and operator
delays (issue 81), summarised from ground truth. Evaluation only.

Per cell (action, cruise speed, operator delay) it reports counts and ranges, never rates: how
many runs there were, how many reached the ground, how many did so in a controlled way, and the
spread of the farthest distance, the time from the command to touchdown and the horizontal speed
at touchdown. Definitions (thresholds are proposals):

- landed: the vehicle reached the ground (`TOUCHDOWN_M`) before the recording ended.
- controlled: landed, with a horizontal speed below 3 m altitude of at most
  `CONTROLLED_SPEED_M_S`. ADR 0003's LAND run was 2.9 m/s; its HOLD and RTL runs were 31.7 and
  24.6 m/s.
- the speed is the mean over the window from 3 m altitude to touchdown (`eval.touchdown_state`).

    python -m eval.frozen_matrix tests/replay/data/experiments/matrix
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from eval.touchdown_state import _horizontal, measure_touchdown
from navtrust.recording import Recording, load_recording

CONTROLLED_SPEED_M_S = 5.0  # proposal
TOUCHDOWN_M = 0.5  # as eval.blind_land


@dataclass(frozen=True)
class Run:
    action: str
    speed: float
    delay: float
    farthest_m: float
    landed: bool
    controlled: bool
    command_to_touchdown_s: float | None
    touchdown_speed_m_s: float | None


@dataclass(frozen=True)
class Cell:
    action: str
    speed: float | None  # None: all speeds
    delay: float | None  # None: all delays
    n: int
    landed: int
    controlled: int
    farthest_m: tuple[float, float]
    command_to_touchdown_s: tuple[float, float] | None
    touchdown_speed_m_s: tuple[float, float] | None


def measure_run(recording: Recording) -> Run:
    header = recording.header
    operator = header.get("operator_action")
    action = operator["action"] if operator else "none"
    truth = recording.of("truth")
    command = recording.first("operator_action")
    state = measure_touchdown(recording)
    down = next(
        (
            r["t_s"]
            for r in truth
            if state is not None
            and r["alt_m"] <= TOUCHDOWN_M
            and r["t_s"] > truth[0]["t_s"]
            and r["t_s"] >= _airborne_after(truth)
        ),
        None,
    )
    speed = state.speed_m_s if state is not None else None
    landed = state is not None and down is not None
    return Run(
        action=action,
        speed=float(header["survey"]["speed_m_s"]),
        delay=float(operator["delay_s"]) if operator else 0.0,
        farthest_m=max(_horizontal(truth[0], r) for r in truth),
        landed=landed,
        controlled=landed and speed is not None and speed <= CONTROLLED_SPEED_M_S,
        command_to_touchdown_s=down - command["t_s"] if landed and command and down else None,
        touchdown_speed_m_s=speed if landed else None,
    )


def _airborne_after(truth: list[dict[str, float]]) -> float:
    """Time of the first sample well above the ground, so ground samples before takeoff do not
    count as a touchdown."""
    return next((r["t_s"] for r in truth if r["alt_m"] > 3.0), float("inf"))


def _range(values: list[float]) -> tuple[float, float] | None:
    return (min(values), max(values)) if values else None


def summarise(runs: list[Run]) -> list[Cell]:
    order = {"none": 0, "land": 1, "hold": 2, "rtl": 3}
    keys = sorted(
        {(r.action, r.speed, r.delay) for r in runs}, key=lambda k: (order.get(k[0], 9), k[1], k[2])
    )
    cells = []
    for action, speed, delay in keys:
        group = [r for r in runs if (r.action, r.speed, r.delay) == (action, speed, delay)]
        farthest = _range([r.farthest_m for r in group])
        assert farthest is not None
        cells.append(
            Cell(
                action,
                speed,
                delay,
                len(group),
                sum(r.landed for r in group),
                sum(r.controlled for r in group),
                farthest,
                _range(
                    [
                        r.command_to_touchdown_s
                        for r in group
                        if r.command_to_touchdown_s is not None
                    ]
                ),
                _range([r.touchdown_speed_m_s for r in group if r.touchdown_speed_m_s is not None]),
            )  # fmt: skip
        )
    return cells


def by_action(runs: list[Run]) -> list[Cell]:
    """One row per action over every speed and delay."""
    cells = []
    for action in ("none", "land", "hold", "rtl"):
        group = [r for r in runs if r.action == action]
        if not group:
            continue
        farthest = _range([r.farthest_m for r in group])
        assert farthest is not None
        cells.append(
            Cell(
                action,
                None,
                None,
                len(group),
                sum(r.landed for r in group),
                sum(r.controlled for r in group),
                farthest,
                _range(
                    [
                        r.command_to_touchdown_s
                        for r in group
                        if r.command_to_touchdown_s is not None
                    ]
                ),
                _range([r.touchdown_speed_m_s for r in group if r.touchdown_speed_m_s is not None]),
            )  # fmt: skip
        )
    return cells


def _span(r: tuple[float, float] | None, digits: int = 0) -> str:
    if r is None:
        return "none"
    lo, hi = (f"{v:.{digits}f}" for v in r)
    return lo if lo == hi else f"{lo} to {hi}"


def _rows(cells: list[Cell]) -> list[str]:
    rows = [
        "| Action | Speed (m/s) | Delay (s) | Runs | Landed | Controlled "
        "| Farthest from start (m) | Command to touchdown (s) | Speed below 3 m (m/s) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for c in cells:
        speed = "all" if c.speed is None else f"{c.speed:g}"
        delay = "all" if c.delay is None else f"{c.delay:g}"
        rows.append(
            f"| {c.action} | {speed} | {delay} | {c.n} | {c.landed} | {c.controlled} "
            f"| {_span(c.farthest_m)} | {_span(c.command_to_touchdown_s)} "
            f"| {_span(c.touchdown_speed_m_s, 1)} |"
        )
    return rows


def table(directory: Path) -> str:
    """The per-action rows, then one row per cell, as two tables."""
    runs = [measure_run(load_recording(p)) for p in sorted(directory.glob("*.jsonl"))]
    return "\n".join(_rows(by_action(runs))) + "\n\n" + "\n".join(_rows(summarise(runs))) + "\n"


def main() -> None:
    p = argparse.ArgumentParser(description="Frozen-position matrix summary (issue 81)")
    p.add_argument("recordings", type=Path)
    print(table(p.parse_args().recordings), end="")


if __name__ == "__main__":
    main()
