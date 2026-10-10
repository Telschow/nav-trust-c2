"""The committed results table must be what the recordings produce (`make eval`)."""

from pathlib import Path

import pytest

from eval.evaluate import OUT, RECORDINGS, SCENARIOS, evaluate, render_markdown
from eval.metrics import EvalConfig

HAVE_RECORDINGS = any(RECORDINGS.glob("*.jsonl"))


@pytest.mark.skipif(not HAVE_RECORDINGS, reason="no recordings yet (make record-all)")
def test_committed_results_match_a_fresh_evaluation() -> None:
    import json

    result = evaluate(RECORDINGS, SCENARIOS, EvalConfig())
    json_path, md_path = OUT / "results.json", OUT / "results.md"
    assert json_path.exists() and md_path.exists(), "run `make eval` and commit the results"
    assert json_path.read_text(encoding="utf-8") == json.dumps(result, indent=2) + "\n", (
        "eval/results.json is stale: run `make eval` and commit"
    )
    assert md_path.read_text(encoding="utf-8") == render_markdown(result), (
        "eval/results.md is stale: run `make eval` and commit"
    )


@pytest.mark.skipif(not HAVE_RECORDINGS, reason="no recordings yet (make record-all)")
def test_every_scenario_has_all_its_runs() -> None:
    result = evaluate(RECORDINGS, SCENARIOS, EvalConfig())
    short = {
        n: (d["aggregate"]["runs"], d["aggregate"]["runs_expected"])
        for n, d in result["scenarios"].items()
        if d["aggregate"]["runs"] != d["aggregate"]["runs_expected"]
    }
    assert short == {}, f"missing recordings (found, expected): {short}"


def test_evaluation_is_deterministic_and_handles_an_empty_directory(tmp_path: Path) -> None:
    a = evaluate(tmp_path, SCENARIOS, EvalConfig())
    b = evaluate(tmp_path, SCENARIOS, EvalConfig())
    assert a == b and all(d["aggregate"]["runs"] == 0 for d in a["scenarios"].values())
    assert "| nominal | 0 of 4 |" in render_markdown(a)
