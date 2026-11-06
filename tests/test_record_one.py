"""The shell side of finishing a recording: record_one and report_outcome (issue 179).

They are the tail of sim/sim_lock.sh, run here under bash with a stub recorder, so no simulator.
"""

import json
import subprocess
import sys
from pathlib import Path

LOCK_SH = Path(__file__).resolve().parents[1] / "sim" / "sim_lock.sh"
FUNCTIONS = LOCK_SH.read_text(encoding="utf-8").split("\nrescued=()", 1)[1]
STUB = (
    "import json, sys, time\n"
    "path, then = sys.argv[1], sys.argv[2]\n"
    "records = [{'t_s': 0, 'event': 'header', 'schema': 1}, {'t_s': 9, 'event': 'recording_stopped'}]\n"
    "open(path, 'w').write(''.join(json.dumps(r) + '\\n' for r in records))\n"
    "if then == 'hang':\n"
    "    time.sleep(60)\n"
    "sys.exit(1 if then == 'fail' else 0)\n"
)


def run_script(tmp_path: Path) -> subprocess.CompletedProcess[str]:
    (tmp_path / "stub.py").write_text(STUB, encoding="utf-8")
    out = tmp_path / "out"
    out.mkdir()
    calls = "".join(
        f"record_one {name} {out}/{name}.jsonl 1 {sys.executable} {tmp_path}/stub.py "
        f"{out}/{name}.jsonl.partial {then} || true\n"
        for name, then in (("fine", "exit"), ("hung", "hang"), ("broken", "fail"))
    )
    script = (
        "set -euo pipefail\n"
        f"IMAGE=none RECORDER_MARGIN=0 PYTHONPATH={LOCK_SH.parents[1]}\nfailures=()\n"
        f"rescued=(){FUNCTIONS}\n{calls}ls {out}\nreport_outcome\n"
    )
    return subprocess.run(["bash", "-c", script], capture_output=True, text=True)


def test_a_rescued_run_is_kept_and_named_in_the_summary(tmp_path: Path) -> None:
    done = run_script(tmp_path)
    files = done.stdout.split("RESCUED RUNS")[0].split()
    assert "fine.jsonl" in files and "hung.jsonl" in files and "broken.jsonl" not in files
    assert "RESCUED RUNS" in done.stdout and "hung" in done.stdout.split("RESCUED RUNS")[1]


def test_a_failed_run_makes_the_script_fail_and_is_named(tmp_path: Path) -> None:
    done = run_script(tmp_path)
    assert done.returncode == 1
    assert "FAILED RUNS: broken" in done.stdout
