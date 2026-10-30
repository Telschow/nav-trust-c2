"""Cut the MAVLink link between PX4 and the scripts for one vehicle, on a schedule.

PX4's data-link-loss failsafe fires when it stops hearing a ground station. MAVSDK presents
itself as one, so dropping the UDP packets in both directions is a lost link to PX4. Nothing
here touches the vehicle or the simulator: it only decides when, and drops datagrams.

A recording of a run with a cut also has these events, on top of the ones listed in
navtrust/recording.py (see docs/validation/px4-lost-link-parameters.md):
`failsafe_params` (what the vehicle holds), `flight_mode` (PX4's mode on each change, which
shows what acted), `link_cut` and `link_restore`.

Whether PX4 really treats the cut as a lost ground station is not shown by any test here: it
needs a simulator run (issue 74). The relay is tested on loopback sockets only.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Protocol

from sim.scenario import LinkCut

# PX4's MAVLink instance for MAVSDK sends to 14540 + instance from 14580 + instance. With a link
# cut, scripts listen 100 ports higher and the relay takes 14540 + instance.
RELAY_PX4_LOCAL_OFFSET = 40
RELAY_SCRIPT_OFFSET = 100


def relay_ports(system_address: str) -> tuple[int, int, int]:
    """(relay listens, PX4 listens, scripts listen) for an address like udpin://0.0.0.0:14541."""
    port = int(system_address.rsplit(":", 1)[1])
    return port, port + RELAY_PX4_LOCAL_OFFSET, port + RELAY_SCRIPT_OFFSET


class LinkCutSchedule:
    """Fed the moments a scenario cares about; `poll` says when to cut and restore.

    A cut with no duration never returns. With a duration it is restored, and with `cycles` above
    one the link is cut again `gap_s` after each restore, `cycles` times in all."""

    def __init__(self, cut: LinkCut) -> None:
        if cut.cycles > 1 and (cut.duration_s is None or cut.gap_s is None):
            raise ValueError("a link cut with cycles above 1 needs a duration_s and a gap_s")
        self._cut = cut
        self.direction = cut.direction
        self._anchor_s: float | None = None
        self._cut_at_s: float | None = None  # when the cut now in force began
        self._next_cut_s: float | None = None  # set after a restore, when more cycles remain
        self._cuts = 0

    def mission_started(self, now_s: float) -> None:
        if self._cut.after == "mission_start":
            self._anchor(now_s)

    def fault_started(self, now_s: float) -> None:
        if self._cut.after == "fault_start":
            self._anchor(now_s)

    def _anchor(self, now_s: float) -> None:
        if self._anchor_s is None:
            self._anchor_s = now_s

    def poll(self, now_s: float) -> str | None:
        """'cut' or 'restore' at the moment each is due, else None."""
        if self._anchor_s is None:
            return None
        if self._cut_at_s is None:
            if self._cuts >= self._cut.cycles:
                return None
            due_s = (
                self._next_cut_s
                if self._next_cut_s is not None
                else self._anchor_s + self._cut.delay_s
            )
            if now_s >= due_s:
                self._cut_at_s = now_s
                self._cuts += 1
                return "cut"
            return None
        if self._cut.duration_s is not None and now_s >= self._cut_at_s + self._cut.duration_s:
            self._cut_at_s = None
            if self._cuts < self._cut.cycles and self._cut.gap_s is not None:
                self._next_cut_s = now_s + self._cut.gap_s
            return "restore"
        return None


class _Side(asyncio.DatagramProtocol):
    def __init__(self, on_datagram: Callable[[bytes], None]) -> None:
        self._on_datagram = on_datagram

    def datagram_received(self, data: bytes, addr: tuple[str | int, ...]) -> None:
        self._on_datagram(data)


class UdpRelay:
    """Sits between PX4 and the scripts on loopback and drops every datagram while cut.

    PX4's MAVLink instance for MAVSDK sends to `px4_listen_port` (14540 + instance) from
    `px4_remote_port` (14580 + instance). The relay binds the first; scripts listen on
    `script_port` instead and answer the address they see, which is the relay's own.
    """

    def __init__(
        self, px4_listen_port: int, px4_remote_port: int, script_port: int, host: str = "127.0.0.1"
    ) -> None:
        self._host = host
        self._px4_listen_port = px4_listen_port
        self._px4_remote = (host, px4_remote_port)
        self._script = (host, script_port)
        self._px4_side: asyncio.DatagramTransport | None = None
        self._script_side: asyncio.DatagramTransport | None = None
        self.is_cut = False
        self._direction = "both"

    async def start(self) -> None:
        loop = asyncio.get_running_loop()
        px4_side, _ = await loop.create_datagram_endpoint(
            lambda: _Side(self._from_px4), local_addr=(self._host, self._px4_listen_port)
        )
        script_side, _ = await loop.create_datagram_endpoint(
            lambda: _Side(self._from_script), local_addr=(self._host, 0)
        )
        self._px4_side, self._script_side = px4_side, script_side

    async def stop(self) -> None:
        for side in (self._px4_side, self._script_side):
            if side is not None:
                side.close()

    def cut(self, direction: str = "both") -> None:
        """Drop datagrams: "both" drops everything, "uplink" only what the scripts send to PX4."""
        self.is_cut = True
        self._direction = direction

    def restore(self) -> None:
        self.is_cut = False

    def _from_px4(self, data: bytes) -> None:
        dropped = self.is_cut and self._direction == "both"
        if not dropped and self._script_side is not None:
            self._script_side.sendto(data, self._script)

    def _from_script(self, data: bytes) -> None:
        if not self.is_cut and self._px4_side is not None:
            self._px4_side.sendto(data, self._px4_remote)


class Cuttable(Protocol):
    def cut(self, direction: str) -> None: ...

    def restore(self) -> None: ...


async def drive_link_cut(
    relay: Cuttable,
    schedule: LinkCutSchedule,
    write: Callable[[str], None],
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    poll_s: float = 0.1,
) -> None:
    """Poll the schedule and act on the relay until cancelled. `write` logs 'link_cut' and
    'link_restore'."""
    while True:
        action = schedule.poll(clock())
        if action == "cut":
            relay.cut(schedule.direction)
            write("link_cut")
        elif action == "restore":
            relay.restore()
            write("link_restore")
        await sleep(poll_s)
