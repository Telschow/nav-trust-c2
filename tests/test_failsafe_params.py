"""The data-link-loss failsafe is set on the vehicle and read back, so the recording can show it."""

import asyncio

import pytest

from sim.failsafe_params import apply_failsafe_params


class FakeParam:
    """Stands in for `drone.param`. `ignore` names parameters whose writes do not stick."""

    def __init__(self, start: dict[str, float], ignore: frozenset[str] = frozenset()) -> None:
        self.values = dict(start)
        self.ignore = ignore
        self.written: list[tuple[str, float]] = []

    async def set_param_int(self, name: str, value: int) -> None:
        self.written.append((name, value))
        if name not in self.ignore:
            self.values[name] = value

    async def get_param_int(self, name: str) -> int:
        return int(self.values[name])

    async def get_param_float(self, name: str) -> float:
        return float(self.values[name])


class FakeDrone:
    def __init__(self, param: FakeParam) -> None:
        self.param = param


# what the airframe leaves at the pinned PX4 commit: the failsafe off, 10 s, a 5 s hold
START = {"NAV_DLL_ACT": 0, "COM_DL_LOSS_T": 10, "COM_FAIL_ACT_T": 5.0}


def test_it_sets_return_and_ten_seconds_and_reports_what_the_vehicle_holds() -> None:
    param = FakeParam(START)
    held = asyncio.run(apply_failsafe_params(FakeDrone(param)))
    assert held == {"NAV_DLL_ACT": 2, "COM_DL_LOSS_T": 10, "COM_FAIL_ACT_T": 5.0}
    assert sorted(param.written) == [("COM_DL_LOSS_T", 10), ("NAV_DLL_ACT", 2)]


def test_a_write_that_did_not_stick_is_an_error_not_a_recording() -> None:
    param = FakeParam(START, ignore=frozenset({"NAV_DLL_ACT"}))
    with pytest.raises(RuntimeError, match="NAV_DLL_ACT"):
        asyncio.run(apply_failsafe_params(FakeDrone(param)))
