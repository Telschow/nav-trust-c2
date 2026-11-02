"""Recording scripts refuse to start on a busy machine (issue 176).

A recording started while another container used about 17 cores produced runs with no ground truth
and a stuck PX4. The preflight is tested without a simulator: `docker` is a stub on PATH."""

import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from sim.preflight import busy_containers, parse_stats

ROOT = Path(__file__).resolve().parent.parent
BUSY = "sandcastle-3041ee0c 1750.05%\nnav-trust-c2-sim 119.03%\nother 3.20%\n"
QUIET = "nav-trust-c2-sim 119.03%\nsandcastle-a 4.00%\n"


def stub_docker(tmp_path: Path, stats: str) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    stub = bin_dir / "docker"
    stub.write_text(f"#!/bin/sh\ncat <<'EOF'\n{stats}EOF\n", encoding="utf-8")
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    return bin_dir


def run_preflight(
    tmp_path: Path, stats: str | None, **env: str
) -> subprocess.CompletedProcess[str]:
    path = str(stub_docker(tmp_path, stats)) + os.pathsep if stats is not None else ""
    return subprocess.run(
        [sys.executable, "-m", "sim.preflight"], cwd=ROOT, capture_output=True, text=True,
        env={**os.environ, "PATH": path + "/usr/bin:/bin", "IMAGE": "nav-trust-c2-sim",
             "SIM_MAX_LOAD": "1000", **env},
        check=False,
    )  # fmt: skip


def test_docker_stats_lines_are_read_as_name_and_cpu_percent() -> None:
    assert parse_stats(BUSY) == [
        ("sandcastle-3041ee0c", 1750.05), ("nav-trust-c2-sim", 119.03), ("other", 3.2)
    ]  # fmt: skip


def test_only_other_containers_above_the_limit_are_busy() -> None:
    stats = parse_stats(BUSY)
    assert busy_containers(stats, own="nav-trust-c2-sim", limit=200.0) == [
        ("sandcastle-3041ee0c", 1750.05)
    ]
    assert busy_containers(stats, own="nav-trust-c2-sim", limit=5000.0) == []
    assert busy_containers(parse_stats("nav-trust-c2-sim 900%\n"), "nav-trust-c2-sim", 200.0) == []


def test_it_refuses_and_names_the_container_that_is_using_the_machine(tmp_path: Path) -> None:
    done = run_preflight(tmp_path, BUSY)
    assert done.returncode == 1
    assert "sandcastle-3041ee0c" in done.stderr and "1750" in done.stderr
    assert "nav-trust-c2-sim" not in done.stderr  # the simulator's own container is not blamed
    assert "SIM_PREFLIGHT=off" in done.stderr  # how to go on anyway


def test_it_passes_on_a_quiet_machine(tmp_path: Path) -> None:
    assert run_preflight(tmp_path, QUIET).returncode == 0


def test_the_override_lets_a_busy_machine_record(tmp_path: Path) -> None:
    assert run_preflight(tmp_path, BUSY, SIM_PREFLIGHT="off").returncode == 0


def test_the_threshold_is_set_by_an_environment_variable(tmp_path: Path) -> None:
    assert run_preflight(tmp_path, BUSY, SIM_MAX_OTHER_CPU="5000").returncode == 0


def test_a_high_load_average_refuses_too(tmp_path: Path) -> None:
    done = run_preflight(tmp_path, QUIET, SIM_MAX_LOAD="0")
    assert done.returncode == 1 and "load average" in done.stderr


def test_without_docker_it_does_not_block(tmp_path: Path) -> None:
    done = run_preflight(tmp_path, None)  # no docker on PATH: the script fails on its own later
    assert done.returncode == 0


@pytest.mark.parametrize(("stats", "starts"), [(BUSY, False), (QUIET, True)])
def test_every_recording_script_that_sources_the_lock_gets_the_check(
    tmp_path: Path, stats: str, starts: bool
) -> None:
    bin_dir = stub_docker(tmp_path, stats)
    done = subprocess.run(
        ["bash", "-c", "set -euo pipefail; source sim/sim_lock.sh; echo started"],
        cwd=ROOT, capture_output=True, text=True, check=False,
        env={
            **os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            "TMPDIR": str(tmp_path), "IMAGE": "nav-trust-c2-sim", "SIM_MAX_LOAD": "1000",
        },
    )  # fmt: skip
    assert ("started" in done.stdout) is starts
    assert (done.returncode == 0) is starts
    assert not (tmp_path / "nav-trust-c2-sim.lock").exists()  # the lock is released either way
