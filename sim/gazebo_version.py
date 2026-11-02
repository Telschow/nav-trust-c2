"""Which Gazebo made a recording (issue 163). Gazebo comes from PX4's setup script when the image
is built, so unlike PX4 (pinned to a commit) its version floats; the recording header names it.

No simulator dependency: it asks the `gz` command and says None when there is none."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from typing import Any


def gazebo_version(run: Callable[..., Any] = subprocess.run) -> str | None:
    """The first line `gz sim --versions` prints, or None if Gazebo is missing or fails."""
    try:
        out = run(["gz", "sim", "--versions"], capture_output=True, text=True, check=False)
    except OSError:
        return None
    if out.returncode != 0:
        return None
    lines = [line.strip() for line in out.stdout.splitlines() if line.strip()]
    return lines[0] if lines else None
