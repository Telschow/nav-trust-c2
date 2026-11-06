"""Wait for the simulator to be ready instead of sleeping a fixed time (issue 180)."""

import subprocess
from collections.abc import Callable
from pathlib import Path

from sim.wait_ready import unmet_after_waiting
from tests.support import Clock


def waiter(clock: Clock) -> Callable[[float], None]:
    def sleep(seconds: float) -> None:
        clock.t += seconds

    return sleep


def test_a_simulator_that_is_ready_at_once_is_not_waited_for() -> None:
    clock = Clock()
    unmet = unmet_after_waiting(
        {"gazebo": lambda: True, "uav1": lambda: True},
        limit_s=100,
        poll_s=5,
        clock=clock,
        sleep=waiter(clock),
    )
    assert unmet == []
    assert clock.t == Clock.t


def test_it_waits_until_every_check_passes() -> None:
    clock = Clock()
    ready_at = Clock.t + 30
    unmet = unmet_after_waiting(
        {"gazebo": lambda: True, "uav1": lambda: clock.t >= ready_at},
        limit_s=100,
        poll_s=5,
        clock=clock,
        sleep=waiter(clock),
    )
    assert unmet == []
    assert Clock.t + 30 <= clock.t < Clock.t + 40


def test_at_the_limit_it_names_what_was_not_ready() -> None:
    clock = Clock()
    unmet = unmet_after_waiting(
        {"gazebo": lambda: True, "uav1": lambda: False, "uav2": lambda: False},
        limit_s=20,
        poll_s=5,
        clock=clock,
        sleep=waiter(clock),
    )
    assert unmet == ["uav1", "uav2"]
    assert clock.t <= Clock.t + 25


def test_a_check_that_raises_counts_as_not_ready() -> None:
    clock = Clock()

    def broken() -> bool:
        raise OSError("gz not found")

    unmet = unmet_after_waiting(
        {"gazebo": broken}, limit_s=10, poll_s=5, clock=clock, sleep=waiter(clock)
    )
    assert unmet == ["gazebo"]


LOCK_SH = Path(__file__).resolve().parents[1] / "sim" / "sim_lock.sh"
WAIT_FOR_SIM = LOCK_SH.read_text(encoding="utf-8").split("\nwait_for_sim() {", 1)[1]


def run_wait_for_sim(tmp_path: Path, exec_exit_code: int) -> subprocess.CompletedProcess[str]:
    """wait_for_sim under bash, with a stub `docker` that fails or not on `exec`."""
    docker = tmp_path / "docker"
    docker.write_text(
        '#!/bin/sh\nif [ "$1" = exec ]; then exit ' + str(exec_exit_code) + " ; fi\n"
        'if [ "$1" = logs ]; then echo "px4: waiting for GPS"; fi\n',
        encoding="utf-8",
    )
    docker.chmod(0o755)
    script = f"IMAGE=sim\nwait_for_sim() {{{WAIT_FOR_SIM}\nwait_for_sim 1\necho carried-on\n"
    env = {"PATH": f"{tmp_path}:/usr/bin:/bin"}
    return subprocess.run(["bash", "-c", script], capture_output=True, text=True, env=env)


def test_a_simulator_that_becomes_ready_lets_the_script_carry_on(tmp_path: Path) -> None:
    done = run_wait_for_sim(tmp_path, exec_exit_code=0)
    assert done.returncode == 0 and "carried-on" in done.stdout


def test_a_simulator_that_never_is_ready_stops_the_script_with_its_log(tmp_path: Path) -> None:
    done = run_wait_for_sim(tmp_path, exec_exit_code=1)
    assert done.returncode == 4 and "carried-on" not in done.stdout
    assert "px4: waiting for GPS" in done.stderr
