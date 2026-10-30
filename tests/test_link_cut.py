"""When the link is cut and restored, and a relay that really drops packets (loopback sockets)."""

import asyncio
import contextlib
import socket

from sim.link_cut import LinkCutSchedule, UdpRelay, drive_link_cut, relay_ports
from sim.scenario import LinkCut


def test_nothing_happens_until_the_anchor_event_and_the_delay_have_passed() -> None:
    schedule = LinkCutSchedule(LinkCut("mission_start", 40.0))
    assert schedule.poll(100.0) is None  # the mission has not started
    schedule.mission_started(10.0)
    assert schedule.poll(49.9) is None
    assert schedule.poll(50.0) == "cut"


def test_the_cut_fires_once_and_a_link_that_never_returns_never_restores() -> None:
    schedule = LinkCutSchedule(LinkCut("mission_start", 0.0, None))
    schedule.mission_started(0.0)
    assert schedule.poll(0.0) == "cut"
    assert [schedule.poll(t) for t in (1.0, 500.0)] == [None, None]


def test_a_link_with_a_duration_is_restored_once() -> None:
    schedule = LinkCutSchedule(LinkCut("mission_start", 40.0, 20.0))
    schedule.mission_started(0.0)
    assert schedule.poll(40.0) == "cut"
    assert schedule.poll(59.9) is None
    assert schedule.poll(60.0) == "restore"
    assert schedule.poll(61.0) is None


def test_a_cut_timed_from_the_fault_ignores_the_mission_start_and_a_second_fault() -> None:
    schedule = LinkCutSchedule(LinkCut("fault_start", 5.0))
    schedule.mission_started(0.0)
    assert schedule.poll(100.0) is None
    schedule.fault_started(30.0)
    schedule.fault_started(90.0)  # a zone can be entered twice; only the first counts
    assert schedule.poll(34.9) is None
    assert schedule.poll(35.0) == "cut"


HOST = "127.0.0.1"


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind((HOST, 0))
        return int(s.getsockname()[1])


class Inbox(asyncio.DatagramProtocol):
    """A UDP endpoint that queues what it receives. Plain asyncio, so it works on uvloop too
    (which has no `sock_recvfrom`)."""

    def __init__(self) -> None:
        self.queue: asyncio.Queue[tuple[bytes, tuple[str, int]]] = asyncio.Queue()
        self.transport: asyncio.DatagramTransport | None = None

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport = transport  # type: ignore[assignment]

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        self.queue.put_nowait((data, addr))

    def send(self, data: bytes, to: tuple[str, int]) -> None:
        assert self.transport is not None
        self.transport.sendto(data, to)

    def close(self) -> None:
        if self.transport is not None:
            self.transport.close()


async def endpoint(port: int) -> Inbox:
    inbox = Inbox()
    await asyncio.get_running_loop().create_datagram_endpoint(
        lambda: inbox, local_addr=(HOST, port)
    )
    return inbox


async def received(inbox: Inbox, wait_s: float = 1.0) -> tuple[bytes, tuple[str, int]] | None:
    try:
        return await asyncio.wait_for(inbox.queue.get(), wait_s)
    except TimeoutError:
        return None


def test_the_relay_carries_both_directions_drops_both_when_cut_and_resumes() -> None:
    async def scenario() -> list[object]:
        px4_listen, px4_remote, script_port = free_port(), free_port(), free_port()
        px4 = await endpoint(px4_remote)  # PX4's local port: it sends to px4_listen
        script = await endpoint(script_port)  # MAVSDK's udpin port
        relay = UdpRelay(px4_listen, px4_remote, script_port)
        await relay.start()
        seen: list[object] = []
        try:
            # downlink: PX4 to the script; the script answers the address it saw
            px4.send(b"telemetry", (HOST, px4_listen))
            down = await received(script)
            seen.append(down and down[0])
            assert down is not None
            script.send(b"command", down[1])
            up = await received(px4)
            seen.append(up and up[0])

            relay.cut()
            px4.send(b"telemetry-2", (HOST, px4_listen))
            script.send(b"command-2", down[1])
            seen.append(await received(script, 0.3))
            seen.append(await received(px4, 0.3))

            relay.restore()
            px4.send(b"telemetry-3", (HOST, px4_listen))
            again = await received(script)
            seen.append(again and again[0])
        finally:
            await relay.stop()
            px4.close()
            script.close()
        return seen

    assert asyncio.run(scenario()) == [b"telemetry", b"command", None, None, b"telemetry-3"]


class FakeRelay:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def cut(self, direction: str) -> None:
        self.calls.append("cut")

    def restore(self) -> None:
        self.calls.append("restore")


def test_the_driver_cuts_and_restores_the_relay_and_logs_each_once() -> None:
    clock = [0.0]
    written: list[str] = []
    relay = FakeRelay()
    schedule = LinkCutSchedule(LinkCut("mission_start", 2.0, 3.0))
    schedule.mission_started(0.0)

    async def sleep(_: float) -> None:
        clock[0] += 1.0
        if clock[0] > 10.0:
            raise asyncio.CancelledError

    async def go() -> None:
        await drive_link_cut(relay, schedule, written.append, lambda: clock[0], sleep)

    with contextlib.suppress(asyncio.CancelledError):
        asyncio.run(go())
    assert relay.calls == ["cut", "restore"]
    assert written == ["link_cut", "link_restore"]


def test_an_uplink_only_cut_drops_commands_but_the_recorder_still_hears_the_vehicle() -> None:
    async def scenario() -> list[object]:
        px4_listen, px4_remote, script_port = free_port(), free_port(), free_port()
        px4 = await endpoint(px4_remote)
        script = await endpoint(script_port)
        relay = UdpRelay(px4_listen, px4_remote, script_port)
        await relay.start()
        seen: list[object] = []
        try:
            px4.send(b"telemetry", (HOST, px4_listen))
            first = await received(script)
            assert first is not None

            relay.cut("uplink")
            px4.send(b"telemetry-2", (HOST, px4_listen))
            during = await received(script)  # the failsafe stays visible in the recording
            seen.append(during and during[0])
            script.send(b"heartbeat", first[1])
            seen.append(await received(px4, 0.3))  # PX4 hears no ground station

            relay.restore()
            script.send(b"heartbeat-2", first[1])
            after = await received(px4)
            seen.append(after and after[0])
        finally:
            await relay.stop()
            px4.close()
            script.close()
        return seen

    assert asyncio.run(scenario()) == [b"telemetry-2", None, b"heartbeat-2"]


def test_the_relay_ports_follow_from_the_script_address() -> None:
    # instance 1: PX4 sends to 14541 from 14581; scripts listen 100 higher
    assert relay_ports("udpin://0.0.0.0:14541") == (14541, 14581, 14641)


def test_a_repeating_cut_drops_and_restores_the_link_the_given_number_of_times() -> None:
    schedule = LinkCutSchedule(LinkCut("mission_start", 40.0, 6.0, cycles=3, gap_s=20.0))
    schedule.mission_started(0.0)
    seen = [(t, a) for t in range(0, 200) if (a := schedule.poll(float(t)))]
    # cut at 40, restore at 46, then 20 s up, cut at 66, restore at 72, cut at 92, restore at 98
    assert seen == [
        (40, "cut"), (46, "restore"), (66, "cut"), (72, "restore"), (92, "cut"), (98, "restore"),
    ]  # fmt: skip


def test_the_next_cut_is_timed_from_the_restore_not_from_the_first_cut() -> None:
    schedule = LinkCutSchedule(LinkCut("mission_start", 0.0, 6.0, cycles=2, gap_s=20.0))
    schedule.mission_started(0.0)
    assert schedule.poll(0.0) == "cut"
    assert schedule.poll(6.5) == "restore"  # a late poll: the gap starts here
    assert schedule.poll(26.0) is None
    assert schedule.poll(26.5) == "cut"


def test_a_single_cycle_behaves_as_before() -> None:
    schedule = LinkCutSchedule(LinkCut("mission_start", 0.0, 5.0))
    schedule.mission_started(0.0)
    assert [schedule.poll(t) for t in (0.0, 5.0, 30.0, 100.0)] == ["cut", "restore", None, None]


def test_a_repeating_cut_with_no_duration_is_refused_by_the_schedule_too() -> None:
    import pytest

    with pytest.raises(ValueError, match="cycles"):
        LinkCutSchedule(LinkCut("mission_start", 0.0, None, cycles=2, gap_s=10.0))
