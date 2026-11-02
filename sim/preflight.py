"""Is the machine quiet enough to record? (issue 176)

A recording started while another container used about 17 cores produced runs with no ground
truth and a stuck PX4, and cost hours: the simulator's clock falls out of step with the wall clock
and Gazebo's stream goes quiet. Every recording script sources sim/sim_lock.sh, which runs this
before it touches the shared simulator container.

It refuses (exit 1, with the reason on stderr) when another container uses more than
SIM_MAX_OTHER_CPU percent of a core (default 200, a proposal) or the 1-minute load average is at or
above SIM_MAX_LOAD (default 1.5 x the core count, a proposal). The simulator's own container, named
by IMAGE, is not counted. SIM_PREFLIGHT=off records anyway. Without docker it does not block: the
recording script fails on its own a moment later.

    python3 -m sim.preflight
"""

from __future__ import annotations

import os
import subprocess
import sys

MAX_OTHER_CPU_PERCENT = 200.0  # proposal: one other container using two cores
LOAD_PER_CORE = 1.5  # proposal


def parse_stats(text: str) -> list[tuple[str, float]]:
    """(container, CPU percent) from `docker stats --format '{{.Name}} {{.CPUPerc}}'`."""
    rows: list[tuple[str, float]] = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[-1].endswith("%"):
            try:
                rows.append((parts[0], float(parts[-1].rstrip("%"))))
            except ValueError:
                continue
    return rows


def busy_containers(
    stats: list[tuple[str, float]], own: str, limit: float
) -> list[tuple[str, float]]:
    """The containers other than `own` that use more than `limit` percent of a core."""
    return [(name, cpu) for name, cpu in stats if name != own and cpu > limit]


def container_stats() -> list[tuple[str, float]] | None:
    """What every running container is using now, or None if docker does not answer."""
    try:
        out = subprocess.run(
            ["docker", "stats", "--no-stream", "--format", "{{.Name}} {{.CPUPerc}}"],
            capture_output=True, text=True, check=True, timeout=30,
        ).stdout  # fmt: skip
    except (OSError, subprocess.SubprocessError):
        return None
    return parse_stats(out)


def main() -> int:
    if os.environ.get("SIM_PREFLIGHT") == "off":
        return 0
    own = os.environ.get("IMAGE", "nav-trust-c2-sim")
    cpu_limit = float(os.environ.get("SIM_MAX_OTHER_CPU", MAX_OTHER_CPU_PERCENT))
    cores = os.cpu_count() or 1
    load_limit = float(os.environ.get("SIM_MAX_LOAD", LOAD_PER_CORE * cores))

    problems: list[str] = []
    stats = container_stats()
    if stats is not None:
        problems += [
            f"container {name} uses {cpu:.0f}% CPU (limit {cpu_limit:.0f}%)"
            for name, cpu in busy_containers(stats, own, cpu_limit)
        ]
    load = os.getloadavg()[0]
    if load >= load_limit:
        problems.append(f"load average {load:.1f} is at or above {load_limit:.1f}")
    if not problems:
        return 0
    print(
        "Not recording: the machine is busy, and a busy machine ruins recordings.", file=sys.stderr
    )
    for problem in problems:
        print(f"  {problem}", file=sys.stderr)
    print(
        "Stop what is using it, or record anyway with SIM_PREFLIGHT=off "
        "(limits: SIM_MAX_OTHER_CPU, SIM_MAX_LOAD).",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
