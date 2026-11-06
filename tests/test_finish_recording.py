"""A recorder that wrote a complete recording but did not exit is finished, not waited for.

The stub recorder is a Python one-liner that writes a file and then exits or sleeps, so none of
this needs the simulator (issue 179).
"""

import json
import subprocess
import sys
from pathlib import Path

from sim.finish_recording import Outcome, run

HEADER = {"t_s": 0.0, "event": "header", "schema": 1, "ground_truth": False}
STOP = {"t_s": 9.0, "event": "recording_stopped", "reason": "max_duration"}
CUT_SHORT = {"t_s": 5.0, "event": "position"}

STUB = (
    "import json, sys, time\n"
    "path, then, records = sys.argv[1], sys.argv[2], json.loads(sys.argv[3])\n"
    "open(path, 'w').write(''.join(json.dumps(r) + '\\n' for r in records))\n"
    "if then == 'hang':\n"
    "    time.sleep(60)\n"
    "sys.exit(1 if then == 'fail' else 0)\n"
)


def recorder(partial: Path, then: str, *records: dict[str, object]) -> list[str]:
    return [sys.executable, "-c", STUB, str(partial), then, json.dumps(records)]


def test_a_recorder_that_exits_cleanly_has_its_recording_moved_into_place(tmp_path: Path) -> None:
    partial, final = tmp_path / "r.partial", tmp_path / "r.jsonl"
    outcome = run(recorder(partial, "exit", HEADER, STOP), partial, final, limit_s=10)
    assert outcome is Outcome.DONE
    assert final.exists() and not partial.exists()


def test_a_recorder_that_fails_has_its_recording_discarded(tmp_path: Path) -> None:
    partial, final = tmp_path / "r.partial", tmp_path / "r.jsonl"
    outcome = run(recorder(partial, "fail", HEADER, STOP), partial, final, limit_s=10)
    assert outcome is Outcome.FAILED
    assert not final.exists() and not partial.exists()


def test_a_hung_recorder_with_a_complete_recording_is_rescued(tmp_path: Path) -> None:
    partial, final = tmp_path / "r.partial", tmp_path / "r.jsonl"
    outcome = run(recorder(partial, "hang", HEADER, STOP), partial, final, limit_s=1)
    assert outcome is Outcome.RESCUED
    assert final.exists() and not partial.exists()


def test_a_hung_recorder_with_an_incomplete_recording_is_discarded(tmp_path: Path) -> None:
    partial, final = tmp_path / "r.partial", tmp_path / "r.jsonl"
    outcome = run(recorder(partial, "hang", HEADER, CUT_SHORT), partial, final, limit_s=1)
    assert outcome is Outcome.FAILED
    assert not final.exists() and not partial.exists()


def test_a_hung_recorder_is_ended_and_its_stop_command_run(tmp_path: Path) -> None:
    partial, final = tmp_path / "r.partial", tmp_path / "r.jsonl"
    marker = tmp_path / "stopped"
    run(
        recorder(partial, "hang", HEADER, STOP),
        partial,
        final,
        limit_s=1,
        stop_cmd=f"touch {marker}",
    )
    assert marker.exists()


def test_the_command_line_says_what_happened_in_its_exit_code(tmp_path: Path) -> None:
    partial, final = tmp_path / "r.partial", tmp_path / "r.jsonl"
    cmd = [sys.executable, "-m", "sim.finish_recording", "--partial", str(partial)]
    cmd += ["--final", str(final), "--limit", "1", "--"]
    done = subprocess.run(cmd + recorder(partial, "exit", HEADER, STOP))
    assert done.returncode == 0
    final.unlink()
    rescued = subprocess.run(cmd + recorder(partial, "hang", HEADER, STOP))
    assert rescued.returncode == 10
    failed = subprocess.run(cmd + recorder(partial, "fail", HEADER, STOP))
    assert failed.returncode == 1
