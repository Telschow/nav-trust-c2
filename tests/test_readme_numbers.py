"""The numbers on the README's first screen are checked against the results files (issue 162).

"Metrics are measured, never typed": the figures the README quotes come from `eval/results.json`,
`eval/heldout/results.json`, `eval/fleet/results.json` and the held-out table. If one of those
changes and the README does not, this fails, so a stale headline cannot ship. Three figures are
history rather than something the current files can recompute (the first version's 30.8% and the
5.3 km run-away at the 220 s cut-off); they are checked against the documents that record them.
The 3 m bound is the calibration's setting and is not read from a results file here.
"""

import json
import re
from pathlib import Path
from typing import Any, NamedTuple

ROOT = Path(__file__).resolve().parent.parent


class Sources(NamedTuple):
    readme: str
    dev: dict[str, Any]
    held: dict[str, Any]
    fleet: dict[str, Any]
    held_md: str
    risks: str
    adr3: str
    adr4: str


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def sources() -> Sources:
    return Sources(
        read("README.md"),
        json.loads(read("eval/results.json")),
        json.loads(read("eval/heldout/results.json")),
        json.loads(read("eval/fleet/results.json")),
        read("eval/heldout/results.md"),
        read("docs/programme/risks.md"),
        read("docs/adr/0003-land-for-frozen-position.md"),
        read("docs/adr/0004-authority-under-lost-link.md"),
    )


def summary(readme: str) -> str:
    start, end = "<!-- summary-start -->", "<!-- summary-end -->"
    return " ".join(readme.split(start, 1)[1].split(end, 1)[0].split())


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


def problems(src: Sources) -> list[str]:
    text = summary(src.readme)
    found: list[str] = []

    def expect(label: str, pattern: str, want: tuple[str, ...]) -> None:
        m = re.search(pattern, text)
        if m is None:
            found.append(f"{label}: the README sentence is gone or changed shape")
        elif m.groups() != want:
            found.append(f"{label}: README says {m.groups()}, the results say {want}")

    loss = runs(src.dev, src.held, prefix="long_outage") + runs(
        src.dev, src.held, prefix="short_outage"
    )
    frozen = runs(src.dev, src.held, prefix="stuck_position")
    nominal = runs(src.dev, src.held, prefix="nominal")
    loss_t = [r["ttd_s"] for r in loss if r["detected"]]
    frozen_t = [r["ttd_s"] for r in frozen if r["detected"]]
    expect(
        "detection",
        r"GNSS loss was detected in ([\d.]+) to ([\d.]+) s in (\d+) runs; a frozen position in "
        r"([\d.]+) to ([\d.]+) s. No alert in (\d+) nominal runs",
        (
            f"{min(loss_t):.1f}", f"{max(loss_t):.1f}", str(len(loss_t)),
            f"{min(frozen_t):.1f}", f"{max(frozen_t):.1f}",
            str(sum(r["false_alert_episodes"] == 0 for r in nominal)),
        ),
    )  # fmt: skip
    expect(
        "bound coverage",
        r"held in ([\d.]+)% of ([\d,]+) reports on the data it was tuned on and in ([\d.]+)% of "
        r"([\d,]+) reports on an independent set",
        (
            percent(src.dev["overall"]["bound_coverage"]),
            f"{src.dev['overall']['green_reports']:,}",
            percent(src.held["overall"]["bound_coverage"]),
            f"{src.held['overall']['green_reports']:,}",
        ),
    )
    approved = src.fleet["scenarios"]["loss_approved"]
    denied = src.fleet["scenarios"]["loss_denied"]
    expect(
        "fleet",
        r"was (\d+)% when the operator approved the re-task and (\d+)% when the operator denied "
        r"it \((\d+) runs each",
        (
            str(round(approved["area_covered_median"] * 100)),
            str(round(denied["area_covered_median"] * 100)),
            str(min(approved["runs"], denied["runs"])),
        ),
    )
    if approved["runs"] != denied["runs"]:
        found.append("fleet: the two scenarios have different numbers of runs; 'each' is wrong")
    met, total = expectations_met(src.held_md)
    expect("held-out", r"(\d+) of (\d+) pre-declared expectations met", (str(met), str(total)))

    # history: the documents that recorded these say the same thing
    expect("first version", r"accuracy figure, held in ([\d.]+)%", ("30.8",))
    if "30.8%" not in src.risks:
        found.append("first version: docs/programme/risks.md does not record 30.8%")
    far = re.search(r"\| none \| (\d+) m \|", src.adr3)
    cut = re.search(r"at the (\d+) s cut-off", src.adr4)
    if far is None or cut is None:
        found.append("run-away: ADR 0003 or 0004 no longer records the distance or the cut-off")
    else:
        expect(
            "run-away",
            r"\(([\d.]+) km at the (\d+) s cut-off",
            (f"{int(far.group(1)) / 1000:.1f}", cut.group(1)),
        )
    return found


def test_the_readme_headline_numbers_match_the_results_files() -> None:
    assert problems(sources()) == []


def test_a_number_changed_in_the_results_but_not_in_the_readme_is_caught() -> None:
    src = sources()
    held = json.loads(json.dumps(src.held))
    held["overall"]["bound_coverage"] = 0.95
    fleet = json.loads(json.dumps(src.fleet))
    fleet["scenarios"]["loss_denied"]["area_covered_median"] = 0.5
    assert any("bound coverage" in p for p in problems(src._replace(held=held)))
    assert any("fleet" in p for p in problems(src._replace(fleet=fleet)))


def test_a_number_changed_in_the_readme_but_not_in_the_results_is_caught() -> None:
    src = sources()
    for old, new, label in (
        ("1.0 to 1.4", "1.1 to 1.4", "detection"),
        ("5.3 km", "9.0 km", "run-away"),
        ("220 s cut-off", "300 s cut-off", "run-away"),
        ("30.8%", "40.8%", "first version"),
    ):
        assert old in src.readme, old
        changed = src._replace(readme=src.readme.replace(old, new, 1))
        assert any(label in p for p in problems(changed)), old


def test_the_docs_say_the_contingency_is_partly_built_and_not_that_it_is_not_built() -> None:
    for name in ("README.md", "docs/ICD.md"):
        text = " ".join(read(name).split())
        assert "ADR 0004, not built" not in text, name
        assert "always empty until the onboard monitor exists" not in text, name
    assert "partly built" in " ".join(read("README.md").split())
