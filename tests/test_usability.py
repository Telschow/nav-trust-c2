import sqlite3
from pathlib import Path

import pytest

from c2.audit import AuditLog
from c2.hub import ExpiredRecommendation, Hub
from c2.messages import Command, Outcome, Recommendation, SectorMove
from eval.usability import main, read_session
from navtrust.types import ReasonCode


class Clock:
    t = 100.0

    def __call__(self) -> float:
        return self.t


def rec(
    rid: str, created: float, expires: float, command: Command | None = Command.LAND
) -> Recommendation:
    return Recommendation(
        rid, "uav2", created, expires, ReasonCode.INCONSISTENT_INNOVATION, command,
        (SectorMove("S2", "uav1"),), "x",
    )  # fmt: skip


def session(tmp_path: Path, name: str = "P1") -> tuple[Hub, Clock, Path]:
    path = tmp_path / f"{name}.sqlite"
    clock = Clock()
    return Hub(AuditLog(path), clock), clock, path


def test_time_to_decision_is_raised_to_answered(tmp_path: Path) -> None:
    hub, clock, path = session(tmp_path)
    hub.add_recommendation(rec("r1", 100.0, 160.0))
    clock.t = 117.5
    hub.decide("r1", Outcome.APPROVED, "P1")
    s = read_session(path)
    [r] = s.recommendations
    assert (r.outcome, r.decided_by, r.command) == ("APPROVED", "P1", "LAND")
    assert r.time_to_decision_s == pytest.approx(17.5) and r.raised_s == 100.0


def test_an_expired_then_reissued_recommendation_has_no_time_to_decision_for_the_first(
    tmp_path: Path,
) -> None:
    hub, clock, path = session(tmp_path)
    hub.add_recommendation(rec("r1", 100.0, 160.0))
    clock.t = 165.0
    hub.sweep()
    hub.add_recommendation(rec("r2", 165.0, 225.0))
    clock.t = 170.0
    hub.decide("r2", Outcome.DENIED, "P1")
    first, second = read_session(path).recommendations
    assert first.outcome == "EXPIRED" and first.time_to_decision_s is None
    assert second.outcome == "DENIED" and second.time_to_decision_s == pytest.approx(5.0)


def test_unanswered_and_rejected_attempts_are_counted(tmp_path: Path) -> None:
    hub, clock, path = session(tmp_path)
    hub.add_recommendation(rec("r1", 100.0, 160.0))
    clock.t = 170.0
    with pytest.raises(ExpiredRecommendation):
        hub.decide("r1", Outcome.APPROVED, "P1")  # too late: rejected and logged
    s = read_session(path)
    assert s.rejected_decisions == 1 and s.recommendations[0].outcome == "EXPIRED"
    hub2, _, path2 = session(tmp_path, "P2")
    hub2.add_recommendation(rec("r1", 100.0, 160.0))
    assert read_session(path2).recommendations[0].outcome is None


def test_the_database_is_opened_read_only(tmp_path: Path) -> None:
    hub, _, path = session(tmp_path)
    hub.add_recommendation(rec("r1", 100.0, 160.0))
    before = path.read_bytes()
    read_session(path)
    assert path.read_bytes() == before
    db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    with pytest.raises(sqlite3.OperationalError):
        db.execute(
            "INSERT INTO events (t_s, kind, vehicle_id, payload) VALUES (0, 'x', NULL, '{}')"
        )


def test_cli_prints_a_table_and_csv_and_reports_a_missing_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    hub, clock, path = session(tmp_path)
    hub.add_recommendation(rec("r1", 100.0, 160.0))
    clock.t = 110.0
    hub.decide("r1", Outcome.APPROVED, "P1")
    assert main([str(path)]) == 0
    assert "time to decision  10.0 s" in capsys.readouterr().out
    assert main([str(path), "--csv"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith("session,recommendation") and lines[1].startswith(
        "P1,r1,uav2,LAND,100.0,APPROVED,P1,10.0"
    )
    assert main([str(tmp_path / "nope.sqlite")]) == 1
