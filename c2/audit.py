"""Append-only audit log in SQLite. There is deliberately no update or delete method."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    t_s        REAL NOT NULL,
    kind       TEXT NOT NULL,
    vehicle_id TEXT,
    payload    TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS events_no_update BEFORE UPDATE ON events
BEGIN SELECT RAISE(ABORT, 'audit log is append-only'); END;
CREATE TRIGGER IF NOT EXISTS events_no_delete BEFORE DELETE ON events
BEGIN SELECT RAISE(ABORT, 'audit log is append-only'); END;
"""


@dataclass(frozen=True)
class AuditEvent:
    id: int
    t_s: float
    kind: str
    vehicle_id: str | None
    payload: dict[str, Any]


class AuditLog:
    def __init__(self, path: str | Path = ":memory:") -> None:
        # check_same_thread=False: FastAPI may call from different threads; writes are
        # serialised by SQLite itself.
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._db.executescript(_SCHEMA)

    def append(
        self, t_s: float, kind: str, vehicle_id: str | None, payload: dict[str, Any]
    ) -> AuditEvent:
        with self._db:
            cur = self._db.execute(
                "INSERT INTO events (t_s, kind, vehicle_id, payload) VALUES (?, ?, ?, ?)",
                (t_s, kind, vehicle_id, json.dumps(payload, sort_keys=True)),
            )
        assert cur.lastrowid is not None
        return AuditEvent(cur.lastrowid, t_s, kind, vehicle_id, payload)

    def events(self, kind: str | None = None, vehicle_id: str | None = None) -> list[AuditEvent]:
        query, args = "SELECT id, t_s, kind, vehicle_id, payload FROM events", []
        clauses = []
        if kind is not None:
            clauses.append("kind = ?")
            args.append(kind)
        if vehicle_id is not None:
            clauses.append("vehicle_id = ?")
            args.append(vehicle_id)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        rows = self._db.execute(query + " ORDER BY id", args).fetchall()
        return [AuditEvent(r[0], r[1], r[2], r[3], json.loads(r[4])) for r in rows]

    def close(self) -> None:
        self._db.close()
