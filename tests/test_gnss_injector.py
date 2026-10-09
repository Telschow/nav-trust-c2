import asyncio

import pytest

pytest.importorskip("mavsdk_grpc")

from mavsdk_grpc.failure import FailureType  # noqa: E402

from sim.gnss_injector import ZoneInjector  # noqa: E402
from sim.interference import rectangle  # noqa: E402
from sim.survey import LocalPoint  # noqa: E402


def run_path(points: list[tuple[float, float]]) -> tuple[list[str | None], list[FailureType]]:
    sent: list[FailureType] = []

    async def inject(t: FailureType) -> None:
        sent.append(t)

    inj = ZoneInjector(rectangle(400, 0, 700, 1000), FailureType.OFF, inject)

    async def go() -> list[str | None]:
        return [await inj.update(LocalPoint(e, n)) for e, n in points]

    return asyncio.run(go()), sent


def test_injects_once_on_entry_and_clears_once_on_exit() -> None:
    actions, sent = run_path([(100, 50), (450, 50), (500, 50), (650, 50), (800, 50)])
    assert actions == [None, "enter", None, None, "exit"]
    assert sent == [FailureType.OFF, FailureType.OK]


def test_never_entering_sends_nothing() -> None:
    _, sent = run_path([(100, 50), (200, 900), (300, 10)])
    assert sent == []


def test_reentry_injects_again() -> None:
    actions, sent = run_path([(500, 10), (900, 10), (500, 20)])
    assert actions == ["enter", "exit", "enter"]
    assert sent == [FailureType.OFF, FailureType.OK, FailureType.OFF]


def test_failed_injection_is_retried_on_next_position() -> None:
    calls: list[FailureType] = []

    async def flaky(t: FailureType) -> None:
        calls.append(t)
        if len(calls) == 1:
            raise RuntimeError("no ack")

    inj = ZoneInjector(rectangle(400, 0, 700, 1000), FailureType.OFF, flaky)

    async def go() -> list[str | None]:
        out: list[str | None] = []
        with pytest.raises(RuntimeError):
            await inj.update(LocalPoint(500, 10))
        out.append(await inj.update(LocalPoint(510, 10)))
        out.append(await inj.update(LocalPoint(520, 10)))
        return out

    assert asyncio.run(go()) == ["enter", None]
    assert calls == [FailureType.OFF, FailureType.OFF]
    assert inj.inside
