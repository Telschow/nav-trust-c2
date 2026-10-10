"""The requirements trace (docs/product/trace.csv) must not claim evidence that does not exist."""

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRACE = ROOT / "docs" / "product" / "trace.csv"
STATUSES = {"met", "partial", "not-met", "gap"}
VERIFICATION = {"test", "manual", "eval", "gap"}
KINDS = {"requirement", "metric"}


def rows() -> list[dict[str, str]]:
    with TRACE.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def test_columns_and_values_are_valid() -> None:
    data = rows()
    assert data and set(data[0]) == {
        "id",
        "kind",
        "requirement",
        "verification",
        "evidence",
        "status",
        "notes",
    }
    ids = [r["id"] for r in data]
    assert len(ids) == len(set(ids)), "duplicate ids"
    for r in data:
        assert (
            r["kind"] in KINDS and r["status"] in STATUSES and r["verification"] in VERIFICATION
        ), r["id"]
        assert r["requirement"].strip() and r["notes"].strip(), (
            f"{r['id']}: say what the evidence shows"
        )


def test_every_evidence_path_exists() -> None:
    missing = [
        f"{r['id']}: {p}"
        for r in rows()
        for p in r["evidence"].split(";")
        if p and not (ROOT / p).exists()
    ]
    assert missing == []


def test_tested_requirements_are_named_in_a_test() -> None:
    """A requirement verified by test must be findable from the tests by its id."""
    sources = [
        p.read_text(encoding="utf-8", errors="ignore")
        for base in ("tests", "console/src")
        for p in (ROOT / base).rglob("*")
        if p.suffix in {".py", ".ts", ".tsx"}
    ]
    unnamed = [
        r["id"]
        for r in rows()
        if r["kind"] == "requirement"
        and r["verification"] == "test"
        and not any(r["id"] in s for s in sources)
    ]
    assert unnamed == [], f"not mentioned in any test: {unnamed}"


def test_a_gap_or_partial_status_is_never_hidden() -> None:
    """requirements.md must list every row, so the table and the prose cannot disagree."""
    text = (ROOT / "docs" / "product" / "requirements.md").read_text(encoding="utf-8")
    assert [r["id"] for r in rows() if r["id"] not in text] == []
    for r in rows():
        if r["status"] in {"partial", "gap"}:
            assert r["status"] in text, "requirements.md should show the same status words"
