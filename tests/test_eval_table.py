"""The committed results tables must be what the recordings produce (`make eval`,
`make eval-heldout`), including the fingerprint of the engine code."""

import json
from pathlib import Path

import pytest

from eval.evaluate import (
    HELDOUT_OUT,
    HELDOUT_RECORDINGS,
    HELDOUT_SCENARIOS,
    OUT,
    RECORDINGS,
    ROOT,
    SCENARIOS,
    evaluate,
    render_markdown,
)
from eval.metrics import EvalConfig

SETS = {
    "development": (RECORDINGS, SCENARIOS, OUT, "Evaluation results", "eval/recordings", False),
    "held-out": (
        ROOT / HELDOUT_RECORDINGS,
        ROOT / HELDOUT_SCENARIOS,
        ROOT / HELDOUT_OUT,
        "Held-out validation results",
        HELDOUT_RECORDINGS,
        True,
    ),
}


def have_recordings(name: str) -> bool:
    return any(SETS[name][0].glob("*.jsonl"))


@pytest.mark.parametrize("name", SETS)
def test_committed_results_match_a_fresh_evaluation(name: str) -> None:
    if not have_recordings(name):
        pytest.skip(f"no {name} recordings yet")
    recordings, scenarios, out, title, where, expectations = SETS[name]
    result = evaluate(recordings, scenarios, EvalConfig())
    json_path, md_path = out / "results.json", out / "results.md"
    assert json_path.exists() and md_path.exists(), (
        "run `make eval` / `make eval-heldout` and commit"
    )
    assert json_path.read_text(encoding="utf-8") == json.dumps(result, indent=2) + "\n", (
        f"{json_path.name} is stale (new recordings, a changed harness, or changed engine code): "
        "regenerate and commit"
    )
    assert md_path.read_text(encoding="utf-8") == render_markdown(
        result, title, where, expectations
    )


@pytest.mark.parametrize("name", SETS)
def test_every_scenario_has_all_its_runs(name: str) -> None:
    if not have_recordings(name):
        pytest.skip(f"no {name} recordings yet")
    recordings, scenarios, *_ = SETS[name]
    result = evaluate(recordings, scenarios, EvalConfig())
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
    assert len(a["engine_sha256"]) == 64
