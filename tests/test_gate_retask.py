"""A re-task is acknowledged one vehicle at a time (issue 77, audit finding NTC-07).

One 5 s window for the whole re-task grew with the number of vehicles, and a miss could not say
which vehicle's upload was unconfirmed. Now each vehicle that has a mission to fly has its own
window and its own audit rows, and a re-task may have a longer timeout than a HOLD or a LAND."""

import asyncio

import pytest

from c2.allocator import Assignment, assign, split_area
from c2.audit import AuditLog
from c2.fleet import FleetState
from c2.gate import CommandGate
from c2.hub import Hub
from c2.messages import Outcome, Recommendation, SectorMove
from navtrust.types import ReasonCode


class Clock:
    t = 100.0

    def __call__(self) -> float:
        return self.t


class SlowRetask:
    """A vehicle that takes `delay_s` to take a new mission, or never answers."""

    def __init__(self, delay_s: float = 0.0, silent: set[str] | None = None) -> None:
        self.delay_s = delay_s
        self.silent = silent or set()
        self.retasked: list[list[str]] = []

    async def hold(self, vehicle_id: str) -> None: ...
    async def return_to_launch(self, vehicle_id: str) -> None: ...
    async def land(self, vehicle_id: str) -> None: ...

    async def retask(self, assignment: Assignment, vehicles: list[str]) -> None:
        self.retasked.append(list(vehicles))
        if set(vehicles) & self.silent:
            await asyncio.sleep(3600)
        await asyncio.sleep(self.delay_s)


ONE = (SectorMove("S2", "uav3"),)  # uav2's only sector goes to uav3: uav2 has nothing left
TWO = (SectorMove("S2", "uav3"), SectorMove("S3", "uav1"))  # uav1 and uav3 both get a mission


def system(
    executor: SlowRetask,
    ack_s: float,
    retask_s: float | None = None,
    moves: tuple[SectorMove, ...] = ONE,
) -> tuple[Hub, CommandGate]:
    hub = Hub(AuditLog(), Clock())
    fleet = FleetState(assign(split_area(900, 900, 3), ["uav1", "uav2", "uav3"]))
    gate = CommandGate(hub, fleet, executor, ack_timeout_s=ack_s, retask_ack_timeout_s=retask_s)
    rec = Recommendation("r1", "uav2", 100.0, 160.0, ReasonCode.GNSS_LOSS, None, moves, "x")
    hub.add_recommendation(rec)
    hub.decide("r1", Outcome.APPROVED, "daniel")
    return hub, gate


def kinds(hub: Hub) -> list[tuple[str, str | None]]:
    return [(e.kind, e.vehicle_id) for e in hub.audit.events() if e.kind.startswith("command_")]


def test_each_vehicle_has_its_own_window_so_two_slow_uploads_are_not_one_slow_command() -> None:
    ex = SlowRetask(delay_s=0.15)  # two uploads take 0.3 s; each has a 0.2 s window
    hub, gate = system(ex, ack_s=0.2, moves=TWO)
    result = asyncio.run(gate.execute("r1"))
    assert result.executed, result.reason
    assert result.actions == [
        "RETASK S2->uav3, S3->uav1 (uav1)",
        "RETASK S2->uav3, S3->uav1 (uav3)",
    ]
    assert ex.retasked == [["uav1"], ["uav3"]]


def test_the_rows_name_the_vehicle_each_command_went_to() -> None:
    hub, gate = system(SlowRetask(), ack_s=0.5, moves=TWO)
    asyncio.run(gate.execute("r1"))
    assert kinds(hub) == [
        ("command_sent", "uav1"),
        ("command_acknowledged", "uav1"),
        ("command_sent", "uav3"),
        ("command_acknowledged", "uav3"),
        ("command_executed", "uav2"),
    ]


def test_the_vehicle_that_lost_all_its_sectors_is_sent_nothing() -> None:
    ex = SlowRetask()
    hub, gate = system(ex, ack_s=0.5)
    result = asyncio.run(gate.execute("r1"))
    assert result.executed and result.actions == ["RETASK S2->uav3 (uav3)"]
    assert ex.retasked == [["uav3"]]  # uav2 has no mission to fly; there is nothing to confirm
    assert ("command_sent", "uav2") not in kinds(hub)


def test_a_vehicle_that_never_answers_is_named_and_the_next_one_is_not_sent_anything() -> None:
    ex = SlowRetask(silent={"uav1"})
    hub, gate = system(ex, ack_s=0.05, moves=TWO)
    result = asyncio.run(gate.execute("r1"))
    assert not result.executed and result.reason is not None
    assert result.reason.startswith("not_acknowledged")
    assert kinds(hub) == [("command_sent", "uav1"), ("command_not_acknowledged", "uav1")]
    assert ex.retasked == [["uav1"]]  # nothing was resent, and uav3 was not asked
    again = asyncio.run(gate.execute("r1"))
    assert again.reason == "already_executed" and ex.retasked == [["uav1"]]


def test_a_vehicle_that_answers_after_another_one_failed_to_is_still_not_asked() -> None:
    ex = SlowRetask(silent={"uav3"})
    hub, gate = system(ex, ack_s=0.05, moves=TWO)
    result = asyncio.run(gate.execute("r1"))
    assert not result.executed
    assert kinds(hub) == [
        ("command_sent", "uav1"),
        ("command_acknowledged", "uav1"),
        ("command_sent", "uav3"),
        ("command_not_acknowledged", "uav3"),
    ]


def test_a_re_task_can_have_a_longer_timeout_than_the_other_commands() -> None:
    slow = SlowRetask(delay_s=0.2)
    hub, gate = system(slow, ack_s=0.1)  # no separate timeout: the re-task is not acknowledged
    assert not asyncio.run(gate.execute("r1")).executed
    slow = SlowRetask(delay_s=0.2)
    hub, gate = system(slow, ack_s=0.1, retask_s=0.6)
    assert asyncio.run(gate.execute("r1")).executed


def test_the_timeout_in_the_row_is_the_one_that_applied() -> None:
    hub, gate = system(SlowRetask(silent={"uav3"}), ack_s=5.0, retask_s=0.05)
    asyncio.run(gate.execute("r1"))
    [row] = hub.audit.events("command_not_acknowledged")
    assert row.payload["timeout_s"] == 0.05


def test_the_re_task_timeout_must_be_positive() -> None:
    hub = Hub(AuditLog(), Clock())
    fleet = FleetState(assign(split_area(900, 900, 3), ["uav1", "uav2", "uav3"]))
    with pytest.raises(ValueError, match="retask_ack_timeout_s"):
        CommandGate(hub, fleet, SlowRetask(), retask_ack_timeout_s=0)
