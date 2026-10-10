"""Expectations for the held-out validation, written before any held-out run was recorded.

docs/validation/heldout-protocol.md explains them. They are code so that the judgement of "met"
or "not met" is fixed in advance and cannot be adjusted after seeing the numbers. The values come
from the development results (eval/results.md) plus a margin, and are proposals, not requirements.
A failed expectation is reported as failed; the engine is not retuned to pass it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

MAX_TTD_S = 5.0  # development maximum was 3.2 s
MAX_RED_AFTER_LONG_OUTAGE_S = 10.0  # development: 6.3 to 6.4 s
EXPECTED_INTERRUPTIONS = {
    "nominal": 0,
    "short_outage": 0,
    "wrong_fix": 0,
    "long_outage": 1,
    "stuck_position": 1,
}
EXPECTED_MISSION_FINISHED = {
    "nominal": True,
    "short_outage": True,
    "wrong_fix": True,
    "long_outage": False,
    "stuck_position": False,
}


@dataclass(frozen=True)
class Outcome:
    id: str
    statement: str
    met: bool
    detail: str


Run = tuple[str, str, dict[str, Any]]  # (scenario, class, per-run metrics)


def _runs(result: dict[str, Any]) -> list[Run]:
    return [
        (name, data["aggregate"]["class"], run)
        for name, data in result["scenarios"].items()
        for run in data["runs"]
    ]


def _all(
    runs: list[Run], ok: Callable[[str, dict[str, Any]], bool], describe: Callable[[Run], str]
) -> tuple[bool, str]:
    bad = [describe(r) for r in runs if not ok(r[1], r[2])]
    return not bad, "all runs" if not bad else "; ".join(bad)


def check(result: dict[str, Any]) -> list[Outcome]:
    runs = _runs(result)
    scenarios = result["scenarios"]
    faulted = [r for r in runs if r[2]["detected"] is not None]
    out: list[Outcome] = []

    def add(id_: str, statement: str, verdict: tuple[bool, str]) -> None:
        out.append(Outcome(id_, statement, verdict[0], verdict[1]))

    short = {
        n: (d["aggregate"]["runs"], d["aggregate"]["runs_expected"])
        for n, d in scenarios.items()
        if d["aggregate"]["runs"] != d["aggregate"]["runs_expected"]
    }
    add(
        "E0",
        "Every scenario has all its recordings",
        (not short, "complete" if not short else f"missing: {short}"),
    )

    add(
        "E1",
        "Every fault run is detected (a report that is not GREEN after the fault starts)",
        _all(
            faulted,
            lambda _c, m: bool(m["detected"]),
            lambda r: f"{r[2]['recording']} not detected",
        ),
    )
    add(
        "E2",
        f"Time to detect is at most {MAX_TTD_S:g} s in every fault run",
        _all(
            faulted,
            lambda _c, m: m["ttd_s"] is not None and m["ttd_s"] <= MAX_TTD_S,
            lambda r: f"{r[2]['recording']} took {r[2]['ttd_s']} s",
        ),
    )
    add(
        "E3",
        "No false alert in any run (no non-GREEN episode outside a fault window)",
        _all(
            runs,
            lambda _c, m: m["false_alert_episodes"] == 0,
            lambda r: f"{r[2]['recording']} had {r[2]['false_alert_episodes']}",
        ),
    )
    add(
        "E4",
        "No second in which the engine said GREEN while the true position was more than 10 m off",
        _all(
            runs,
            lambda _c, m: m["misleading_s"] == 0,
            lambda r: f"{r[2]['recording']}: {r[2]['misleading_s']} s (None means no ground truth)",
        ),
    )

    def classified(cls: str, m: dict[str, Any]) -> bool:
        if cls == "nominal":
            return bool(m["worst_state"] == "GREEN")
        if cls in ("short_outage", "wrong_fix"):
            return bool(m["worst_state"] == "AMBER")
        if cls == "long_outage":
            return (
                m["red_after_fault_s"] is not None
                and m["red_after_fault_s"] <= MAX_RED_AFTER_LONG_OUTAGE_S
            )
        return bool(m["worst_state"] == "RED")  # stuck_position

    add(
        "E5",
        "Severity matches the class: nominal stays GREEN; short outage and wrong fix reach AMBER only;"
        f" a long outage reaches RED within {MAX_RED_AFTER_LONG_OUTAGE_S:g} s; a frozen position reaches RED",
        _all(
            runs,
            classified,
            lambda r: (
                f"{r[2]['recording']} worst {r[2]['worst_state']}, RED after {r[2]['red_after_fault_s']}"
            ),
        ),
    )
    add(
        "E6",
        "Operator interruptions per run: 1 for a long outage or a frozen position, otherwise 0",
        _all(
            runs,
            lambda cls, m: m["interruptions"] == EXPECTED_INTERRUPTIONS[cls],
            lambda r: f"{r[2]['recording']} had {r[2]['interruptions']}",
        ),
    )
    add(
        "E7",
        "PX4 behaved as the scenario file says: missions finish for nominal, short outage and wrong fix,"
        " and do not for a long outage or a frozen position",
        _all(
            runs,
            lambda cls, m: m["mission_finished"] == EXPECTED_MISSION_FINISHED[cls],
            lambda r: f"{r[2]['recording']} finished={r[2]['mission_finished']}",
        ),
    )
    return out
