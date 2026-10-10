import copy
from collections.abc import Callable
from typing import Any

from eval.expectations import check


def run(name: str, **kw: Any) -> dict[str, Any]:
    base = {
        "recording": name, "detected": None, "ttd_s": None, "false_alert_episodes": 0,
        "misleading_s": 0.0, "worst_state": "GREEN", "red_after_fault_s": None,
        "interruptions": 0, "mission_finished": True,
    }  # fmt: skip
    return {**base, **kw}


def result() -> dict[str, Any]:
    def scenario(
        cls: str, runs: list[dict[str, Any]], expected: int | None = None
    ) -> dict[str, Any]:
        return {
            "aggregate": {"class": cls, "runs": len(runs), "runs_expected": expected or len(runs)},
            "runs": runs,
        }

    return {
        "scenarios": {
            "nom": scenario("nominal", [run("nom-1")]),
            "short": scenario("short_outage", [run("short-1", detected=True, ttd_s=1.2, worst_state="AMBER")]),
            "wrong": scenario("wrong_fix", [run("wrong-1", detected=True, ttd_s=0.3, worst_state="AMBER")]),
            "long": scenario("long_outage", [run("long-1", detected=True, ttd_s=1.3, worst_state="RED", red_after_fault_s=6.3, interruptions=1, mission_finished=False)]),
            "stuck": scenario("stuck_position", [run("stuck-1", detected=True, ttd_s=3.0, worst_state="RED", red_after_fault_s=3.0, interruptions=1, mission_finished=False)]),
        }
    }  # fmt: skip


def verdicts(r: dict[str, Any]) -> dict[str, bool]:
    return {o.id: o.met for o in check(r)}


def test_a_clean_result_meets_every_expectation() -> None:
    assert verdicts(result()) == {f"E{i}": True for i in range(8)}


def test_each_expectation_can_fail_on_its_own() -> None:
    cases: dict[str, Callable[[dict[str, Any]], object]] = {
        "E0": lambda r: r["scenarios"]["nom"]["aggregate"].update(runs_expected=3),
        "E1": lambda r: r["scenarios"]["short"]["runs"][0].update(detected=False, ttd_s=None),
        "E2": lambda r: r["scenarios"]["stuck"]["runs"][0].update(ttd_s=5.5),
        "E3": lambda r: r["scenarios"]["nom"]["runs"][0].update(false_alert_episodes=1),
        "E4": lambda r: r["scenarios"]["stuck"]["runs"][0].update(misleading_s=1.5),
        "E5": lambda r: r["scenarios"]["short"]["runs"][0].update(worst_state="RED"),
        "E6": lambda r: r["scenarios"]["nom"]["runs"][0].update(interruptions=1),
        "E7": lambda r: r["scenarios"]["long"]["runs"][0].update(mission_finished=True),
    }
    for failing, mutate in cases.items():
        r = copy.deepcopy(result())
        mutate(r)
        got = verdicts(r)
        assert got[failing] is False, failing


def test_missing_ground_truth_is_not_silently_ok() -> None:
    r = result()
    r["scenarios"]["nom"]["runs"][0]["misleading_s"] = None
    assert verdicts(r)["E4"] is False


def test_slow_stuck_detection_is_the_documented_risk() -> None:
    r = result()
    r["scenarios"]["stuck"]["runs"][0].update(recording="stuck_position_slow-1", ttd_s=7.0)
    [e2] = [o for o in check(r) if o.id == "E2"]
    assert not e2.met and "stuck_position_slow-1 took 7.0 s" in e2.detail
