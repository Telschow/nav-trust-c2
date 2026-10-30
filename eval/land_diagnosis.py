"""What the vehicle was doing when LAND was commanded under a frozen position, and what PX4 did
next (issue 141). Evaluation only.

Issue 81 found that LAND reaches the ground 8 to 12 s after the command but touches down at 2.0
to 28.3 m/s. The recordings had no flight-mode events, so why was not known. These runs record
them (`sim.record_run --log-flight-mode`). Per run:

- mode at the command: the last PX4 flight mode entered at or before the command;
- command to LAND mode: seconds from the command to PX4 entering LAND;
- speed at the command, and speed at LAND mode: horizontal metres per second from the true
  position, over the samples within one second either side of that moment (the vehicle's momentum
  when LAND was sent, and when PX4 actually began to land; a vehicle that has not slowed by then
  is carrying its speed in, which the frozen position alone would not explain);
- speed below 3 m and command to touchdown: as in `eval.frozen_matrix`.

Counts and ranges only, never rates. This says what the recordings show; it does not say why PX4
does it, which needs PX4's own logs.

    python -m eval.land_diagnosis tests/replay/data/experiments/land-diagnosis
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from eval.frozen_matrix import measure_run, range_of, span
from navtrust.recording import Recording, load_recording

SPEED_WINDOW_S = 1.0  # proposal: samples this close to the command give its speed


@dataclass(frozen=True)
class RunState:
    action: str
    survey_speed: float
    delay: float
    mode_at_command: str | None
    command_to_land_mode_s: float | None
    speed_at_command_m_s: float | None
    speed_at_land_mode_m_s: float | None
    touchdown_speed_m_s: float | None
    command_to_touchdown_s: float | None
    has_mode_events: bool


@dataclass(frozen=True)
class Cell:
    action: str
    survey_speed: float
    delay: float
    n: int
    with_mode_events: int
    modes_at_command: tuple[str, ...]
    command_to_land_mode_s: tuple[float, float] | None
    speed_at_command_m_s: tuple[float, float] | None
    speed_at_land_mode_m_s: tuple[float, float] | None
    touchdown_speed_m_s: tuple[float, float] | None


def _speed_at(truth: list[dict[str, Any]], command_s: float) -> float | None:
    near = [r for r in truth if abs(r["t_s"] - command_s) <= SPEED_WINDOW_S]
    if len(near) < 2 or near[-1]["t_s"] <= near[0]["t_s"]:
        return None
    a, b = near[0], near[-1]
    dist = math.hypot(b["east_m"] - a["east_m"], b["north_m"] - a["north_m"])
    return float(dist / (b["t_s"] - a["t_s"]))


def measure(recording: Recording) -> RunState:
    command = recording.first("operator_action")
    if command is None:
        raise ValueError("recording has no operator_action")
    command_s = float(command["t_s"])
    modes = recording.of("flight_mode")
    entered = [m for m in modes if m["t_s"] <= command_s]
    land = next((m for m in modes if m["mode"] == "LAND" and m["t_s"] >= command_s), None)
    flown = measure_run(recording)
    truth = recording.of("truth")
    return RunState(
        action=flown.action,
        survey_speed=flown.speed,
        delay=flown.delay,
        mode_at_command=str(entered[-1]["mode"]) if entered else None,
        command_to_land_mode_s=float(land["t_s"]) - command_s if land else None,
        speed_at_command_m_s=_speed_at(truth, command_s),
        speed_at_land_mode_m_s=_speed_at(recording.of("truth"), float(land["t_s"]))
        if land
        else None,
        touchdown_speed_m_s=flown.touchdown_speed_m_s,
        command_to_touchdown_s=flown.command_to_touchdown_s,
        has_mode_events=bool(modes),
    )


def _range_of(group: list[RunState], field: str) -> tuple[float, float] | None:
    return range_of([v for r in group if (v := getattr(r, field)) is not None])


def summarise(runs: list[RunState]) -> list[Cell]:
    keys = sorted({(r.action, r.survey_speed, r.delay) for r in runs}, key=lambda k: (k[1], k[2]))
    cells = []
    for action, speed, delay in keys:
        group = [r for r in runs if (r.action, r.survey_speed, r.delay) == (action, speed, delay)]
        cells.append(
            Cell(
                action=action,
                survey_speed=speed,
                delay=delay,
                n=len(group),
                with_mode_events=sum(r.has_mode_events for r in group),
                modes_at_command=tuple(
                    sorted({r.mode_at_command for r in group if r.mode_at_command})
                ),
                command_to_land_mode_s=_range_of(group, "command_to_land_mode_s"),
                speed_at_command_m_s=_range_of(group, "speed_at_command_m_s"),
                speed_at_land_mode_m_s=_range_of(group, "speed_at_land_mode_m_s"),
                touchdown_speed_m_s=_range_of(group, "touchdown_speed_m_s"),
            )
        )
    return cells


def _num(value: float | None) -> str:
    return "none" if value is None else f"{value:.1f}"


def table(directory: Path) -> str:
    """Per run, then per cell as counts and ranges."""
    paths = sorted(directory.glob("*.jsonl"))
    runs = [measure(load_recording(p)) for p in paths]
    per_run = [
        "| Recording | Mode at command | Command to LAND mode (s) | Speed at command (m/s) "
        "| Speed at LAND mode (m/s) | Speed below 3 m (m/s) |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for path, r in zip(paths, runs, strict=True):
        per_run.append(
            f"| {path.stem} | {r.mode_at_command or 'not recorded'} "
            f"| {_num(r.command_to_land_mode_s)} | {_num(r.speed_at_command_m_s)} "
            f"| {_num(r.speed_at_land_mode_m_s)} | {_num(r.touchdown_speed_m_s)} |"
        )
    per_cell = [
        "| Action | Speed (m/s) | Delay (s) | Runs | With mode events | Mode at command "
        "| Command to LAND mode (s) | Speed at command (m/s) | Speed at LAND mode (m/s) "
        "| Speed below 3 m (m/s) |",
        "|---|---:|---:|---:|---:|---|---:|---:|---:|---:|",
    ]
    for c in summarise(runs):
        per_cell.append(
            f"| {c.action} | {c.survey_speed:g} | {c.delay:g} | {c.n} | {c.with_mode_events} "
            f"| {', '.join(c.modes_at_command) or 'not recorded'} "
            f"| {span(c.command_to_land_mode_s, 1)} | {span(c.speed_at_command_m_s, 1)} "
            f"| {span(c.speed_at_land_mode_m_s, 1)} | {span(c.touchdown_speed_m_s, 1)} |"
        )
    return "\n".join(per_run) + "\n\n" + "\n".join(per_cell) + "\n"


def main() -> None:
    p = argparse.ArgumentParser(description="LAND under a frozen position, with flight modes")
    p.add_argument("recordings", type=Path)
    print(table(p.parse_args().recordings), end="")


if __name__ == "__main__":
    main()
