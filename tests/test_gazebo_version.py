"""A recording says which Gazebo made it (issue 163): PX4 is pinned but Gazebo comes from PX4's
setup script at image build time, so its version floats."""

import subprocess

from sim.gazebo_version import gazebo_version


def fake(stdout: str = "", returncode: int = 0, error: Exception | None = None):  # type: ignore[no-untyped-def]
    def run(cmd: list[str], **kw: object) -> subprocess.CompletedProcess[str]:
        if error is not None:
            raise error
        return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr="")

    return run


def test_the_version_is_the_first_line_gazebo_prints() -> None:
    assert gazebo_version(fake("9.1.0\n")) == "9.1.0"


def test_no_gazebo_or_a_failing_one_gives_none_not_an_error() -> None:
    assert gazebo_version(fake(error=FileNotFoundError("gz"))) is None
    assert gazebo_version(fake("garbage", returncode=1)) is None
    assert gazebo_version(fake("   \n")) is None
