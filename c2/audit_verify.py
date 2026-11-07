"""Check an audit database: every command that was sent traces to one operator approval.

    python -m c2.audit_verify logs/audit.sqlite      # exit 0 if clean, 1 and the problems if not

For each `command_sent` row it checks that the row cites a `decision` row (`decision_audit_id`),
that this row is an approval of the same recommendation, that it was taken in the same backend
run (between the same `session_started` rows, because every run restarts the clock and the
recommendation counter), and that the run approved the recommendation once. It also checks that no
recommendation id was used twice. It compares what was sent (vehicle and action) with the
audited `recommendation` row of the same run, so a command to another vehicle or of another kind
than the one the operator saw fails. A database from before issue 159 has no such citations and
fails: that is the point, it cannot prove the link.

This is a linkage check, not tamper evidence: the log is append-only in the application, but
someone who edits the SQLite file directly is not detected, and a `command_sent` row proves an
approval existed, not that the vehicle then did anything.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from c2.audit import AuditEvent, AuditLog


def problems(path: str | Path) -> list[str]:
    log = AuditLog(path)
    try:
        events = log.events()
    finally:
        log.close()
    by_id = {e.id: e for e in events}
    session_of: dict[int, str] = {}
    current = ""
    for e in events:
        if e.kind == "session_started":
            current = str(e.payload["session_id"])
        session_of[e.id] = current
    found: list[str] = []

    seen: set[str] = set()
    for e in events:
        if e.kind == "recommendation":
            rid = str(e.payload["id"])
            if rid in seen:
                found.append(f"row {e.id}: recommendation id {rid} was used before")
            seen.add(rid)

    for e in events:
        if e.kind != "command_sent":
            continue
        found.extend(_check_command(e, by_id, session_of, events))
    return found


def _check_command(
    sent: AuditEvent,
    by_id: dict[int, AuditEvent],
    session_of: dict[int, str],
    events: list[AuditEvent],
) -> list[str]:
    where = f"row {sent.id} command_sent {sent.payload.get('action')}"
    ref = sent.payload.get("decision_audit_id")
    decision = by_id.get(ref) if isinstance(ref, int) else None
    if decision is None or decision.kind != "decision":
        return [f"{where}: cites no decision row"]
    rid = sent.payload.get("recommendation_id")
    if decision.payload.get("recommendation_id") != rid:
        return [f"{where}: the decision row {decision.id} is about another recommendation"]
    if decision.payload.get("outcome") != "APPROVED":
        return [f"{where}: the decision row {decision.id} is not an approval"]
    if session_of[decision.id] != session_of[sent.id]:
        return [f"{where}: the approval was taken in another session"]
    approvals = [
        e
        for e in events
        if e.kind == "decision"
        and e.payload.get("recommendation_id") == rid
        and e.payload.get("outcome") == "APPROVED"
        and session_of[e.id] == session_of[sent.id]
    ]
    if len(approvals) != 1:
        return [f"{where}: {len(approvals)} approvals of {rid} in this session, expected one"]
    rec_rows = [
        e
        for e in events
        if e.kind == "recommendation"
        and e.payload.get("id") == rid
        and session_of[e.id] == session_of[sent.id]
    ]
    if not rec_rows:
        return [f"{where}: no recommendation row {rid} in this session"]
    return [f"{where}: {why}" for why in _differs(sent, rec_rows[0].payload)]


def _differs(sent: AuditEvent, rec: dict[str, Any]) -> list[str]:
    """How the sent command departs from the recommendation the operator was shown."""
    action = str(sent.payload.get("action"))
    verb, _, rest = action.partition(" ")
    if verb in ("HOLD", "RTL", "LAND"):
        if rec.get("command") != verb:
            return [f"the recommendation proposed {rec.get('command')}, not {verb}"]
        if sent.vehicle_id != rec["vehicle_id"] or rest != rec["vehicle_id"]:
            return [f"the recommendation was for {rec['vehicle_id']}, not {rest}"]
        return []
    if verb == "RETASK":
        moves = ", ".join(f"{m['sector_id']}->{m['to_vehicle']}" for m in rec["sector_moves"])
        planned = {rec["vehicle_id"], *(m["to_vehicle"] for m in rec["sector_moves"])}
        if not rest.startswith(f"{moves} (") or sent.vehicle_id not in planned:
            return [f"the recommendation proposed moves {moves or 'none'}, not {rest}"]
        return []
    return [f"unknown action {action}"]


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: python -m c2.audit_verify DATABASE", file=sys.stderr)
        return 2
    found = problems(argv[0])
    for line in found:
        print(f"{argv[0]}: {line}", file=sys.stderr)
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
