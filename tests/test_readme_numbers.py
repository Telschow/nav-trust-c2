"""The numbers on the README's first screen are checked against the results files (issue 162).

"Metrics are measured, never typed": the figures the README quotes come from `eval/results.json`,
`eval/heldout/results.json`, `eval/fleet/results.json` and the held-out table. If one of those
changes and the README does not, this fails, so a stale headline cannot ship. Two figures are
history rather than something the current files can recompute (the first version's 30.8% and the
5.3 km run-away); they are checked against the documents that record them.
"""

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent


def summary(readme: str) -> str:
    start, end = "<!-- summary-start -->", "<!-- summary-end -->"
    return " ".join(readme.split(start, 1)[1].split(end, 1)[0].split())


def load(path: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((ROOT / path).read_text(encoding="utf-8"))
    return data


def percent(x: float) -> str:
    return f"{x * 100:.2f}".rstrip("0").rstrip(".")


def runs(*results: dict[str, Any], prefix: str) -> list[dict[str, Any]]:
    return [
        run
        for res in results
        for name, scenario in res["scenarios"].items()
        if name.startswith(prefix)
        for run in scenario["runs"]
    ]


def expectations_met(held_md: str) -> tuple[int, int]:
    rows = [line for line in held_md.splitlines() if re.match(r"\| E\d ", line)]
    return sum(1 for r in rows if "| met |" in r), len(rows)


def problems(
    readme: str,
    dev: dict[str, Any],
    held: dict[str, Any],
    fleet: dict[str, Any],
    held_md: str,
    risks: str,
    adr3: str,
) -> list[str]:
    text = summary(readme)
    found: list[str] = []

    def expect(label: str, pattern: str, want: tuple[str, ...]) -> None:
        m = re.search(pattern, text)
        if m is None:
            found.append(f"{label}: the README sentence is gone or changed shape")
        elif m.groups() != want:
            found.append(f"{label}: README says {m.groups()}, the results say {want}")

    loss = [
        r for r in runs(dev, held, prefix="long_outage") + runs(dev, held, prefix="short_outage")
    ]
    frozen = runs(dev, held, prefix="stuck_position")
    nominal = runs(dev, held, prefix="nominal")
    loss_t = [r["ttd_s"] for r in loss if r["detected"]]
    frozen_t = [r["ttd_s"] for r in frozen if r["detected"]]
    expect(
        "detection",
        r"GNSS loss was detected in ([\d.]+) to ([\d.]+) s in (\d+) runs; a frozen position in "
        r"([\d.]+) to ([\d.]+) s. No alert in (\d+) nominal runs",
        (
            f"{min(loss_t):.1f}", f"{max(loss_t):.1f}", str(len(loss_t)),
            f"{min(frozen_t):.1f}", f"{max(frozen_t):.1f}",
            str(len(nominal) - sum(r["false_alert_episodes"] > 0 for r in nominal)),
        ),
    )  # fmt: skip
    expect(
        "bound coverage",
        r"held in ([\d.]+)% of ([\d,]+) reports on the data it was tuned on and in ([\d.]+)% of "
        r"([\d,]+) reports on an independent set",
        (
            percent(dev["overall"]["bound_coverage"]), f"{dev['overall']['green_reports']:,}",
            percent(held["overall"]["bound_coverage"]), f"{held['overall']['green_reports']:,}",
        ),
    )  # fmt: skip
    approved, denied = fleet["scenarios"]["loss_approved"], fleet["scenarios"]["loss_denied"]
    expect(
        "fleet",
        r"was (\d+)% when the operator approved the re-task and (\d+)% when the operator denied "
        r"it \((\d+) runs each",
        (
            str(round(approved["area_covered_median"] * 100)),
            str(round(denied["area_covered_median"] * 100)),
            str(approved["runs"]) if approved["runs"] == denied["runs"] else "differ",
        ),
    )
    met, total = expectations_met(held_md)
    expect("held-out", r"(\d+) of (\d+) pre-declared expectations met", (str(met), str(total)))

    expect("first version", r"accuracy figure, held in ([\d.]+)%", ("30.8",))
    if "30.8%" not in risks:
        found.append("first version: docs/programme/risks.md does not record 30.8%")
    if "5.3 km" in text and "5320 m" not in adr3:
        found.append("run-away: the README says 5.3 km but ADR 0003 does not record 5320 m")
    return found


def test_the_readme_headline_numbers_match_the_results_files() -> None:
    assert (
        problems(
            (ROOT / "README.md").read_text(encoding="utf-8"),
            load("eval/results.json"),
            load("eval/heldout/results.json"),
            load("eval/fleet/results.json"),
            (ROOT / "eval/heldout/results.md").read_text(encoding="utf-8"),
            (ROOT / "docs/programme/risks.md").read_text(encoding="utf-8"),
            (ROOT / "docs/adr/0003-land-for-frozen-position.md").read_text(encoding="utf-8"),
        )
        == []
    )


def test_a_number_changed_in_the_results_but_not_in_the_readme_is_caught() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    args = (
        load("eval/results.json"),
        load("eval/heldout/results.json"),
        load("eval/fleet/results.json"),
        (ROOT / "eval/heldout/results.md").read_text(encoding="utf-8"),
        (ROOT / "docs/programme/risks.md").read_text(encoding="utf-8"),
        (ROOT / "docs/adr/0003-land-for-frozen-position.md").read_text(encoding="utf-8"),
    )
    dev, held, fleet, *rest = args
    held_changed = json.loads(json.dumps(held))
    held_changed["overall"]["bound_coverage"] = 0.95
    fleet_changed = json.loads(json.dumps(fleet))
    fleet_changed["scenarios"]["loss_denied"]["area_covered_median"] = 0.5
    assert any("bound coverage" in p for p in problems(readme, dev, held_changed, fleet, *rest))
    assert any("fleet" in p for p in problems(readme, dev, held, fleet_changed, *rest))
    assert any(
        "detection" in p
        for p in problems(readme.replace("1.0 to 1.4", "1.1 to 1.4"), dev, held, fleet, *rest)
    )


def test_the_docs_do_not_call_built_contingency_code_not_built() -> None:
    for name in ("README.md", "docs/ICD.md"):
        text = " ".join((ROOT / name).read_text(encoding="utf-8").split())
        assert "ADR 0004, not built" not in text, name
        assert "always empty until the onboard monitor exists" not in text, name
