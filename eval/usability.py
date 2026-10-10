"""Usability session metrics from a backend audit database (docs/usability/).

One database per participant session (`make demo-run DEMO_DB=logs/usability/P1.sqlite`). The
audit log already holds when each recommendation was raised and when it was answered, on the
backend's clock (the `T+` clock in the console header), so time to decision needs no stopwatch.

    python -m eval.usability logs/usability/P1.sqlite logs/usability/P2.sqlite
    python -m eval.usability logs/usability/*.sqlite --csv > decisions.csv

The database is opened read-only. Nothing here measures noticing or understanding: those come
from the facilitator's observation sheet.
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO


@dataclass(frozen=True)
class RecommendationRow:
    session: str
    recommendation_id: str
    vehicle_id: str
    command: str | None
    raised_s: float
    expires_s: float
    outcome: str | None  # APPROVED, DENIED, EXPIRED, or None if never answered
    decided_s: float | None
    decided_by: str | None
    time_to_decision_s: float | None  # raised to decided; None if unanswered or expired
    executed: bool | None  # for approved ones: did the gate execute the command


@dataclass(frozen=True)
class SessionMetrics:
    session: str
    recommendations: list[RecommendationRow]
    rejected_decisions: int


def read_session(path: Path) -> SessionMetrics:
    db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        rows = db.execute("SELECT kind, payload FROM events ORDER BY id").fetchall()
    finally:
        db.close()
    recs: dict[str, dict[str, object]] = {}
    decisions: dict[str, dict[str, object]] = {}
    executed: dict[str, bool] = {}
    rejected = 0
    for kind, payload in rows:
        data = json.loads(payload)
        if kind == "recommendation":
            recs[data["id"]] = data
        elif kind == "decision":
            decisions[data["recommendation_id"]] = data
        elif kind == "command_executed":
            executed[data["recommendation_id"]] = True
        elif kind in ("command_failed", "command_blocked"):
            executed[data["recommendation_id"]] = False
        elif kind == "rejected_decision":
            rejected += 1

    out: list[RecommendationRow] = []
    for rid, rec in recs.items():
        d = decisions.get(rid)
        outcome = None if d is None else str(d["outcome"])
        answered = d is not None and outcome != "EXPIRED"
        decided_s = None if d is None else float(d["decided_s"])  # type: ignore[arg-type]
        raised = float(rec["created_s"])  # type: ignore[arg-type]
        out.append(
            RecommendationRow(
                session=path.stem,
                recommendation_id=rid,
                vehicle_id=str(rec["vehicle_id"]),
                command=None if rec["command"] is None else str(rec["command"]),
                raised_s=raised,
                expires_s=float(rec["expires_s"]),  # type: ignore[arg-type]
                outcome=outcome,
                decided_s=decided_s,
                decided_by=None if d is None else str(d["operator"]),
                time_to_decision_s=(decided_s - raised)
                if answered and decided_s is not None
                else None,
                executed=executed.get(rid) if outcome == "APPROVED" else None,
            )
        )
    return SessionMetrics(path.stem, out, rejected)


def fmt(v: float | None) -> str:
    return "" if v is None else f"{v:.1f}"


def write_csv(sessions: list[SessionMetrics], out: TextIO) -> None:
    w = csv.writer(out)
    w.writerow(
        ["session", "recommendation", "vehicle", "command", "raised_s", "outcome", "decided_by",
         "time_to_decision_s", "executed", "rejected_decisions_in_session"]
    )  # fmt: skip
    for s in sessions:
        for r in s.recommendations:
            w.writerow(
                [r.session, r.recommendation_id, r.vehicle_id, r.command or "", fmt(r.raised_s),
                 r.outcome or "unanswered", r.decided_by or "", fmt(r.time_to_decision_s),
                 "" if r.executed is None else str(r.executed).lower(), s.rejected_decisions]
            )  # fmt: skip


def print_table(sessions: list[SessionMetrics]) -> None:
    for s in sessions:
        print(f"{s.session}: {len(s.recommendations)} recommendation(s), "
              f"{s.rejected_decisions} rejected decision attempt(s)")  # fmt: skip
        for r in s.recommendations:
            print(f"  {r.recommendation_id}  {r.vehicle_id} {r.command or 're-task only':<13}"
                  f" raised T+{r.raised_s:6.1f}s  {r.outcome or 'unanswered':<10}"
                  f" time to decision {fmt(r.time_to_decision_s) or '-':>5} s"
                  f"  executed {'-' if r.executed is None else r.executed}")  # fmt: skip


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Usability session metrics from audit databases")
    p.add_argument("databases", nargs="+", type=Path)
    p.add_argument("--csv", action="store_true")
    args = p.parse_args(argv)
    missing = [str(d) for d in args.databases if not d.exists()]
    if missing:
        print(f"no such database: {', '.join(missing)}", file=sys.stderr)
        return 1
    sessions = [read_session(d) for d in args.databases]
    if args.csv:
        write_csv(sessions, sys.stdout)
    else:
        print_table(sessions)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
