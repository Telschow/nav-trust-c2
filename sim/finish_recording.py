"""Run a recorder; if it writes a complete recording and then does not exit, finish it anyway.

The recorder sometimes hangs after `recording_stopped` (issue 178). The recording scripts give it a
time limit, the run's maximum duration plus a margin. At the limit a partial file that passes the
completeness check (sim/recording_check.py) is kept and the recorder is ended; an incomplete one is
discarded, as it is when the recorder fails.

    python3 -m sim.finish_recording --partial P --final F --limit SECONDS [--stop CMD] -- RECORDER

Exit code 0: the recorder finished and the recording is in place. 10: rescued, the recorder had to
be ended but the recording is complete and in place. 1: no recording was kept.
`--stop` is a shell command that ends the recorder where killing the local process does not reach
it, such as `docker exec IMAGE pkill -f sim.record_run`.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from enum import Enum
from pathlib import Path

from sim.recording_check import incomplete_reason

RESCUED_EXIT_CODE = 10
GRACE_S = 10.0  # how long a recorder gets to exit after being asked to, before it is killed


class Outcome(Enum):
    DONE = "done"
    RESCUED = "rescued"
    FAILED = "failed"


def run(
    cmd: list[str],
    partial: Path,
    final: Path,
    limit_s: float,
    stop_cmd: str | None = None,
) -> Outcome:
    proc = subprocess.Popen(cmd)
    try:
        code = proc.wait(timeout=limit_s)
    except subprocess.TimeoutExpired:
        reason = incomplete_reason(partial)  # judged at the limit, before the recorder is ended
        _end(proc, stop_cmd)
        if reason is None:
            partial.replace(final)
            print(f"rescued: the recorder did not exit within {limit_s:.0f} s", file=sys.stderr)
            return Outcome.RESCUED
        print(f"discarded: the recorder did not exit and {reason}", file=sys.stderr)
        partial.unlink(missing_ok=True)
        return Outcome.FAILED
    if code != 0:
        partial.unlink(missing_ok=True)
        return Outcome.FAILED
    partial.replace(final)
    return Outcome.DONE


def _end(proc: subprocess.Popen[bytes], stop_cmd: str | None) -> None:
    if stop_cmd:
        subprocess.run(stop_cmd, shell=True, check=False)
    proc.terminate()
    try:
        proc.wait(timeout=GRACE_S)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--partial", type=Path, required=True)
    parser.add_argument("--final", type=Path, required=True)
    parser.add_argument("--limit", type=float, required=True, help="seconds the recorder gets")
    parser.add_argument("--stop", help="shell command that ends the recorder")
    parser.add_argument("recorder", nargs="+", help="after --")
    args = parser.parse_args(argv)
    outcome = run(args.recorder, args.partial, args.final, args.limit, args.stop)
    return {Outcome.DONE: 0, Outcome.RESCUED: RESCUED_EXIT_CODE, Outcome.FAILED: 1}[outcome]


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
